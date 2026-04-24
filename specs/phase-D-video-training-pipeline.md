# Phase D — Video Training Pipeline

**Prerequisite for**: A populated pgvector knowledge base  
**Depends on**: Phase A (PostgreSQL running), Phase B (real embeddings)  
**Estimated effort**: 6–10 hours  
**Outside VS Code work**: Yes — installing Whisper, preparing video files, running the ingest CLI

---

## Goal

Build a CLI pipeline that takes AutoCAD tutorial `.mp4` files as input and populates the pgvector `embeddings` table with semantically searchable knowledge chunks. Without this, the RAG service has nothing to retrieve and the LLM guidance will be generic.

---

## Overall Pipeline

```
tutorial.mp4
      │
      ▼
[video_extractor.py]     — sample frames every N seconds
      │
      ├──► [transcriber.py]     — Whisper speech-to-text on audio track
      │         │
      │         ▼
      │    transcript.txt       — time-stamped narration text
      │
      └──► [frame_captioner.py] — EasyOCR on sampled frames (optional, Phase G)
                │
                ▼
           frame_captions.json

[chunker.py]
      │ combines transcript segments + optional frame text
      │ splits into ~300-word knowledge chunks with metadata
      ▼
chunks[]  {text, source_video, timestamp_start, active_tool_hint, tags[]}

[ingest.py]  — embeds each chunk + inserts into pgvector
      │
      ▼
embeddings table: {content, embedding[384], metadata_jsonb}
```

---

## Outside VS Code — Prerequisites

### 1. Install FFmpeg (required by Whisper for audio extraction)

Download from https://ffmpeg.org/download.html or use winget:

```powershell
winget install Gyan.FFmpeg
# Then restart PowerShell so ffmpeg is on PATH
ffmpeg -version
```

### 2. Install Whisper and its dependencies

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
.venv\Scripts\Activate.ps1

pip install openai-whisper
pip install opencv-python-headless
pip install easyocr          # optional for frame captions
```

> Whisper downloads the model on first use. Recommended model: `base.en` (~145 MB, English only, fast). Use `medium.en` for better accuracy on technical vocabulary.

### 3. Prepare tutorial videos

Create a folder for raw input videos:

```
TrainerAi/
└── training_videos/
    ├── autocad_basics_lines.mp4
    ├── autocad_fillet_chamfer.mp4
    └── ...
```

Good sources: official Autodesk YouTube channel, LinkedIn Learning AutoCAD courses. Keep videos under 60 min per file for reasonable processing times.

---

## In VS Code — New Module Structure

Create the following directory and files inside `trainerAI_backend/app/`:

```
trainerAI_backend/app/training/
    __init__.py
    video_extractor.py
    transcriber.py
    chunker.py
    ingest.py
```

---

### `training/__init__.py`

Empty file.

---

### `training/video_extractor.py`

```python
"""
Extracts the audio track from an MP4 file using FFmpeg.
Returns the path to the extracted .wav file.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def extract_audio(video_path: str | Path) -> Path:
    """
    Extract audio from video file to a temporary WAV file.
    Returns the path to the WAV file. Caller is responsible for cleanup.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav_path = Path(tmp.name)
    tmp.close()

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",                    # no video
            "-acodec", "pcm_s16le",   # WAV PCM
            "-ar", "16000",           # 16kHz — Whisper requirement
            "-ac", "1",               # mono
            str(wav_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")

    return wav_path
```

---

### `training/transcriber.py`

```python
"""
Transcribes audio using OpenAI Whisper (local, no API key needed).
Returns a list of segments: {start, end, text}.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, TypedDict

import whisper


class Segment(TypedDict):
    start: float   # seconds
    end: float
    text: str


def transcribe(audio_path: str | Path, model_name: str = "base.en") -> List[Segment]:
    """
    Transcribe an audio file using Whisper.
    model_name: "tiny.en", "base.en", "medium.en" — larger = slower but better
    """
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path), language="en", fp16=False)
    return [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
        for seg in result["segments"]
    ]
```

---

### `training/chunker.py`

```python
"""
Splits a transcript (list of timed segments) into knowledge chunks.
Each chunk is ~300 words, contains metadata about its source position.
Attempts to detect the AutoCAD tool/command being discussed.
"""
from __future__ import annotations

import re
from typing import List, TypedDict

# Common AutoCAD command names — used to tag chunks
_AUTOCAD_COMMANDS = {
    "LINE", "CIRCLE", "ARC", "RECTANGLE", "RECTANG", "TRIM", "EXTEND",
    "OFFSET", "MIRROR", "COPY", "MOVE", "ROTATE", "SCALE", "STRETCH",
    "FILLET", "CHAMFER", "HATCH", "DIMENSION", "DIM", "BLOCK", "INSERT",
    "LAYER", "PROPERTIES", "EXPLODE", "PEDIT", "SPLINE", "ELLIPSE",
    "POLYGON", "XREF", "PLOT", "ARRAY", "ZOOM", "PAN", "OSNAP",
}

_CHUNK_WORD_LIMIT = 300
_CHUNK_OVERLAP_WORDS = 30  # overlap between adjacent chunks for context continuity


class Chunk(TypedDict):
    text: str
    source_video: str
    timestamp_start: float
    timestamp_end: float
    active_tool_hint: str   # detected AutoCAD command, or "general"
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
    buffer_start = 0.0
    buffer_end = 0.0

    for seg in segments:
        words = seg["text"].split()
        if not buffer_words:
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
            # Overlap: keep last N words for context continuity
            buffer_words = buffer_words[-_CHUNK_OVERLAP_WORDS:]
            buffer_start = buffer_end

    # Flush remaining words as final chunk
    if buffer_words:
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

    return chunks
```

---

### `training/ingest.py` (CLI entrypoint)

```python
"""
CLI: python -m app.training.ingest --video path/to/tutorial.mp4 [--model base.en]

Processes a video file end-to-end:
  1. Extract audio with FFmpeg
  2. Transcribe with Whisper
  3. Chunk the transcript
  4. Embed each chunk with sentence-transformers
  5. Insert into pgvector embeddings table
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Allow running as: python -m app.training.ingest
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.db.postgres import create_pool
from app.db.crud import insert_embedding
from app.services.embedder_service import embed_text
from app.training.video_extractor import extract_audio
from app.training.transcriber import transcribe
from app.training.chunker import make_chunks


async def ingest_video(video_path: str, whisper_model: str) -> None:
    video_name = Path(video_path).stem
    print(f"[1/5] Extracting audio from {video_name}...")
    audio_path = extract_audio(video_path)

    try:
        print(f"[2/5] Transcribing with Whisper ({whisper_model})...")
        segments = transcribe(audio_path, model_name=whisper_model)
        print(f"      Got {len(segments)} segments")

        print("[3/5] Chunking transcript...")
        chunks = make_chunks(segments, source_video=video_name)
        print(f"      Created {len(chunks)} chunks")

        print("[4/5] Embedding and inserting chunks into pgvector...")
        pool = await create_pool()
        inserted = 0
        for i, chunk in enumerate(chunks, 1):
            vector = embed_text(chunk["text"])
            metadata = {
                "source_video": chunk["source_video"],
                "timestamp_start": chunk["timestamp_start"],
                "timestamp_end": chunk["timestamp_end"],
                "active_tool_hint": chunk["active_tool_hint"],
                "tags": chunk["tags"],
            }
            await insert_embedding(pool, chunk["text"], vector, metadata)
            inserted += 1
            if i % 10 == 0:
                print(f"      {i}/{len(chunks)} inserted...")

        await pool.close()
        print(f"[5/5] Done. Inserted {inserted} embeddings for '{video_name}'.")

    finally:
        os.unlink(audio_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a tutorial video into pgvector.")
    parser.add_argument("--video", required=True, help="Path to the .mp4 tutorial video")
    parser.add_argument("--model", default="base.en", help="Whisper model (tiny.en/base.en/medium.en)")
    args = parser.parse_args()
    asyncio.run(ingest_video(args.video, args.model))


if __name__ == "__main__":
    main()
```

---

## Outside VS Code — Run the Ingest Pipeline

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
.venv\Scripts\Activate.ps1

# Make sure .env is loaded
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_USER = "trainerai"
$env:POSTGRES_PASSWORD = "trainerai_pass"
$env:POSTGRES_DB = "trainerai_db"

# Run ingest for a video
python -m app.training.ingest --video ..\training_videos\autocad_basics_lines.mp4 --model base.en
```

Expected output:

```
[1/5] Extracting audio from autocad_basics_lines...
[2/5] Transcribing with Whisper (base.en)...
      Got 312 segments
[3/5] Chunking transcript...
      Created 18 chunks
[4/5] Embedding and inserting chunks into pgvector...
      10/18 inserted...
[5/5] Done. Inserted 18 embeddings for 'autocad_basics_lines'.
```

---

## Outside VS Code — Verify the Data

```powershell
docker exec -it trainerai_postgres psql -U trainerai -d trainerai_db -c "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM embeddings;"
```

You should see a non-zero count of rows.

Test that the RAG service finds relevant docs by querying the similarity endpoint:

```powershell
$body = @{
    query_text = "how to draw a line in AutoCAD"
    top_k = 4
    threshold = 0.5
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8000/db/embeddings/query -Body $body -ContentType "application/json"
```

---

## Notes on Video Quality

- **Clear narration** dramatically improves transcription accuracy. Avoid videos where the instructor only types silently.
- If the video has subtitles embedded (`.srt` / `.vtt`), use those instead of Whisper for perfect text.
- For videos with complex technical vocabulary, `medium.en` transcription model is worth the extra time (3–5x slower than `base.en` but fewer command-name mistakes).
- Process 5–10 hours of tutorial video to get a useful knowledge base.

---

## Acceptance Criteria

- [ ] `python -m app.training.ingest --video <file>` completes without errors
- [ ] `embeddings` table has rows after ingest (`SELECT COUNT(*) FROM embeddings`)
- [ ] `GET /db/embeddings/query` with a relevant AutoCAD query returns top-k docs with similarity > 0.5
- [ ] Retrieved docs contain recognisable AutoCAD workflow steps
