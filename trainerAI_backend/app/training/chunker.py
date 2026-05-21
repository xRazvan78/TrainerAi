"""
Splits a transcript (list of timed segments) into knowledge chunks.
Each chunk is ~300 words, contains metadata about its source position.
Attempts to detect the AutoCAD tool/command being discussed.
"""
from __future__ import annotations

import re
from typing import List, TypedDict

_AUTOCAD_COMMANDS = {
    "LINE", "CIRCLE", "ARC", "RECTANGLE", "RECTANG", "TRIM", "EXTEND",
    "OFFSET", "MIRROR", "COPY", "MOVE", "ROTATE", "SCALE", "STRETCH",
    "FILLET", "CHAMFER", "HATCH", "DIMENSION", "DIM", "BLOCK", "INSERT",
    "LAYER", "PROPERTIES", "EXPLODE", "PEDIT", "SPLINE", "ELLIPSE",
    "POLYGON", "XREF", "PLOT", "ARRAY", "ZOOM", "PAN", "OSNAP",
}

_CHUNK_WORD_LIMIT = 300
_CHUNK_OVERLAP_WORDS = 30


class Chunk(TypedDict):
    text: str
    source_video: str
    timestamp_start: float
    timestamp_end: float
    active_tool_hint: str
    tags: List[str]


def _detect_tool(text: str) -> str:
    upper = text.upper()
    for cmd in _AUTOCAD_COMMANDS:
        if re.search(rf"\b{cmd}\b", upper):
            return cmd
    return "general"


def _collect_tags(text: str) -> List[str]:
    upper = text.upper()
    return [cmd for cmd in _AUTOCAD_COMMANDS if re.search(rf"\b{cmd}\b", upper)]


def make_chunks(segments: list, source_video: str) -> List[Chunk]:
    """
    Merge transcript segments into word-limited chunks with overlap.
    """
    chunks: List[Chunk] = []
    buffer_words: List[str] = []
    buffer_start: float | None = None  # None = will be set from next segment's start
    buffer_end = 0.0

    for seg in segments:
        words = seg["text"].split()
        if buffer_start is None:
            buffer_start = seg["start"]

        buffer_words.extend(words)
        buffer_end = seg["end"]

        if len(buffer_words) >= _CHUNK_WORD_LIMIT:
            text = " ".join(buffer_words)
            chunks.append(
                Chunk(
                    text=text,
                    source_video=source_video,
                    timestamp_start=buffer_start,
                    timestamp_end=buffer_end,
                    active_tool_hint=_detect_tool(text),
                    tags=_collect_tags(text),
                )
            )
            # Keep overlap words; timestamp_start for the next chunk comes from
            # the next segment (overlap words inherit the next segment's start time).
            buffer_words = buffer_words[-_CHUNK_OVERLAP_WORDS:]
            buffer_start = None

    if buffer_words:
        text = " ".join(buffer_words)
        chunks.append(
            Chunk(
                text=text,
                source_video=source_video,
                timestamp_start=buffer_start if buffer_start is not None else 0.0,
                timestamp_end=buffer_end,
                active_tool_hint=_detect_tool(text),
                tags=_collect_tags(text),
            )
        )

    return chunks
