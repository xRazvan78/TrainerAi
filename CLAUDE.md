# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TrainerAI is an AI-powered AutoCAD training assistant that runs as a transparent always-on-top overlay on Windows. It captures the screen, detects UI elements (YOLOv8 + EasyOCR), retrieves relevant documentation from a vector database (RAG), and generates context-aware guidance using a locally-hosted Qwen LLM.

## Repository Layout

```
trainerAI_backend/    # FastAPI backend (Python)
trainerAI_overlay/    # Tauri + Dioxus desktop overlay (Rust)
.github/agents/       # AI agent specifications (Conductor + 4 core + 11 subagents)
specs/                # Implementation roadmap and phase specifications
plans/                # Phase completion reports
```

## Commands

### Backend

```bash
cd trainerAI_backend

# Install dependencies
pip install -r requirements.txt

# Run dev server (from trainerAI_backend/)
uvicorn app.main:app --reload

# Run tests
pytest tests/

# Run a single test file
pytest tests/test_command_api.py -v
```

### Frontend (Tauri + Dioxus)

```bash
cd trainerAI_overlay

# Development
dx serve --port 1420       # Dioxus frontend dev server
cargo tauri dev            # Full Tauri dev build

# Production
dx build
cargo tauri build
```

## Environment Setup

Copy `.env.example` to `.env` in `trainerAI_backend/`:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
POSTGRES_DB=trainerAI_database
```

PostgreSQL 18+ with the `pgvector` extension is required. The schema is auto-bootstrapped on FastAPI startup via `app/db/schema.py`.

The Qwen LLM runs locally via Docker Desktop Model Runner at `http://localhost:11434` using model `qwen3.5:35B-A3B-Q4_K_M`.

## Architecture

### Backend (`trainerAI_backend/app/`)

**Entry point:** `main.py` — FastAPI app with lifespan context manager that initializes the DB pool and registers routers.

**Routers:**

- `POST /api/command` — async command ingestion (202 Accepted, background task)
- `POST /api/perception/state` — YOLO/OCR perception state persistence
- `db_crud` — CRUD endpoints for sessions, embeddings, training examples

**Services (business logic):**

- `command_pipeline_service.py` — orchestrates the full pipeline: context assembly → RAG → feedback logging
- `session_state_service.py` — maintains action log, active tool, command sequences
- `rag_service.py` — vector semantic search using pgvector cosine similarity
- `embedder_service.py` — text-to-embedding conversion (**currently a SHA-256 mock**; Phase B replaces with sentence-transformers `all-MiniLM-L6-v2`, 384 dimensions)
- `feedback_logger_service.py` — persists training examples to PostgreSQL

**Database (`db/`):**

- `postgres.py` — async connection pool (asyncpg + SQLAlchemy)
- `schema.py` — DDL definitions; tables: `sessions`, `embeddings`, `training_examples`, `perception_states`
- `crud.py` — async data access layer (~20 operations)

### Frontend (`trainerAI_overlay/`)

- `src/main.rs` — Dioxus UI component; renders a transparent overlay (dark theme, 320px wide, RGBA backgrounds)
- `src-tauri/src/` — Tauri commands for native OS integration (always-on-top window, screen capture)

### Agent Architecture (`.github/agents/`)

Three-tier system used as AI agent guidelines:

1. **Conductor** — master orchestrator managing Planning → Implementation → Review → Commit lifecycle
2. **Core agents** — Perception, Context, Guidance, Feedback (domain owners)
3. **Subagents** — single-responsibility units (frame diff, YOLO inference, OCR, RAG search, prompt building, Qwen interface, etc.)

The pipeline runs on each screen capture (200–500ms cadence):

```
Screen capture → Frame diff → YOLOv8 + EasyOCR (parallel)
→ Session state update → RAG retrieval + Error detection (parallel)
→ Prompt assembly → Qwen inference → Validate
→ Stream guidance via WebSocket → Outcome tracking + Data logging (async)
```

## Current Development Status

6 of 8 phases complete:

- ✅ PostgreSQL + pgvector schema, FastAPI CRUD, command ingestion pipeline, RAG service (mock embedder), perception ingestion, feedback logging
- ⬜ **Phase B**: Real embeddings (replace SHA-256 mock with sentence-transformers)
- ⬜ **Phase C**: Qwen LLM integration + WebSocket streaming
- Phases D–G: video training pipeline, screen capture, full pipeline wiring, AutoCAD-specific detection
