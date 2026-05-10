# Phase B — Real Semantic Embeddings: Implementation Plan

## Context

The current `embedder_service.py` uses SHA-256 hashing to produce 384-dimensional vectors. These are deterministic but semantically random — `"draw a line"` and `"LINE command"` get completely dissimilar vectors despite being conceptually identical. This makes the entire RAG pipeline useless. Phase B replaces the mock with `sentence-transformers` `all-MiniLM-L6-v2`, which produces real 384-dimensional semantic vectors matching the existing pgvector schema exactly — no DB migration needed.

---

## Files to Change

| File                                                 | Change                                         |
| ---------------------------------------------------- | ---------------------------------------------- |
| `trainerAI_backend/requirements.txt`                 | Add `sentence-transformers` and `torch`        |
| `trainerAI_backend/app/services/embedder_service.py` | Full rewrite — replace SHA-256 with real model |
| `trainerAI_backend/tests/test_embedder_service.py`   | New file — semantic similarity tests           |

**No changes needed to:**

- `rag_service.py` — already calls `embed_text()` correctly
- `db/schema.py` — already uses `vector(384)`, which matches `all-MiniLM-L6-v2` output
- `db/crud.py` — cosine similarity query is already correct
- All other test files — RAG tests mock `crud.query_similar_embeddings`, so real vectors from `embed_text()` pass through without issue

---

## Step-by-Step Implementation

### Step 1 — Update `requirements.txt`

**File:** `trainerAI_backend/requirements.txt`

Append two lines:

```
sentence-transformers>=3.0.0
torch>=2.3.0
```

`torch` is listed explicitly for clarity; `sentence-transformers` pulls it transitively, but pinning avoids version ambiguity.

---

### Step 2 — Rewrite `embedder_service.py`

**File:** `trainerAI_backend/app/services/embedder_service.py`

Replace the entire file content with:

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

- `@lru_cache(maxsize=1)` — model loads exactly once per process, not per request
- `normalize_embeddings=True` — produces unit-length vectors required for correct cosine similarity in pgvector
- No async wrapper needed — `encode()` takes ~5–15 ms on CPU, acceptable for now
- The public API (`embed_text(text: str) -> List[float]`) is unchanged — all callers work without modification

---

### Step 3 — Add `tests/test_embedder_service.py`

**File:** `trainerAI_backend/tests/test_embedder_service.py`

New test file covering:

1. Output is a list of exactly 384 floats
2. Semantically similar strings have high dot product (> 0.6)
3. Semantically unrelated strings have low dot product (< 0.3)
4. Model is cached — second call completes in < 3 seconds
5. Output is deterministic — same input always gives same vector

```python
import time
import pytest
from app.services.embedder_service import embed_text


def test_embed_text_returns_384_floats():
    vector = embed_text("test string")
    assert isinstance(vector, list)
    assert len(vector) == 384
    assert all(isinstance(x, float) for x in vector)


def test_semantic_similarity_related_strings():
    v1 = embed_text("draw a line")
    v2 = embed_text("LINE command in AutoCAD")
    dot = sum(x * y for x, y in zip(v1, v2))
    assert dot > 0.6, f"Expected > 0.6, got {dot}"


def test_semantic_similarity_unrelated_strings():
    v1 = embed_text("draw a line")
    v3 = embed_text("how to make coffee")
    dot = sum(x * y for x, y in zip(v1, v3))
    assert dot < 0.3, f"Expected < 0.3, got {dot}"


def test_model_is_cached():
    embed_text("warmup")  # ensure model is loaded
    start = time.perf_counter()
    embed_text("second call")
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0, f"Second call took {elapsed:.2f}s — model may not be cached"


def test_embed_text_is_deterministic():
    v1 = embed_text("AutoCAD circle command")
    v2 = embed_text("AutoCAD circle command")
    assert v1 == v2
```

---

## Installation (outside VS Code)

After editing the files, run in the backend virtualenv:

```powershell
cd trainerAI_backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

First run downloads `all-MiniLM-L6-v2` (~90 MB) to `~/.cache/huggingface/`. Subsequent runs use the cache.

---

## Re-seed Existing Test Embeddings (if any exist)

If mock embeddings were previously inserted, clear them:

```powershell
docker exec -it trainerai_postgres psql -U trainerai -d trainerai_db
```

```sql
DELETE FROM embeddings;
\q
```

Real embeddings will be populated by Phase D (video training pipeline).

---

## Verification

### 1. Smoke test the embedder

```powershell
python -c "from app.services.embedder_service import embed_text; v = embed_text('draw a line in AutoCAD'); print(f'dim={len(v)}, first3={v[:3]}')"
# Expected: dim=384, first3=[<float>, <float>, <float>]
```

### 2. Run the full test suite

```powershell
pytest tests/ -v
```

All existing tests should pass. The new `test_embedder_service.py` should show 5 passing tests.

---

## Acceptance Criteria

- [ ] `embed_text("test")` returns a `list` of exactly 384 `float` values
- [ ] `embed_text("LINE command") · embed_text("draw a line") > 0.6`
- [ ] `embed_text("draw a line") · embed_text("how to make coffee") < 0.3`
- [ ] Second call to `embed_text()` completes in < 3 seconds (model cached)
- [ ] `pytest tests/` passes with no regressions
- [ ] Backend starts cleanly: `uvicorn app.main:app --reload`
