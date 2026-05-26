# Graph Report - TrainerAi  (2026-05-27)

## Corpus Check
- 106 files · ~55,155 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1160 nodes · 1253 edges · 103 communities (66 shown, 37 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 81 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fed71c7b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]

## God Nodes (most connected - your core abstractions)
1. `Phase G — AutoCAD-Specific Detection` - 14 edges
2. `Phase A — Setup Instructions` - 12 edges
3. `make_chunks()` - 11 edges
4. `Phase E — Screen Capture (Tauri / Windows Graphics Capture)` - 11 edges
5. `Sub-phase C.5 — Verification & Acceptance` - 11 edges
6. `embed_text()` - 10 edges
7. `ingest_video()` - 10 edges
8. `Sub-phase C.1 — Config + Dependencies` - 10 edges
9. `Sub-phase C.2 — LLM Service (Qwen SSE Streaming Client)` - 10 edges
10. `Sub-phase C.3 — WebSocket Router (`/api/guidance/ws/{session_id}`)` - 10 edges

## Surprising Connections (you probably didn't know these)
- `session-state-subagent` --semantically_similar_to--> `session_state_service.py`  [INFERRED] [semantically similar]
  README.md → CLAUDE.md
- `rag-retrieval-subagent` --semantically_similar_to--> `rag_service.py`  [INFERRED] [semantically similar]
  README.md → CLAUDE.md
- `qwen-inference-subagent` --semantically_similar_to--> `llm_service.py Phase C`  [INFERRED] [semantically similar]
  README.md → specs/phase-C-qwen-llm-integration.md
- `Phase F Full Pipeline Connection Spec` --references--> `src/main.rs Dioxus`  [EXTRACTED]
  specs/phase-F-full-pipeline-connection.md → trainerAI_overlay/src/main.rs
- `D.5 RAG Evaluation Harness` --references--> `scripts/eval_rag.py`  [EXTRACTED]
  specs/phase-D/05-rag-evaluation-harness.md → trainerAI_backend/scripts/eval_rag.py

## Hyperedges (group relationships)
- **RAG Retrieval Pipeline** — claudemd_embedder_service, claudemd_pgvector, claudemd_rag_service, claudemd_all_minilm [EXTRACTED 1.00]
- **Command Pipeline Flow** — claudemd_command_router, claudemd_command_pipeline_service, claudemd_rag_service, claudemd_session_state_service, claudemd_feedback_logger_service [EXTRACTED 1.00]
- **Perception Subagent Triad** — readme_frame_diff, readme_yolov8, readme_easyocr [EXTRACTED 1.00]
- **Video-to-Embedding Ingest Pipeline** — video_extractor_py, transcriber_py, chunker_py, ingest_py, embedder_service_py, crud_py [EXTRACTED 1.00]
- **AutoCAD Perception Detection Pipeline** — capture_rs, perception_service_py, yolov8_detection, easyocr_text, session_state_service_py [EXTRACTED 0.95]
- **End-to-End Guidance Flow** — commands_rs, ws_client_rs, dioxus_main_rs, websocket_streaming, rag_service_py [EXTRACTED 0.95]
- **Tauri App Icon Set** — icon_128x128, icon_128x128at2x, icon_32x32, icon_icon, icon_square107, icon_square142, icon_square150, icon_square284, icon_square30, icon_square310, icon_square44, icon_square71, icon_square89, icon_storelogo [EXTRACTED 0.95]

## Communities (103 total, 37 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (52): all-MiniLM-L6-v2, command_pipeline_service.py, command.py Router, app/config.py, db/crud.py, db_crud.py Router, embedder_service.py, feedback_logger_service.py (+44 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (39): EvalQuery, evaluate(), main(), print_report(), Lightweight RAG quality eval — not a pytest, run as:      python scripts/eval_, _make_seg(), test_collect_tags_multiple(), test_detect_tool_fillet() (+31 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (24): _build_user_prompt(), generate_guidance(), LLM service — streams guidance from Docker Desktop Model Runner (Qwen 3.5). Use, stream_guidance(), ahash(), bgra_to_rgba(), capture_window_frame(), CapturedFrame (+16 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (12): BaseModel, PerceptionElement, PerceptionStatePersistedResponse, PerceptionStateRequest, EmbeddingCreate, EmbeddingUpdate, SessionCreate, SessionUpdate (+4 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (31): _affected_rows_from_status(), create_embedding(), create_perception_state(), create_session(), create_training_example(), delete_embedding(), delete_session(), delete_training_example() (+23 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (33): 1. Set up Label Studio, 2. Create a project, 3. Label images, 4. Export and convert, 5. Fine-tune YOLOv8, Acceptance Criteria, Approach: Fine-Tuned YOLOv8 on AutoCAD Screenshots, AutoCAD UI Elements to Detect (+25 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (33): 8a. Backend health, 8b. Database connection, 8c. Qwen model responds, Acceptance Checklist, code:powershell (docker version), code:powershell (cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiec), code:powershell (Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Remo), code:powershell (cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiec) (+25 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (24): run_week2_command_pipeline(), safe_run_week2_command_pipeline(), embed_text(), embed_texts(), _get_model(), Real semantic embedding service using sentence-transformers all-MiniLM-L6-v2. P, Load the model once and keep it in memory for the process lifetime., Embed a single string into a 384-dimensional float vector.     Thread-safe; mod (+16 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (31): Agent file locations, AI Copilot — Agent Orchestra, code:block1 (Screen capture), code:block2 (.github/agents/), `Conductor.agent.md`, `context-agent.agent.md`, Context subagents, `data-logger-subagent.agent.md` (+23 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (30): 1. Install FFmpeg (required by Whisper for audio extraction), 2. Install Whisper and its dependencies, 3. Prepare tutorial videos, Acceptance Criteria, code:block1 (tutorial.mp4), code:powershell (cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiec), code:block11 ([1/5] Extracting audio from autocad_basics_lines...), code:powershell (docker exec -it trainerai_postgres psql -U trainerai -d trai) (+22 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (18): Chunk Overlap Strategy, scripts/eval_rag.py, FFmpeg Audio Extraction, pgvector 384-dim Embeddings, Phase B Implementation Plan, D.1 Schema Migration, D.2 Environment Setup, D.3 Training Module (+10 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (23): 1. Verify Docker Desktop is running, 2. Verify the model is available in Docker Desktop, 3. Verify the pgvector image is available, Acceptance Criteria, code:powershell (docker version), code:powershell (docker model ls), code:powershell (docker pull pgvector/pgvector:pg18), code:yaml (services:) (+15 more)

### Community 12 - "Community 12"
Cohesion: 0.08
Nodes (23): 1. New file: `trainerAI_backend/app/services/llm_service.py`, 2. Update `trainerAI_backend/app/config.py`, 3. New file: `trainerAI_backend/app/routers/guidance.py`, 4. Update `trainerAI_backend/app/services/command_pipeline_service.py`, 5. Register the new router in `trainerAI_backend/app/main.py`, 6. Update `requirements.txt`, Acceptance Criteria, Architecture of This Phase (+15 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (23): Acceptance Criteria, code:block1 (User types "LINE" in AutoCAD), code:powershell (# Install wscat), code:json ({), code:rust (//! WebSocket client that connects to the FastAPI guidance e), code:toml (tokio-tungstenite = { version = "0.24", features = ["native-), code:rust (// After the existing cursor polling thread setup:), code:toml (uuid = { version = "1", features = ["v4"] }) (+15 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (15): get_settings(), Settings, lifespan(), BaseSettings, create_pool(), get_pool_from_request(), shutdown_database(), startup_database() (+7 more)

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (21): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, Agent Architecture (`.github/agents/`), Architecture, Backend (run from `trainerAI_backend/`), Backend (`trainerAI_backend/app/`) (+13 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (21): 1. Smoke test the embedder, 2. Run the full test suite, Acceptance Criteria, code:block1 (sentence-transformers>=3.0.0), code:python ("""), code:python (import time), code:powershell (cd trainerAI_backend), code:powershell (docker exec -it trainerai_postgres psql -U trainerai -d trai) (+13 more)

### Community 17 - "Community 17"
Cohesion: 0.17
Nodes (17): ContextPacketFoundation, SessionSnapshot, build_context_packet_foundation(), _build_next_command_sequence(), _ensure_session_exists(), _extract_active_tool(), _normalize_command_sequence(), update_session_from_command() (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.1
Nodes (20): code:python ("""), code:python (from app.routers.guidance import router as guidance_router), code:python (from fastapi.testclient import TestClient), code:python (import asyncio), Design notes, Edge Cases & Risks, File & Directory Changes, File: `trainerAI_backend/app/routers/guidance.py` (+12 more)

### Community 19 - "Community 19"
Cohesion: 0.1
Nodes (20): 1. Test suite, 2. OpenAPI / docs check, 3. End-to-end smoke test, 4. Idle-keepalive check, 5. Failure-mode check, Acceptance Checklist, code:bash (cd trainerAI_backend), code:bash (uvicorn app.main:app --reload) (+12 more)

### Community 20 - "Community 20"
Cohesion: 0.1
Nodes (20): code:js ((function () {), code:rust (loop {), code:rust (#[derive(serde::Deserialize)]), code:toml (gloo-timers = { version = "0.3", features = ["futures"] }), code:block5 (is_streaming = false, token arrives with done=false →), Edge Cases & Risks, Event listener registration (one-shot, on mount), File & Directory Changes (+12 more)

### Community 21 - "Community 21"
Cohesion: 0.1
Nodes (19): 1. `trainerAI_backend/requirements.txt`, 2. `trainerAI_backend/app/services/embedder_service.py`, 3. `trainerAI_backend/app/services/rag_service.py`, Acceptance Criteria, Background: Why the Current Embedder is Broken, code:python (import hashlib, struct), code:block2 (sentence-transformers >= 3.0.0), code:python (""") (+11 more)

### Community 22 - "Community 22"
Cohesion: 0.1
Nodes (19): Acceptance Criteria, code:powershell (# WGC requires Windows 10 2004+ (build 19041+)), code:powershell (rustup update stable), code:toml (windows = { version = "0.58", features = [), code:rust (//! Windows Graphics Capture (WGC) screen capture module.), code:rust (use std::sync::atomic::{AtomicBool, Ordering};), code:powershell (cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiec), code:powershell (# In a separate terminal with the backend running) (+11 more)

### Community 23 - "Community 23"
Cohesion: 0.1
Nodes (19): code:powershell (Invoke-RestMethod http://localhost:12434/engines/llama.cpp/v), code:powershell (wscat -c ws://localhost:8000/api/guidance/ws/default-session), code:powershell ($body = @{), code:powershell ($env:SESSION_ID     = "default-session"), code:powershell (Invoke-RestMethod "http://localhost:8000/db/perception_state), Edge Cases & Risks, Goals, Implementation Steps (+11 more)

### Community 24 - "Community 24"
Cohesion: 0.17
Nodes (16): Average Hash Frame Diffing, src/main.rs Dioxus, EasyOCR Text Extraction, Label Studio Annotation Tool, perception.py Router, Phase A Setup, Phase D Video Training Pipeline Spec, Phase E Screen Capture Spec (+8 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (17): code:block1 (foundation = await build_context_packet_foundation(...)), code:block2 (foundation = await build_context_packet_foundation(...)), code:python (import httpx), Design notes, Edge Cases & Risks, File & Directory Changes, Goals, Implementation Steps (+9 more)

### Community 26 - "Community 26"
Cohesion: 0.11
Nodes (17): Acceptance, `chunker.py`, code:block1 (trainerAI_backend/app/training/), code:python (from pathlib import Path), code:python (from app.db.crud import create_embedding), code:python (doc_id = f"{video_name}-{i:04d}"), code:python (metadata = {), code:python (from app.services.embedder_service import embed_texts) (+9 more)

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (18): Acceptance, Batch download, Channels worth scraping, code:block1 (training_videos/), code:powershell (mkdir D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Pro), code:powershell (cd D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiec), code:powershell (yt-dlp `), code:block5 (TrainerAi/) (+10 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (18): `ahash` (8×8 average hash), `capture_window_frame`, code:rust (pub struct CapturedFrame {), code:rust (std::fs::write("debug-frame.jpg", &raw_jpeg_bytes).unwrap();), Edge Cases & Risks, File & Directory Changes, `find_autocad_hwnd`, Goals (+10 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (17): Cargo.toml additions, code:rust (#[derive(Clone, serde::Serialize)]), code:toml (tokio-tungstenite = { version = "0.24", features = ["rustls-), code:jsonc ({"type": "token", "content": "..."}   // streaming chunk), code:rust (loop {), Edge Cases & Risks, Envelope parsing, File & Directory Changes (+9 more)

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (17): code:python ("""), code:bash (python -c "import asyncio; from app.services.llm_service imp), code:block3 (data: {"choices":[{"delta":{"content":"Hello"}}]}), Design notes, Edge Cases & Risks, File & Directory Changes, File: `trainerAI_backend/app/services/llm_service.py`, Goals (+9 more)

### Community 31 - "Community 31"
Cohesion: 0.19
Nodes (12): CommandAcceptedResponse, CommandRequest, command_endpoint(), process_command_placeholder(), _utc_now_iso8601(), _command(), _build_command(), _install_fake_crud() (+4 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (15): code:block2 (# DOCKER_MODEL_RUNNER_URL=http://localhost:12434/engines/lla), code:powershell (Invoke-RestMethod -Method Post `), Dependency, Edge Cases & Risks, `.env.example`, File & Directory Changes, Goals, Implementation Steps (+7 more)

### Community 33 - "Community 33"
Cohesion: 0.12
Nodes (16): code:rust (mod ws_client;), code:rust (let app_handle_ws = app.handle().clone();), code:rust (.invoke_handler(tauri::generate_handler![), code:rust (#[tauri::command]), `commands.rs` changes, Edge Cases & Risks, File & Directory Changes, Goals (+8 more)

### Community 34 - "Community 34"
Cohesion: 0.12
Nodes (14): 1. `trainerAI_backend/app/db/schema.py`, 2. `trainerAI_backend/app/db/crud.py`, 3. `trainerAI_backend/app/services/embedder_service.py`, Acceptance, Changes, code:python (# Replace the embeddings CREATE TABLE statement with:), code:python ("""), code:sql (SELECT doc_id, source, content, embedding::text AS embedding) (+6 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (15): Backend Pydantic change, Cargo.toml dependencies to add, code:toml (windows-capture = "1.4"), code:python (frame_hash: str | None = None), code:python (frame_b64: str | None = None), Edge Cases & Risks, File & Directory Changes, Goals (+7 more)

### Community 36 - "Community 36"
Cohesion: 0.12
Nodes (15): code:rust (use std::sync::atomic::{AtomicBool, Ordering};), code:rust (.invoke_handler(tauri::generate_handler![), code:block3 (BACKEND_URL=http://localhost:8000), `commands.rs` — full rewrite, Edge Cases & Risks, File & Directory Changes, Goals, Implementation Steps (+7 more)

### Community 37 - "Community 37"
Cohesion: 0.13
Nodes (14): code:powershell ($env:BACKEND_URL = "http://localhost:8000"), code:powershell (Invoke-RestMethod -Method Post `), code:powershell (Invoke-RestMethod "http://localhost:8000/db/perception_state), code:powershell (docker exec -it trainerai_postgres psql -U trainerai -d trai), Edge Cases & Risks, File & Directory Changes, Goals, Implementation Steps (+6 more)

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (12): code:powershell (# 1. Bring up infra), D.1 — schema + CRUD, D.2 — environment, D.3 — training module, D.4 — corpus, D.5 — eval harness, D.6 — overall, D.6 — Verification & acceptance (+4 more)

### Community 39 - "Community 39"
Cohesion: 0.17
Nodes (11): code:block1 (AutoCAD screen), code:block2 (Phase A (Docker)), code:block3 (TrainerAi/), Current State (as of start of roadmap), Hardware Requirements, Phase Execution Order, Phase Summary, Repository Layout (Target) (+3 more)

### Community 40 - "Community 40"
Cohesion: 0.17
Nodes (11): code:powershell (# FFmpeg — required by Whisper for audio decoding), code:powershell (cd D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiec), code:powershell (python -c "import whisper; whisper.load_model('base.en')"), code:block4 (openai-whisper>=20231117), D.2 — Environment setup, Goal, Python packages, `requirements.txt` updates (+3 more)

### Community 41 - "Community 41"
Cohesion: 0.17
Nodes (11): code:block1 (E.1 (deps + backend model) ──► E.2 (capture module) ──► E.3 ), Context, Definition of done for the whole phase, Out of scope for Phase E, Phase dependency graph, Phase E — Screen Capture (Execution Plan), Reused existing code, Sub-phase index (+3 more)

### Community 42 - "Community 42"
Cohesion: 0.17
Nodes (11): code:block1 (F.1 (deps + ws_client) ──► F.2 (lib.rs + commands.rs wiring)), Context, Definition of done for the whole phase, Out of scope for Phase F, Phase dependency graph, Phase F — Full Pipeline Connection (Execution Plan), Reused existing code, Sub-phase index (+3 more)

### Community 43 - "Community 43"
Cohesion: 0.36
Nodes (8): _build_client(), test_command_ack_then_async_processing_path(), test_command_endpoint_returns_ack_immediately(), test_command_payload_requires_iso_timestamp(), test_command_payload_requires_text_timestamp_session_id(), test_command_payload_requires_timezone_in_timestamp(), test_command_pipeline_without_error_detect_week2_scope(), test_feedback_logger_non_blocking_from_command_ack()

### Community 44 - "Community 44"
Cohesion: 0.2
Nodes (9): Code Review Findings, code:python (_background_tasks: set[asyncio.Task] = set()), Critical Issues, Findings, Plan Conformance, Suggestions, Summary, Verdict (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.22
Nodes (8): code:block1 (C.1 ──┬──► C.2 ──┐), Definition of done for the whole phase, Dependency graph, Out of scope for Phase C, Phase C — Qwen LLM Integration + WebSocket Streaming (Execution Plan), Sub-phase index, Two reconciliations with the original spec, Why this exists

### Community 46 - "Community 46"
Cohesion: 0.22
Nodes (8): Code Review Findings, Critical Issues, Findings, Plan Conformance, Suggestions, Summary, Verdict, Warnings

### Community 47 - "Community 47"
Cohesion: 0.22
Nodes (8): code:block1 (D.1 ──┬──► D.3 ──┬──► D.5 ──► D.6), Definition of done for the whole phase, Dependency graph, Out of scope for Phase D, Phase D — Video Training Pipeline (Execution Plan), Sub-phase index, Two corrections to the original spec, Why this exists

### Community 48 - "Community 48"
Cohesion: 0.22
Nodes (8): Code Review Findings, Critical Issues, Findings, Plan Conformance, Suggestions, Summary, Verdict, Warnings

### Community 49 - "Community 49"
Cohesion: 0.22
Nodes (8): Code Review Findings, Critical Issues, Findings, Plan Conformance, Suggestions, Summary, Verdict, Warnings

### Community 50 - "Community 50"
Cohesion: 0.25
Nodes (7): Acceptance, code:python ("""), D.5 — RAG evaluation harness, File: `trainerAI_backend/scripts/eval_rag.py`, Goal, Tuning loop, Why a separate `scripts/` directory and not `tests/`

### Community 51 - "Community 51"
Cohesion: 0.53
Nodes (4): _build_client(), test_perception_payload_persisted_jsonb(), test_perception_payload_requires_iso_timestamp(), test_perception_payload_requires_timezone_in_timestamp()

### Community 52 - "Community 52"
Cohesion: 0.33
Nodes (5): Deviations from Original Spec, Open Issues for Phase F, Phase C — Completion Report, Test Count, What Shipped

### Community 53 - "Community 53"
Cohesion: 0.7
Nodes (4): _build_prompt_payload(), persist_command_feedback(), safe_persist_command_feedback(), _validate_iso8601_timestamp()

## Knowledge Gaps
- **521 isolated node(s):** `WebSocket endpoint for streaming AI guidance to the overlay client. One connect`, `Real semantic embedding service using sentence-transformers all-MiniLM-L6-v2. P`, `Load the model once and keep it in memory for the process lifetime.`, `Embed a single string into a 384-dimensional float vector.     Thread-safe; mod`, `Embed many strings in one model call (~10x faster than calling embed_text in a l` (+516 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **37 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_pool()` connect `Community 14` to `Community 1`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `ingest_video()` connect `Community 1` to `Community 4`, `Community 14`, `Community 7`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `stream_guidance()` connect `Community 2` to `Community 14`, `Community 7`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `make_chunks()` (e.g. with `ingest_video()` and `test_make_chunks_empty_segments()`) actually correct?**
  _`make_chunks()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `WebSocket endpoint for streaming AI guidance to the overlay client. One connect`, `Real semantic embedding service using sentence-transformers all-MiniLM-L6-v2. P`, `Load the model once and keep it in memory for the process lifetime.` to the rest of the system?**
  _521 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._