# Phase D — Video Training Pipeline (Execution Plan)

This folder breaks Phase D (`specs/phase-D-video-training-pipeline.md`) into six sequential sub-phases, each in its own file. The original spec remains the design reference; this folder is the runbook for the dev team.

## Why this exists

The `embeddings` table is empty. Until it contains real AutoCAD knowledge chunks, the RAG service returns nothing useful, and the upcoming Phase C (Qwen + WebSocket) would only ever produce ungrounded LLM output. This phase fills the gap end-to-end: tutorial videos → transcripts → chunks → 384-dim embeddings → pgvector rows → meaningful retrieval.

## Two corrections to the original spec

The dev team should be aware of these before starting — they change a couple of code blocks in `phase-D-video-training-pipeline.md`:

1. **`insert_embedding(pool, text, vector, metadata)` does not exist.** The actual helper is `app.db.crud.create_embedding(pool, doc_id, source, content, embedding)` at `trainerAI_backend/app/db/crud.py:167`. Sub-phase **D.1** extends it with a `metadata` parameter and adds upsert semantics.
2. **The `embeddings` table has no `metadata` column** (`app/db/schema.py:21`). Sub-phase **D.1** adds it via `ALTER TABLE … ADD COLUMN IF NOT EXISTS`.

## Sub-phase index

| # | File | Title | Owner suggestion | Blocks |
|---|---|---|---|---|
| D.1 | [01-schema-migration.md](./01-schema-migration.md) | Schema + CRUD changes (`metadata` column, upsert, batched embedder helper) | Backend dev | D.3, D.5 |
| D.2 | [02-environment-setup.md](./02-environment-setup.md) | Local tooling (FFmpeg, Whisper) + `requirements.txt` updates | Any dev | D.3, D.4 |
| D.3 | [03-training-module.md](./03-training-module.md) | New `app/training/` package (extractor, transcriber, chunker, ingest CLI) | Backend dev | D.4, D.5 |
| D.4 | [04-video-corpus-sourcing.md](./04-video-corpus-sourcing.md) | Source 5–8 h of starter tutorials, organize `training_videos/` | Anyone | D.5, D.6 |
| D.5 | [05-rag-evaluation-harness.md](./05-rag-evaluation-harness.md) | `scripts/eval_rag.py` + curated query set | Backend dev | D.6 |
| D.6 | [06-verification-acceptance.md](./06-verification-acceptance.md) | End-to-end verification + acceptance checklist | Whoever finishes last | — |

## Dependency graph

```
D.1 ──┬──► D.3 ──┬──► D.5 ──► D.6
      │         │
D.2 ──┴──► D.4 ─┘
```

D.1 and D.2 are independent and can start in parallel. D.3 needs both. D.4 (video downloads) only needs D.2 (yt-dlp/ffmpeg installed) and can run concurrently with D.3. D.5 needs D.3's `create_embedding` upsert plus D.4's videos so it has actual data to evaluate against.

## Out of scope for Phase D

- Frame OCR captions via EasyOCR — explicitly deferred to Phase G in the original spec.
- Re-embedding when the embedding model changes — assumed not to happen during Phase D.
- Multi-language transcripts — English-only for the starter corpus.
- Any overlay or LLM wiring — that's Phase C / Phase F.

## Definition of done for the whole phase

All acceptance items in [06-verification-acceptance.md](./06-verification-acceptance.md) are checked, `pytest` is green, and the RAG eval harness reports ≥70% top-1 video-source match across the curated query set.
