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


def embed_texts(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Embed many strings in one model call (~10x faster than calling embed_text in a loop)."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    assert vectors.shape[1] == _EXPECTED_DIM, (
        f"Embedding dimension mismatch: expected {_EXPECTED_DIM}, got {vectors.shape[1]}"
    )
    return vectors.tolist()
