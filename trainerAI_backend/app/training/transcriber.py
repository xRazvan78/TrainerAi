"""
Transcribes audio using OpenAI Whisper (local, no API key needed).
Falls back to a sibling .srt file if present.
Returns a list of segments: {start, end, text}.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, TypedDict


class Segment(TypedDict):
    start: float   # seconds
    end: float
    text: str


def _srt_time_to_seconds(t: str) -> float:
    """Convert SRT timestamp '00:04:12,345' to float seconds."""
    h, m, rest = t.strip().split(":")
    s, ms = rest.replace(",", ".").split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _try_load_srt(video_path: Path) -> List[Segment] | None:
    """If a sibling .en.srt or .srt exists, parse it instead of running Whisper."""
    for suffix in (".en.srt", ".srt"):
        srt_path = video_path.with_suffix(suffix)
        if srt_path.exists():
            return _parse_srt(srt_path)
    return None


def _parse_srt(srt_path: Path) -> List[Segment]:
    """Parse a .srt subtitle file into Segment dicts."""
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\n+", content.strip())
    segments: List[Segment] = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        # lines[0]: sequence number, lines[1]: timestamp range, lines[2+]: text
        m = re.match(r"(\S+)\s*-->\s*(\S+)", lines[1])
        if not m:
            continue
        try:
            start = _srt_time_to_seconds(m.group(1))
            end = _srt_time_to_seconds(m.group(2))
        except (ValueError, IndexError):
            continue
        text = " ".join(lines[2:]).strip()
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return segments


def transcribe(audio_path: str | Path, model_name: str = "base.en",
               video_path: str | Path | None = None) -> List[Segment]:
    """
    Transcribe an audio file using Whisper, or parse a sibling .srt if one exists.
    Pass `video_path` so the SRT short-circuit can probe for a subtitle file.
    """
    if video_path is not None:
        srt_segments = _try_load_srt(Path(video_path))
        if srt_segments is not None:
            print(f"      SRT short-circuit: loaded {len(srt_segments)} segments from subtitle file")
            return srt_segments

    import whisper  # deferred import — not installed in test env
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path), language="en", fp16=False)
    return [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
        for seg in result["segments"]
    ]
