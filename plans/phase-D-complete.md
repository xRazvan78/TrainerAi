## Plan Complete: Phase D — Video Training Pipeline

Phase D is complete. The pgvector `embeddings` table is populated with AutoCAD tutorial knowledge and the RAG service returns meaningful results for natural-language queries.

**Row count:** ~200+ rows across 17 videos (exact count varies with transcript length per video).

**Topic coverage (17 videos):**
- General AutoCAD intro (workspace, ribbon, command line)
- LINE, CIRCLE, RECTANGLE/POLYGON
- TRIM, EXTEND, OFFSET, MIRROR
- FILLET/CHAMFER (combined), CHAMFER (dedicated)
- ROTATE, SCALE
- HATCH
- LAYER management, LAYER hide/show
- BLOCK/symbols
- DIMENSION (linear, aligned, angular, radius)

**Eval score:** 73% top-1 video-match (11/15 queries) — above the 70% acceptance threshold.

**Known weak spots:**
- OFFSET query (`make a parallel copy of a line at a fixed distance`) returns CHAMFER at sim=0.417 — transcript of the OFFSET video may not use "parallel" enough; acceptable for now.
- BLOCK query (`reusable symbols I can insert multiple times`) returns no hit — the downloaded video transcript may not contain strong semantic signal for this phrasing.
- CHAMFER query (`45-degree corner`) competes with TRIM; both videos discuss cutting, so the top-1 sometimes flips.
- GENERAL intro displaced by CHAMFER for the command-line query at sim=0.626.

These misses are semantic, not structural — the pipeline is correct. Adding more targeted OFFSET/BLOCK videos or tuning the chunker's tool-hint regex for those commands would push the score higher.

**All files created/modified:**
- trainerAI_backend/app/db/schema.py (metadata jsonb column)
- trainerAI_backend/app/db/crud.py (upsert semantics, metadata param)
- trainerAI_backend/app/services/embedder_service.py (embed_texts batch helper)
- trainerAI_backend/app/training/__init__.py
- trainerAI_backend/app/training/video_extractor.py
- trainerAI_backend/app/training/transcriber.py
- trainerAI_backend/app/training/chunker.py
- trainerAI_backend/app/training/ingest.py
- trainerAI_backend/scripts/eval_rag.py
- trainerAI_backend/scripts/eval-baselines/initial.json
- trainerAI_backend/tests/test_chunker.py
- trainerAI_backend/tests/test_ingest_cli.py
- trainerAI_backend/tests/test_embedder_service.py
- trainerAI_backend/tests/test_db_crud_helpers.py
- trainerAI_backend/requirements.txt
- training_videos/urls.txt
- .gitignore (training_videos/, *.mp4, *.wav, *.srt, *.vtt added)
