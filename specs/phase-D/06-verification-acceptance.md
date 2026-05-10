# D.6 — Verification & acceptance

**Depends on:** D.1, D.2, D.3, D.4, D.5
**Blocks:** Phase C (the next phase doesn't *technically* block on this, but starting Phase C without Phase D in place produces ungrounded LLM output)
**Estimated effort:** 30–60 min

## Goal

A single, repeatable end-to-end check that proves Phase D's work hangs together: schema is migrated, ingest CLI runs cleanly on the full starter corpus, the RAG service surfaces relevant chunks for natural-language queries, and the existing test suite is still green.

## End-to-end run

Do this on a freshly-restarted backend and a clean (or rebuilt) Postgres container, so the checks aren't masked by stale state.

```powershell
# 1. Bring up infra
cd D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi
docker compose up -d
docker exec -it trainerai_postgres psql -U trainerai -d trainerai_db -c "\d embeddings"

# 2. Restart backend so the schema migration runs
cd trainerAI_backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
# Confirm in another shell:
curl http://localhost:8000/health

# 3. Confirm metadata column exists post-migration
docker exec -it trainerai_postgres psql -U trainerai -d trainerai_db `
  -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='embeddings' ORDER BY ordinal_position;"

# 4. Ingest the corpus
python -m app.training.ingest --videos-dir ..\training_videos --whisper-model base.en

# 5. Spot-check rows
docker exec -it trainerai_postgres psql -U trainerai -d trainerai_db `
  -c "SELECT source, COUNT(*) FROM embeddings GROUP BY source ORDER BY 2 DESC;"

# 6. Idempotency — re-run on one video, count should be unchanged
$before = docker exec trainerai_postgres psql -U trainerai -d trainerai_db -tAc "SELECT COUNT(*) FROM embeddings;"
python -m app.training.ingest --video ..\training_videos\<one-file>.mp4
$after = docker exec trainerai_postgres psql -U trainerai -d trainerai_db -tAc "SELECT COUNT(*) FROM embeddings;"
if ($before -ne $after) { Write-Error "Upsert broken: $before -> $after" }

# 7. RAG quality eval
python scripts/eval_rag.py --json scripts/eval-baselines/initial.json

# 8. Existing test suite — nothing should regress from the schema change
pytest tests/
```

## Final acceptance checklist

Use this as the pull-request checklist for the umbrella Phase D PR (or for the last sub-phase PR if merged piecewise).

### D.1 — schema + CRUD
- [ ] `embeddings.metadata jsonb` column exists with default `'{}'`.
- [ ] `create_embedding(metadata=...)` round-trips JSON.
- [ ] Re-inserting same `doc_id` upserts (single row remains).
- [ ] `embed_texts([...])` returns N × 384-dim vectors.

### D.2 — environment
- [ ] FFmpeg, Whisper, OpenCV available in the venv.
- [ ] `requirements.txt` updated with `openai-whisper`, `opencv-python-headless`.

### D.3 — training module
- [ ] `app/training/{__init__,video_extractor,transcriber,chunker,ingest}.py` exist and import cleanly.
- [ ] `python -m app.training.ingest --video <file> --dry-run` reports chunk count without DB writes.
- [ ] `--videos-dir` mode iterates a folder.
- [ ] `tests/test_chunker.py` and `tests/test_ingest_cli.py` green.

### D.4 — corpus
- [ ] `training_videos/` excluded from git for media files; `urls.txt` committed.
- [ ] At least 10 videos covering the topic checklist in `04-video-corpus-sourcing.md`.
- [ ] At least 60% have sibling `.en.srt` files.

### D.5 — eval harness
- [ ] `scripts/eval_rag.py` runs on a populated DB.
- [ ] Baseline JSON committed under `scripts/eval-baselines/`.
- [ ] Top-1 video-match rate ≥ 70%.

### D.6 — overall
- [ ] `pytest tests/` green.
- [ ] `specs/README.md` "Current State" table updated: Phase D ✅; A and B were already done but the original table still marked them ❌/⚠️ — fix while you're there.
- [ ] One short paragraph added to `plans/` (mirroring the existing `*-complete.md` convention) summarising row count, topic coverage, eval score, and any known weak spots.

## Hand-off to Phase C

Once this list is green, Phase C (Qwen + WebSocket per `specs/phase-C-qwen-llm-integration.md`) can start with confidence that:

- `rag_service.query_similar_embeddings(...)` returns real chunks for AutoCAD queries.
- The chunks include `metadata.source_video` + `timestamp_start`, which the LLM prompt builder can use for citations.
- Re-ingesting or expanding the corpus is a one-command operation, so the LLM's grounding can grow without code changes.
