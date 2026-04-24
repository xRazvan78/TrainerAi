# Phase B — Real Semantic Embeddings

**Prerequisite for**: Phase D (video ingestion), meaningful RAG results  
**Depends on**: Phase A (PostgreSQL running)  
**Estimated effort**: 2–3 hours  
**Outside VS Code work**: Minor (pip install, first-run model download)

---

## Goal

Replace the SHA-256 deterministic mock in `embedder_service.py` with a real local semantic embedding model. The existing pgvector schema already expects 384-dimensional float vectors — `all-MiniLM-L6-v2` produces exactly that.

Without this, the RAG retrieval pipeline returns semantically meaningless results regardless of how good the indexed knowledge is.

---

## Background: Why the Current Embedder is Broken

`embedder_service.py` currently does:

```python
import hashlib, struct
hash_bytes = hashlib.sha256(text.encode()).digest()  # 32 bytes
# pad/truncate to 384 floats
```

This produces deterministic but **semantically random** vectors. Two strings like `"draw a line"` and `"LINE command"` will have completely dissimilar vectors despite being about the same concept. Similarity search is therefore useless.

---

## In VS Code — Changes Required

### 1. `trainerAI_backend/requirements.txt`

Add:

```
sentence-transformers >= 3.0.0
torch >= 2.3.0          # CPU-only build is fine; sentence-transformers pulls it automatically
```

> `sentence-transformers` downloads the model on first use (~90 MB) and caches it locally in `~/.cache/huggingface/`. No GPU required — the model runs fast on CPU.

---

### 2. `trainerAI_backend/app/services/embedder_service.py`

Rewrite completely:

```python
"""
Real semantic embedding service using sentence-transformers all-MiniLM-L6-v2.
Produces 384-dimensional float vectors — matches the pgvector schema exactly.
Model is downloaded once on first use (~90 MB) and cached locally.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_EXPECTED_DIM = 384


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load the model once and keep it in memory for the process lifetime."""
    return SentenceTransformer(_MODEL_NAME)


def embed_text(text: str) -> List[float]:
    """
    Embed a single string into a 384-dimensional float vector.
    Thread-safe; model is loaded once via lru_cache.
    """
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    assert len(vector) == _EXPECTED_DIM, (
        f"Embedding dimension mismatch: expected {_EXPECTED_DIM}, got {len(vector)}"
    )
    return vector.tolist()
```

**Key design decisions:**

- `@lru_cache(maxsize=1)` ensures the model is loaded into memory exactly once per process, not once per request
- `normalize_embeddings=True` produces unit-length vectors — required for cosine similarity search in pgvector to behave correctly
- No async wrapper needed; `encode()` is fast enough on CPU (~5–15 ms for typical short strings) to not block the event loop meaningfully. If needed later, wrap with `asyncio.to_thread()`

---

### 3. `trainerAI_backend/app/services/rag_service.py`

No code changes needed — it already calls `embed_text()`. After this phase, the embedded query vectors will be semantically meaningful.

---

## Outside VS Code — Install and Verify

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

First-time model download happens automatically when you first call `embed_text()`. To pre-download and verify:

```powershell
python -c "from app.services.embedder_service import embed_text; v = embed_text('draw a line in AutoCAD'); print(f'dim={len(v)}, first3={v[:3]}')"
```

Expected output: `dim=384, first3=[<some float>, <some float>, <some float>]`

---

## Outside VS Code — Re-seed Any Existing Test Embeddings

If you previously inserted any test embeddings with the mock hash embedder, they must be deleted and re-inserted. Their vectors are semantically garbage.

```powershell
# Connect to the running postgres container
docker exec -it trainerai_postgres psql -U trainerai -d trainerai_db

# Delete all mock embeddings
DELETE FROM embeddings;

# Exit psql
\q
```

After Phase D (video training pipeline) completes, real embeddings will be inserted into this table.

---

## Test: Semantic Similarity Should Now Work

With the real embedder and some test data, verify that semantically similar strings return each other:

```python
from app.services.embedder_service import embed_text

v1 = embed_text("draw a line")
v2 = embed_text("LINE command in AutoCAD")
v3 = embed_text("how to make coffee")

import numpy as np
dot = lambda a, b: sum(x*y for x, y in zip(a, b))
print(dot(v1, v2))  # should be > 0.7
print(dot(v1, v3))  # should be < 0.3
```

---

## Acceptance Criteria

- [ ] `embed_text("test")` returns a list of exactly 384 floats
- [ ] Semantic similarity: `embed_text("LINE command") · embed_text("draw a line") > 0.6`
- [ ] Model loads in < 3 seconds on second call (cached via `lru_cache`)
- [ ] Backend starts without error after requirements update
- [ ] Existing test suite (`pytest tests/`) still passes (mock calls will now return real vectors)

---

## Notes on Future Upgrade

`all-MiniLM-L6-v2` is intentionally chosen because:

1. Exactly 384 dimensions — matches the existing DB schema with no migration needed
2. Fast on CPU — suitable for real-time inference in a dev environment
3. Good enough for AutoCAD domain with RAG (domain-specific fine-tuning is a later optimisation)

If you later need higher quality embeddings, `all-mpnet-base-v2` (768-dim) or a domain-tuned model are options, but they require a DB migration to change the vector dimension.
