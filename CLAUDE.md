# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TrainerAI is an AI-powered AutoCAD training assistant that runs as a transparent always-on-top overlay on Windows. It captures the screen via Windows Graphics Capture (WGC), detects UI elements (YOLOv8 + EasyOCR), retrieves relevant documentation from a pgvector RAG store, and streams context-aware guidance through a WebSocket using the Mistral AI API.

The repo is a monorepo with two deployable units (`trainerAI_backend/` and `trainerAI_overlay/`) plus design artifacts (`.github/agents/`, `specs/`, `plans/`).

## Commands

### Backend (run from `trainerAI_backend/`)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload      # dev server
pytest tests/                      # full test suite
pytest tests/test_command_api.py -v   # single test file
pytest tests/test_rag_service.py::test_name -v   # single test
```

### Frontend (run from `trainerAI_overlay/`)

```bash
dx serve --port 1420       # Dioxus frontend dev server (UI only)
cargo tauri dev            # full Tauri dev build (overlay + Dioxus)
dx build                   # production frontend bundle
cargo tauri build          # production overlay binary
```

### Infrastructure

```bash
docker compose up -d       # starts the pgvector/pgvector:pg18 container on :5432
```

## Environment Setup

Copy `.env.example` to `.env` at the repo root — the backend reads `.env` from its CWD when launched. Variables drive `app/config.py` (pydantic-settings); `Settings.database_url` is derived from `POSTGRES_*` unless `DATABASE_URL` is set explicitly.

PostgreSQL 18+ with `pgvector` is required. The bundled `docker-compose.yml` provides this; schema DDL is applied on FastAPI startup via `app/db/schema.py` — there is no separate migration tool.

The LLM is **Mistral AI** (cloud API), called via `app/services/llm_service.py`. Set `LLM_API_KEY` to your Mistral API key. `LLM_BASE_URL` defaults to `https://api.mistral.ai/v1` and `LLM_MODEL` defaults to `mistral-small-latest`. The previous Qwen/Docker Model Runner approach has been replaced.

The overlay connects to the backend WebSocket at `BACKEND_WS_URL` (must be `ws://localhost:…`) using `SESSION_ID`. Both are set in the Tauri app config or environment.

## Architecture

### Backend (`trainerAI_backend/app/`)

**Entry point:** `main.py` — `create_app()` registers routers and a `lifespan` that opens/closes the asyncpg pool. Health check at `GET /health`.

**Routers:**

- `command.py` → `POST /api/command` — async ingestion (202 Accepted); heavy work runs in a FastAPI background task via `command_pipeline_service`.
- `perception.py` → `POST /api/perception/state` — receives a base64 JPEG frame, runs `perception_service.analyse_frame()`, persists results, and may trigger guidance via `guidance_trigger_service`.
- `guidance.py` → `WS /api/guidance/ws/{session_id}` — WebSocket endpoint; sends keepalive pings; guidance tokens are pushed by `ws_broadcaster`.
- `db_crud.py` — CRUD endpoints for `sessions`, `embeddings`, `training_examples`.

**Services (business logic):**

- `command_pipeline_service.py` — orchestrates per-command flow: context assembly → RAG retrieval → LLM call → feedback log. Central seam; new pipeline steps plug in here.
- `guidance_trigger_service.py` — per-session drop-on-busy lock; triggers guidance when the active tool changes. Prevents concurrent pipeline runs per session.
- `llm_service.py` — streams tokens from Mistral AI (`/v1/chat/completions`). `stream_guidance()` yields tokens; `generate_guidance()` collects them. System prompt is fixed: 2–4 sentence AutoCAD guidance, no preamble.
- `ws_broadcaster.py` — `broadcast_token()` / `broadcast_done()` push LLM tokens to the registered WebSocket for a session. Keepalive ping every 20 s.
- `perception_service.py` — `analyse_frame()` decodes a base64 JPEG, runs the OCR heuristic (bottom command-line band), then YOLOv8 (if weights exist at `app/models_weights/autocad_yolov8.pt`). YOLO detections override the heuristic for `command_line`. EasyOCR enhances text contrast before reading. Saves debug PNGs on first frame.
- `session_state_service.py` — in-memory action log, active tool, command sequences keyed by session.
- `rag_service.py` — pgvector cosine-similarity search; tuned by `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `RAG_TOKEN_BUDGET`.
- `embedder_service.py` — sentence-transformers `all-MiniLM-L6-v2`, 384-dim, normalized; lazy-loaded once via `lru_cache`.
- `feedback_logger_service.py` — persists `training_examples` rows for downstream model training.

**Training pipeline (`app/training/`):**

- `ingest.py` — CLI (`python -m app.training.ingest --video <file>`): extract audio (FFmpeg) → transcribe (Whisper) → chunk → embed → upsert into pgvector. Supports `--dry-run`.
- `transcriber.py` — wraps `openai-whisper`; loads a `.srt` sidecar if available to skip re-transcription.
- `chunker.py` — segments transcript into overlapping chunks with `active_tool_hint` and `tags` metadata.
- `video_extractor.py` — calls `ffmpeg` to strip audio to a temp `.wav`.

**Database (`app/db/`):**

- `postgres.py` — async pool (asyncpg), wired into FastAPI app state by lifespan.
- `schema.py` — DDL for `sessions`, `embeddings` (vector(384)), `training_examples`, `perception_states`. The 384 dimension is hard-coded; changing the embed model requires updating both.
- `crud.py` — ~20 async data-access helpers.

### Frontend (`trainerAI_overlay/`)

- `src/main.rs` + `src/renderer/app.rs` — Dioxus UI (transparent dark overlay). The UI is currently a minimal placeholder; guidance display via WebSocket events is wired in Tauri but the Dioxus side is not yet fully built out.
- `src-tauri/src/commands.rs` — Tauri commands for OS integration (always-on-top, screen capture trigger).
- `src-tauri/src/capture.rs` — Windows Graphics Capture (WGC) pipeline: `find_autocad_hwnd()` enumerates windows, `capture_window_frame()` grabs one BGRA frame, converts to JPEG+base64. Includes perceptual hashing (`ahash`, `hamming`) for frame-diff filtering.
- `src-tauri/src/ws_client.rs` — connects to `WS /api/guidance/ws/{session_id}` with exponential-backoff reconnect. Emits `guidance-token` and `guidance-ws-status` Tauri events to the Dioxus frontend.

### Agent Architecture (`.github/agents/`)

Three-tier specification used as design docs (not runnable code):

1. **Conductor** — master orchestrator: Planning → Implementation → Review → Commit lifecycle.
2. **Core agents** — Perception, Context, Guidance, Feedback.
3. **Subagents** — Frame-diff, YOLOv8, EasyOCR, RAG-Retrieval, Prompt-Builder, LLM-Interface, Step-Validator, Outcome-Tracker, Data-Logger, etc.

Live runtime pipeline (per screen capture):

```
WGC capture (Tauri) → ahash frame-diff → POST /api/perception/state (base64 JPEG)
→ EasyOCR heuristic + YOLOv8 (parallel if weights present)
→ guidance_trigger_service (tool-change gate, drop-on-busy)
→ command_pipeline_service → RAG retrieval → Mistral stream
→ ws_broadcaster → WS /api/guidance/ws/{session_id}
→ ws_client.rs → guidance-token event → Dioxus overlay
```

## Development Status

Tracked in `specs/` (per-phase specs) and `plans/` (per-phase completion reports). Current branch: `main`.

- ✅ Phase A: PostgreSQL + pgvector schema, FastAPI CRUD, command ingestion pipeline, RAG service, perception ingestion, feedback logging, Docker infra.
- ✅ Phase B: Real sentence-transformers embeddings (`all-MiniLM-L6-v2`, 384-dim) replacing SHA-256 mock.
- ✅ Phase C: LLM integration + WebSocket guidance streaming. Originally designed for Qwen; **switched to Mistral AI** (cloud API). `llm_service.py` streams via `/v1/chat/completions`.
- ✅ Phase D: Video training pipeline — `app/training/` (FFmpeg + Whisper + chunker + embedder → pgvector).
- ✅ Phase E: WGC screen capture in Tauri (`capture.rs`) — ahash frame-diff, JPEG/base64, posts to backend.
- ✅ Phase F: Overlay WebSocket client (`ws_client.rs`) wired to backend guidance stream; Tauri events bridge to Dioxus.
- ✅ Phase G: AutoCAD-specific perception — EasyOCR heuristic for command-line band + optional YOLOv8 (weights at `app/models_weights/autocad_yolov8.pt`).
- ✅ Phase H: Perception-driven guidance trigger — `guidance_trigger_service.py` gates LLM calls on tool-change, drop-on-busy semantics.
- ✅ Overlay UI: Dioxus frontend displays streamed guidance tokens in the transparent overlay. The full end-to-end pipeline is working — selecting a command in AutoCAD triggers detection, RAG retrieval, Mistral inference, and guidance appears in the overlay.

When picking up new work, read the relevant `specs/phase-*.md` first — they encode the intended scope and acceptance criteria for each phase.

---

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
