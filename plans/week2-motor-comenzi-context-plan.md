## Plan: Week 2 Motor Comenzi Context

Build the command nervous system end-to-end so the backend can ingest natural language commands, capture and persist visual/session context, retrieve relevant pgvector context, and log feedback data for future learning. This plan keeps command ingress non-blocking by returning immediate acknowledgement IDs while streaming enriched results later through the WebSocket pipeline.

**Stack components affected:** FastAPI orchestrator, Context Agent/session-state and RAG flow, Perception payload ingestion, Feedback logging, PostgreSQL schema, pgvector retrieval

**Phases 6**
1. **Phase 1: Command Entrypoint Contract and Acknowledge Flow**
    - **Objective:** Create `/api/command` to accept natural language input and immediately return an acknowledgement task/session ID without waiting for LLM or full context processing.
    - **Agent tier:** Tier 2 - Context Agent
    - **Files/Functions to Modify/Create:** `trainerAI_backend/app/models/command_models.py`, `trainerAI_backend/app/routers/command.py`, `trainerAI_backend/app/main.py`, command orchestration scaffold under `trainerAI_backend/app/services/`
    - **Tests to Write:** `test_command_payload_requires_text_timestamp_session_id`, `test_command_payload_requires_iso_timestamp`, `test_command_endpoint_returns_ack_immediately`
    - **Steps:**
        1. Define command request schema with `text`, `timestamp` (ISO-8601), `session_id`.
        2. Add command endpoint with immediate non-blocking acknowledgement response.
        3. Stub async command processing hook for later streaming pipeline integration.

2. **Phase 2: Session State Orchestration and Context Packet Foundation**
    - **Objective:** Implement session-state-subagent style session tracking and active context assembly for each command request.
    - **Agent tier:** Tier 3 - session-state-subagent
    - **Files/Functions to Modify/Create:** `trainerAI_backend/app/services/session_state_service.py`, extend `trainerAI_backend/app/db/crud.py`, context packet models in `trainerAI_backend/app/models/context_models.py`
    - **Tests to Write:** `test_session_state_creates_if_missing`, `test_session_state_updates_action_count`, `test_session_state_tracks_recent_commands`
    - **Steps:**
        1. Upsert/load session state by `session_id` on each command.
        2. Update action count, command sequence, active tool/context labels.
        3. Return normalized context foundation object for downstream retrieval.

3. **Phase 3: RAG Retrieval Pipeline on pgvector Embeddings**
    - **Objective:** Wire RAG-retrieval-subagent behavior to query `embeddings` with semantic similarity for command context.
    - **Agent tier:** Tier 3 - rag-retrieval-subagent
    - **Files/Functions to Modify/Create:** `trainerAI_backend/app/services/rag_service.py`, optional embedder helper in `trainerAI_backend/app/services/embedder_service.py`, extend `trainerAI_backend/requirements.txt` if needed
    - **Tests to Write:** `test_rag_retrieval_returns_top_k_docs`, `test_rag_retrieval_applies_similarity_threshold`, `test_rag_retrieval_handles_db_failure_non_blocking`
    - **Steps:**
        1. Build command-context query text and obtain embedding.
        2. Query pgvector similarity with threshold/top-k controls.
        3. Attach retrieved docs to context packet for later streaming use.

4. **Phase 4: Perception Ingestion with Persistent JSONB State**
    - **Objective:** Add Perception Agent ingestion endpoint and persist visual payloads (YOLO boxes + OCR text) in PostgreSQL for replay/debug/fine-tuning.
    - **Agent tier:** Tier 2 - Perception Agent handoff to Context Agent
    - **Files/Functions to Modify/Create:** schema migration/bootstrap updates in `trainerAI_backend/app/db/schema.py`, CRUD extensions in `trainerAI_backend/app/db/crud.py`, `trainerAI_backend/app/models/perception_models.py`, `trainerAI_backend/app/routers/perception.py`
    - **Tests to Write:** `test_perception_payload_requires_iso_timestamp`, `test_perception_payload_persisted_jsonb`, `test_command_context_reads_latest_persisted_perception`
    - **Steps:**
        1. Define perception payload contract with ISO-8601 timestamp.
        2. Add JSONB persistence for visual state linked to session.
        3. Read latest persisted perception state during command context assembly.

5. **Phase 5: Feedback Logging with Dedicated Context Retrieval Column**
    - **Objective:** Implement Data-Logger-subagent logging path to persist incoming command, retrieved context, and session ID into `training_examples` using a new dedicated `context_retrieved` column.
    - **Agent tier:** Tier 3 - data-logger-subagent
    - **Files/Functions to Modify/Create:** `trainerAI_backend/app/db/schema.py`, `trainerAI_backend/app/db/crud.py`, `trainerAI_backend/app/services/feedback_logger_service.py`
    - **Tests to Write:** `test_training_example_logs_context_retrieved_separately`, `test_feedback_logger_non_blocking_from_command_ack`, `test_feedback_logger_persists_iso_timestamp`
    - **Steps:**
        1. Add `context_retrieved` column to `training_examples` schema.
        2. Extend insert/update logging helpers to include separated retrieved-context payload.
        3. Execute logging asynchronously so `/api/command` acknowledgement remains immediate.

6. **Phase 6: Orchestration Integration and End-to-End Validation**
    - **Objective:** Integrate command, context, perception, and feedback paths into a coherent Week 2 flow, explicitly deferring error-detect-subagent logic to Week 3.
    - **Agent tier:** Tier 1 - Conductor integration
    - **Files/Functions to Modify/Create:** `trainerAI_backend/app/main.py`, orchestration service module(s), integration tests under `trainerAI_backend/tests/`
    - **Tests to Write:** `test_command_ack_then_async_processing_path`, `test_command_pipeline_without_error_detect_week2_scope`, `test_e2e_context_logging_with_perception_and_rag`
    - **Steps:**
        1. Register new routers/services and lifecycle dependencies.
        2. Wire asynchronous pipeline to produce command ack immediately and process context/logging in background.
        3. Validate Week 2 boundaries: no error-detect-subagent evaluation in command output.

**Open Questions 1**
1. None pending. Resolved by user approval: immediate ack response, persisted perception payloads in PostgreSQL, dedicated `context_retrieved` column, ISO-8601 timestamps, error-detect-subagent deferred to Week 3.
