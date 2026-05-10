# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TrainerAI is an AI-powered AutoCAD training assistant that runs as a transparent always-on-top overlay on Windows. It captures the screen, detects UI elements (YOLOv8 + EasyOCR), retrieves relevant documentation from a vector database (RAG), and generates context-aware guidance using a locally-hosted Qwen LLM.

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

The Qwen LLM is expected at `http://localhost:12434/engines/llama.cpp/v1` (Docker Desktop Model Runner, OpenAI-compatible) using model `ai/qwen3.5:35B-A3B-Q4_K_M`. Phase C is the integration milestone; the backend does not call it yet.

## Architecture

### Backend (`trainerAI_backend/app/`)

**Entry point:** `main.py` — `create_app()` registers routers and a `lifespan` that opens/closes the asyncpg pool. Health check at `GET /health`.

**Routers:**

- `command.py` → `POST /api/command` — async ingestion (202 Accepted); the heavy work runs in a FastAPI background task via `command_pipeline_service`.
- `perception.py` → `POST /api/perception/state` — YOLO/OCR perception state persistence.
- `db_crud.py` — CRUD endpoints for `sessions`, `embeddings`, `training_examples`.

**Services (business logic):**

- `command_pipeline_service.py` — orchestrates the per-command flow: context assembly → RAG retrieval → feedback log entry. This is the central seam; new pipeline steps plug in here.
- `session_state_service.py` — in-memory action log, active tool, command sequences keyed by session.
- `rag_service.py` — pgvector cosine-similarity search; tuned by `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `RAG_TOKEN_BUDGET`.
- `embedder_service.py` — sentence-transformers `all-MiniLM-L6-v2`, 384-dim, normalized; the model is lazy-loaded once via `lru_cache` and reused for the process lifetime.
- `feedback_logger_service.py` — persists `training_examples` rows for downstream model training.

**Database (`app/db/`):**

- `postgres.py` — async pool (asyncpg + SQLAlchemy async engine), wired into the FastAPI app state by lifespan.
- `schema.py` — DDL for `sessions`, `embeddings` (vector(384)), `training_examples`, `perception_states`. The 384 dimension is hard-coded to match the embedder; changing the embed model means changing both.
- `crud.py` — ~20 async data-access helpers used by routers and services.

### Frontend (`trainerAI_overlay/`)

- `src/main.rs` + `src/renderer/` — Dioxus UI (transparent dark overlay, ~320 px wide, RGBA backgrounds).
- `src-tauri/src/commands.rs` + `lib.rs` — Tauri commands for OS integration (always-on-top, screen capture). The Tauri app embeds the Dioxus build.

### Agent Architecture (`.github/agents/`)

Three-tier specification used as design docs (not code):

1. **Conductor** — master orchestrator: Planning → Implementation → Review → Commit lifecycle.
2. **Core agents** — Perception, Context, Guidance, Feedback (domain owners).
3. **Subagents** — single-responsibility units (Frame-diff, YOLOv8, EasyOCR, RAG-Retrieval, Prompt-Builder, Qwen-Interface, Step-Validator, Outcome-Tracker, Data-Logger, etc.).

Target runtime pipeline (per screen capture, 200–500 ms cadence):

```
Screen capture → Frame diff → YOLOv8 + EasyOCR (parallel)
→ Session state update → RAG retrieval + Error detection (parallel)
→ Prompt assembly → Qwen inference → Validate
→ Stream guidance via WebSocket → Outcome tracking + Data logging (async)
```

Most of this pipeline is not yet wired end-to-end — see "Development Status" below for what exists today.

## Development Status

Tracked in `specs/` (per-phase specs) and `plans/` (per-phase completion reports). Current branch is `feature/phase-b`.

- ✅ Phase A: PostgreSQL + pgvector schema, FastAPI CRUD, command ingestion pipeline, RAG service, perception ingestion, feedback logging, Docker infra.
- ✅ Phase B: Real sentence-transformers embeddings (`all-MiniLM-L6-v2`, 384-dim) replacing the earlier SHA-256 mock — implemented on this branch.
- ⬜ Phase C: Qwen LLM integration + WebSocket streaming.
- ⬜ Phases D–G: video training pipeline, screen capture, full pipeline wiring, AutoCAD-specific detection.

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
