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
    assert dot > 0.4, f"Expected > 0.4, got {dot}"


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


def test_embed_texts_returns_correct_count_and_dimension():
    from app.services.embedder_service import embed_texts
    vectors = embed_texts(["foo", "bar", "baz"])
    assert len(vectors) == 3
    assert all(len(v) == 384 for v in vectors)
    assert all(isinstance(x, float) for v in vectors for x in v)


def test_embed_texts_empty_returns_empty():
    from app.services.embedder_service import embed_texts
    assert embed_texts([]) == []
