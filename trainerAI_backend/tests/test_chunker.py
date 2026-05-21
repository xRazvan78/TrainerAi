import pytest
from app.training.chunker import make_chunks, _detect_tool, _collect_tags, _CHUNK_WORD_LIMIT


def _make_seg(start: float, end: float, text: str) -> dict:
    return {"start": start, "end": end, "text": text}


def test_make_chunks_empty_segments():
    assert make_chunks([], "test_video") == []


def test_make_chunks_single_short_segment():
    segs = [_make_seg(0, 5, "Hello world")]
    chunks = make_chunks(segs, "test_video")
    assert len(chunks) == 1
    assert chunks[0]["source_video"] == "test_video"
    assert chunks[0]["text"] == "Hello world"


def test_make_chunks_word_limit():
    # Generate a segment with exactly CHUNK_WORD_LIMIT + 10 words
    words = ["word"] * (_CHUNK_WORD_LIMIT + 10)
    segs = [_make_seg(0, 60, " ".join(words))]
    chunks = make_chunks(segs, "test_video")
    # Should produce 2 chunks: one at word limit, one for remainder
    assert len(chunks) >= 2


def test_make_chunks_overlap():
    # Two segments that together exceed word limit: second chunk should start with overlap words
    w1 = ["alpha"] * _CHUNK_WORD_LIMIT
    w2 = ["beta"] * 50
    segs = [
        _make_seg(0, 30, " ".join(w1)),
        _make_seg(30, 60, " ".join(w2)),
    ]
    chunks = make_chunks(segs, "vid")
    assert len(chunks) >= 2
    # The second chunk should contain overlap words from the first
    assert "alpha" in chunks[1]["text"]


def test_detect_tool_fillet():
    assert _detect_tool("Use the FILLET command to round corners") == "FILLET"


def test_detect_tool_general():
    assert _detect_tool("This is a general introduction to the software") == "general"


def test_collect_tags_multiple():
    tags = _collect_tags("Use TRIM and EXTEND to clean up lines")
    assert "TRIM" in tags
    assert "EXTEND" in tags


def test_make_chunks_tool_hint_detected():
    segs = [_make_seg(0, 10, "FILLET " + "word " * 50)]
    chunks = make_chunks(segs, "fillet_video")
    assert chunks[0]["active_tool_hint"] == "FILLET"
