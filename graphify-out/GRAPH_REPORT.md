# Graph Report - .  (2026-05-10)

## Corpus Check
- Corpus is ~31,180 words - fits in a single context window. You may not need a graph.

## Summary
- 314 nodes · 415 edges · 48 communities (25 shown, 23 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.81)
- Token cost: 180,325 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Perception Data Models|Perception Data Models]]
- [[_COMMUNITY_Backend Service Layer|Backend Service Layer]]
- [[_COMMUNITY_Database CRUD Layer|Database CRUD Layer]]
- [[_COMMUNITY_Video Ingest & Training|Video Ingest & Training]]
- [[_COMMUNITY_Context & Session State|Context & Session State]]
- [[_COMMUNITY_Screen Capture & Overlay|Screen Capture & Overlay]]
- [[_COMMUNITY_Multi-Agent Architecture|Multi-Agent Architecture]]
- [[_COMMUNITY_Command API Layer|Command API Layer]]
- [[_COMMUNITY_Command Tests & Rust App|Command Tests & Rust App]]
- [[_COMMUNITY_Embedding Service|Embedding Service]]
- [[_COMMUNITY_App Configuration|App Configuration]]
- [[_COMMUNITY_FastAPI Startup & DB Pool|FastAPI Startup & DB Pool]]
- [[_COMMUNITY_Command API Tests|Command API Tests]]
- [[_COMMUNITY_Perception API Tests|Perception API Tests]]
- [[_COMMUNITY_Feedback Logger|Feedback Logger]]
- [[_COMMUNITY_UI Framework Assets|UI Framework Assets]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
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

## God Nodes (most connected - your core abstractions)
1. `_record_to_dict()` - 9 edges
2. `embed_text()` - 9 edges
3. `_build_client()` - 8 edges
4. `command_pipeline_service.py` - 8 edges
5. `Phase F Full Pipeline Connection Spec` - 8 edges
6. `Settings` - 7 edges
7. `update_session_from_command()` - 7 edges
8. `TrainerAI Implementation Roadmap` - 7 edges
9. `D.3 Training Module` - 7 edges
10. `to_vector_literal()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `session-state-subagent` --semantically_similar_to--> `session_state_service.py`  [INFERRED] [semantically similar]
  README.md → CLAUDE.md
- `rag-retrieval-subagent` --semantically_similar_to--> `rag_service.py`  [INFERRED] [semantically similar]
  README.md → CLAUDE.md
- `qwen-inference-subagent` --semantically_similar_to--> `llm_service.py Phase C`  [INFERRED] [semantically similar]
  README.md → specs/phase-C-qwen-llm-integration.md
- `data-logger-subagent` --calls--> `pgvector Vector DB`  [EXTRACTED]
  README.md → CLAUDE.md
- `Phase F Full Pipeline Connection Spec` --references--> `src/main.rs Dioxus`  [EXTRACTED]
  specs/phase-F-full-pipeline-connection.md → trainerAI_overlay/src/main.rs

## Hyperedges (group relationships)
- **RAG Retrieval Pipeline** — claudemd_embedder_service, claudemd_pgvector, claudemd_rag_service, claudemd_all_minilm [EXTRACTED 1.00]
- **Command Pipeline Flow** — claudemd_command_router, claudemd_command_pipeline_service, claudemd_rag_service, claudemd_session_state_service, claudemd_feedback_logger_service [EXTRACTED 1.00]
- **Perception Subagent Triad** — readme_frame_diff, readme_yolov8, readme_easyocr [EXTRACTED 1.00]
- **Video-to-Embedding Ingest Pipeline** — video_extractor_py, transcriber_py, chunker_py, ingest_py, embedder_service_py, crud_py [EXTRACTED 1.00]
- **AutoCAD Perception Detection Pipeline** — capture_rs, perception_service_py, yolov8_detection, easyocr_text, session_state_service_py [EXTRACTED 0.95]
- **End-to-End Guidance Flow** — commands_rs, ws_client_rs, dioxus_main_rs, websocket_streaming, rag_service_py [EXTRACTED 0.95]
- **Tauri App Icon Set** — icon_128x128, icon_128x128at2x, icon_32x32, icon_icon, icon_square107, icon_square142, icon_square150, icon_square284, icon_square30, icon_square310, icon_square44, icon_square71, icon_square89, icon_storelogo [EXTRACTED 0.95]

## Communities (48 total, 23 thin omitted)

### Community 0 - "Perception Data Models"
Cohesion: 0.07
Nodes (12): BaseModel, PerceptionElement, PerceptionStatePersistedResponse, PerceptionStateRequest, EmbeddingCreate, EmbeddingUpdate, SessionCreate, SessionUpdate (+4 more)

### Community 1 - "Backend Service Layer"
Cohesion: 0.08
Nodes (34): all-MiniLM-L6-v2, command_pipeline_service.py, command.py Router, app/config.py, db/crud.py, db_crud.py Router, embedder_service.py, feedback_logger_service.py (+26 more)

### Community 2 - "Database CRUD Layer"
Cohesion: 0.12
Nodes (26): _affected_rows_from_status(), create_embedding(), create_perception_state(), create_session(), create_training_example(), delete_embedding(), delete_session(), delete_training_example() (+18 more)

### Community 3 - "Video Ingest & Training"
Cohesion: 0.12
Nodes (18): Chunk Overlap Strategy, scripts/eval_rag.py, FFmpeg Audio Extraction, pgvector 384-dim Embeddings, Phase B Implementation Plan, D.1 Schema Migration, D.2 Environment Setup, D.3 Training Module (+10 more)

### Community 4 - "Context & Session State"
Cohesion: 0.17
Nodes (17): ContextPacketFoundation, SessionSnapshot, build_context_packet_foundation(), _build_next_command_sequence(), _ensure_session_exists(), _extract_active_tool(), _normalize_command_sequence(), update_session_from_command() (+9 more)

### Community 5 - "Screen Capture & Overlay"
Cohesion: 0.17
Nodes (16): Average Hash Frame Diffing, src/main.rs Dioxus, EasyOCR Text Extraction, Label Studio Annotation Tool, perception.py Router, Phase A Setup, Phase D Video Training Pipeline Spec, Phase E Screen Capture Spec (+8 more)

### Community 6 - "Multi-Agent Architecture"
Cohesion: 0.12
Nodes (18): Conductor Agent, Context Agent, ContextPacket JSON, data-logger-subagent, difficulty-calibrator-subagent, easyocr-subagent, error-detect-subagent, Feedback Agent (+10 more)

### Community 7 - "Command API Layer"
Cohesion: 0.17
Nodes (11): CommandAcceptedResponse, command_endpoint(), process_command_placeholder(), _utc_now_iso8601(), run_week2_command_pipeline(), safe_run_week2_command_pipeline(), _apply_token_budget(), _query_text_from_foundation() (+3 more)

### Community 8 - "Command Tests & Rust App"
Cohesion: 0.18
Nodes (11): CommandRequest, run(), main(), _command(), test_e2e_context_logging_with_perception_and_rag(), _build_command(), _install_fake_crud(), test_command_context_reads_latest_persisted_perception() (+3 more)

### Community 9 - "Embedding Service"
Cohesion: 0.24
Nodes (10): embed_text(), _get_model(), Real semantic embedding service using sentence-transformers all-MiniLM-L6-v2. Pr, Load the model once and keep it in memory for the process lifetime., Embed a single string into a 384-dimensional float vector.     Thread-safe; mode, test_embed_text_is_deterministic(), test_embed_text_returns_384_floats(), test_model_is_cached() (+2 more)

### Community 10 - "App Configuration"
Cohesion: 0.29
Nodes (7): get_settings(), Settings, BaseSettings, _clear_env(), test_settings_database_url_prefers_explicit_value(), test_settings_derives_database_url_from_parts(), test_settings_port_defaults_5432()

### Community 11 - "FastAPI Startup & DB Pool"
Cohesion: 0.22
Nodes (7): lifespan(), create_pool(), get_pool_from_request(), shutdown_database(), startup_database(), bootstrap_schema(), get_db_pool()

### Community 12 - "Command API Tests"
Cohesion: 0.36
Nodes (8): _build_client(), test_command_ack_then_async_processing_path(), test_command_endpoint_returns_ack_immediately(), test_command_payload_requires_iso_timestamp(), test_command_payload_requires_text_timestamp_session_id(), test_command_payload_requires_timezone_in_timestamp(), test_command_pipeline_without_error_detect_week2_scope(), test_feedback_logger_non_blocking_from_command_ack()

### Community 13 - "Perception API Tests"
Cohesion: 0.53
Nodes (4): _build_client(), test_perception_payload_persisted_jsonb(), test_perception_payload_requires_iso_timestamp(), test_perception_payload_requires_timezone_in_timestamp()

### Community 14 - "Feedback Logger"
Cohesion: 0.7
Nodes (4): _build_prompt_payload(), persist_command_feedback(), safe_persist_command_feedback(), _validate_iso8601_timestamp()

## Knowledge Gaps
- **50 isolated node(s):** `Real semantic embedding service using sentence-transformers all-MiniLM-L6-v2. Pr`, `Load the model once and keep it in memory for the process lifetime.`, `Embed a single string into a 384-dimensional float vector.     Thread-safe; mode`, `trainerAI_overlay`, `perception.py Router` (+45 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ContextPacketFoundation` connect `Context & Session State` to `Perception Data Models`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `get_db_pool()` connect `FastAPI Startup & DB Pool` to `Perception Data Models`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `run_week2_command_pipeline()` connect `Command API Layer` to `Context & Session State`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `embed_text()` (e.g. with `retrieve_context_documents()` and `test_embed_text_returns_384_floats()`) actually correct?**
  _`embed_text()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Real semantic embedding service using sentence-transformers all-MiniLM-L6-v2. Pr`, `Load the model once and keep it in memory for the process lifetime.`, `Embed a single string into a 384-dimensional float vector.     Thread-safe; mode` to the rest of the system?**
  _50 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Perception Data Models` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Backend Service Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._