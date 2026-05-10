# D.3 — Training module (`app/training/`)

**Depends on:** D.1 (CRUD upsert + `embed_texts`), D.2 (FFmpeg + Whisper installed)
**Blocks:** D.4 verification, D.5
**Estimated effort:** 4–6 h

## Goal

Implement the four-stage video → embedding pipeline as a runnable CLI under `trainerAI_backend/app/training/`. The CLI takes one `.mp4` per invocation and writes chunks into the `embeddings` table with full metadata.

## Module layout

```
trainerAI_backend/app/training/
    __init__.py            # empty
    video_extractor.py     # ffmpeg → 16 kHz mono WAV
    transcriber.py         # WAV → timed segments (Whisper or .srt)
    chunker.py             # segments → ~300-word chunks with metadata
    ingest.py              # CLI: orchestrates the four stages above
```

The original spec in `specs/phase-D-video-training-pipeline.md` provides full code blocks for each file. Take those almost verbatim with the modifications below.

## File-by-file specifics

### `video_extractor.py`

Use the spec verbatim. One refinement: log the elapsed time so `ingest.py` can print per-stage timings.

### `transcriber.py`

Take the spec verbatim, then add an `.srt` short-circuit at the top of `transcribe()`:

```python
from pathlib import Path

def _try_load_srt(audio_path: Path) -> List[Segment] | None:
    """If a sibling .srt or .vtt exists for the original video, parse it
    instead of running Whisper. Returns None when no subtitles are present."""
    # audio_path is the temporary WAV; the caller passes the original video stem
    # via a separate argument, OR we can probe for ``<wav_dir>/../<stem>.srt``.
    # Recommended: pass the original video path through to transcribe(),
    # not just the WAV path.
    ...
```

This pays off massively for D.4 where `yt-dlp` downloads auto-captions: parsing an existing SRT is essentially free vs. ~5–20 min of Whisper time per video.

If implementing SRT parsing, use `pysrt` (single-file dependency, MIT) or write a 30-line parser — the format is trivial. Map each SRT cue to `{"start": float_seconds, "end": float_seconds, "text": cue.text}`.

### `chunker.py`

Use the spec verbatim. The `_AUTOCAD_COMMANDS` set is intentionally small; expanding it is a Phase G concern.

One thing to watch: the chunker overlap logic resets `buffer_start = buffer_end` after a chunk, which means the overlap text inherits the next segment's start time. That is correct (we want the timestamp of *the displayed text*, not the moment the overlap began). Do not change it.

### `ingest.py` — the four corrections

This is where the original spec diverges from reality. Take the spec's `ingest.py` and apply these changes:

1. **Use `create_embedding`, not `insert_embedding`:**

```python
from app.db.crud import create_embedding
```

2. **Generate deterministic `doc_id`s** so re-running the CLI on the same video upserts rather than duplicates:

```python
doc_id = f"{video_name}-{i:04d}"
```

3. **Pass `source` and `metadata` explicitly:**

```python
metadata = {
    "source_video": chunk["source_video"],
    "timestamp_start": chunk["timestamp_start"],
    "timestamp_end": chunk["timestamp_end"],
    "active_tool_hint": chunk["active_tool_hint"],
    "tags": chunk["tags"],
}
await create_embedding(
    pool=pool,
    doc_id=doc_id,
    source=f"video:{video_name}",
    content=chunk["text"],
    embedding=vectors[i],
    metadata=metadata,
)
```

4. **Batch-encode all chunks before the insert loop** (uses `embed_texts` from D.1):

```python
from app.services.embedder_service import embed_texts

print(f"[4/5] Encoding {len(chunks)} chunks ({sum(len(c['text'].split()) for c in chunks)} words)...")
vectors = embed_texts([c["text"] for c in chunks])  # one model.encode call

print("[5/5] Inserting into pgvector...")
pool = await create_pool()
try:
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        ...
finally:
    await pool.close()
```

This brings ingest time for a 30-min tutorial from "transcription dominates, embedding negligible" — the embedding loop in the spec was already fast, but batching cleans up the code path and avoids per-chunk overhead.

### `ingest.py` — recommended CLI surface

Beyond the spec's `--video` and `--model`, add:

```python
parser.add_argument(
    "--videos-dir",
    help="Process every .mp4 in this directory. Mutually exclusive with --video.",
)
parser.add_argument(
    "--whisper-model",
    default="base.en",
    choices=["tiny.en", "base.en", "small.en", "medium.en"],
)
parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Run extraction + transcription + chunking but skip DB writes.",
)
```

The `--videos-dir` mode is what D.4 will use to ingest the whole starter corpus in one command.

## Tests to add

Unit-level tests for the pure-Python parts (no FFmpeg / Whisper / DB needed):

- `tests/test_chunker.py` — feed a synthetic list of segments, assert chunk count, assert word-limit honoured, assert overlap, assert tool-hint detection on a "FILLET" segment.
- `tests/test_ingest_cli.py` — invoke the argparse parser with various flag combinations; assert it rejects `--video` and `--videos-dir` together.

Integration tests for `video_extractor` and `transcriber` are deferred — they need real binaries on PATH. Mark them with `@pytest.mark.integration` and skip in CI.

## Acceptance

- [ ] `python -m app.training.ingest --video <file.mp4> --dry-run` prints chunk count and tool-hint distribution without touching the DB.
- [ ] `python -m app.training.ingest --video <file.mp4>` completes and inserts N rows.
- [ ] Re-running the same command leaves the row count unchanged (upsert verified).
- [ ] `SELECT metadata->>'source_video' FROM embeddings LIMIT 5;` returns the video stem for new rows.
- [ ] `SELECT metadata->>'active_tool_hint', COUNT(*) FROM embeddings GROUP BY 1;` shows a sensible tool-hint distribution (mostly "general" + a few command-specific tags).
- [ ] `pytest tests/test_chunker.py tests/test_ingest_cli.py` green.
