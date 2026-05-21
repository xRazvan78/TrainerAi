"""
CLI: python -m app.training.ingest --video path/to/tutorial.mp4
     python -m app.training.ingest --videos-dir path/to/folder/ --dry-run

Processes video(s) end-to-end:
  1. Extract audio with FFmpeg
  2. Transcribe with Whisper (or load sibling .srt if available)
  3. Chunk the transcript
  4. Batch-embed all chunks with sentence-transformers
  5. Upsert into pgvector embeddings table
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.db.postgres import create_pool
from app.db.crud import create_embedding
from app.services.embedder_service import embed_texts
from app.training.video_extractor import extract_audio
from app.training.transcriber import transcribe
from app.training.chunker import make_chunks


async def ingest_video(video_path: Path, whisper_model: str, dry_run: bool) -> int:
    """Ingest one video. Returns number of chunks processed."""
    video_name = video_path.stem
    print(f"\n=== {video_name} ===")

    t0 = time.perf_counter()
    audio_path = None
    try:
        print("[1/5] Extracting audio...")
        audio_path = extract_audio(video_path)

        print(f"[2/5] Transcribing with Whisper ({whisper_model})...")
        segments = transcribe(audio_path, model_name=whisper_model, video_path=video_path)
        print(f"      Got {len(segments)} segments")

        print("[3/5] Chunking transcript...")
        chunks = make_chunks(segments, source_video=video_name)
        print(f"      Created {len(chunks)} chunks")

        if not chunks:
            print("      No chunks produced — skipping.")
            return 0

        if dry_run:
            tool_dist: dict[str, int] = {}
            for c in chunks:
                tool_dist[c["active_tool_hint"]] = tool_dist.get(c["active_tool_hint"], 0) + 1
            print(f"      [dry-run] Tool-hint distribution: {tool_dist}")
            print(f"      [dry-run] Skipping embedding + DB writes.")
            return len(chunks)

        word_count = sum(len(c["text"].split()) for c in chunks)
        print(f"[4/5] Encoding {len(chunks)} chunks ({word_count} words)...")
        vectors = embed_texts([c["text"] for c in chunks])

        print("[5/5] Inserting into pgvector...")
        pool = await create_pool()
        try:
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                doc_id = f"{video_name}-{i:04d}"
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
                    embedding=vector,
                    metadata=metadata,
                )
        finally:
            await pool.close()

        elapsed = time.perf_counter() - t0
        print(f"      Done. {len(chunks)} rows upserted in {elapsed:.1f}s.")
        return len(chunks)

    finally:
        if audio_path and Path(audio_path).exists():
            os.unlink(audio_path)


async def ingest_directory(videos_dir: Path, whisper_model: str, dry_run: bool) -> None:
    mp4_files = sorted(
        f for ext in ("*.mp4", "*.mkv", "*.webm") for f in videos_dir.glob(ext)
    )
    if not mp4_files:
        print(f"No video files found in {videos_dir}")
        return
    print(f"Found {len(mp4_files)} video(s) in {videos_dir}")
    total = 0
    for video_path in mp4_files:
        total += await ingest_video(video_path, whisper_model, dry_run)
    print(f"\nAll done. {total} chunks processed across {len(mp4_files)} video(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest AutoCAD tutorial video(s) into pgvector.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", help="Path to a single .mp4 tutorial video.")
    group.add_argument("--videos-dir", help="Process every .mp4 in this directory.")
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
    args = parser.parse_args()

    if args.video:
        asyncio.run(ingest_video(Path(args.video), args.whisper_model, args.dry_run))
    else:
        asyncio.run(ingest_directory(Path(args.videos_dir), args.whisper_model, args.dry_run))


if __name__ == "__main__":
    main()
