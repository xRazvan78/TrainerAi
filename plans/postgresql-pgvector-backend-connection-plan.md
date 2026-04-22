## Plan: PostgreSQL pgvector backend connection

Build a minimal FastAPI backend foundation that connects to PostgreSQL on port 5432 and supports pgvector similarity operations using existing backend dependencies. This initializes the database lifecycle and schema at startup, then adds a first integration route to validate end-to-end vector DB flow.

**Stack components affected:** FastAPI orchestrator backend, asyncpg connection pool, PostgreSQL schema bootstrap, pgvector index/query helpers

**Phases 4**
1. **Phase 1: Backend Service Skeleton**
    - **Objective:** Create initial backend package structure and environment-driven DB settings with empty credential fields for user completion.
    - **Agent tier:** Tier 2 - Context Agent
    - **Files/Functions to Modify/Create:** trainerAI_backend app package, configuration module, environment template, baseline tests
    - **Tests to Write:** test_settings_port_defaults_5432, test_settings_database_url_prefers_explicit_value
    - **Steps:**
        1. Create backend app package and FastAPI entrypoint scaffolding.
        2. Add settings model with PostgreSQL host/port/user/password/database fields.
        3. Add .env.example with empty credentials and documented defaults.

2. **Phase 2: Async PostgreSQL Connectivity**
    - **Objective:** Implement asyncpg pool creation and startup/shutdown lifecycle wiring in FastAPI.
    - **Agent tier:** Tier 2 - Context Agent
    - **Files/Functions to Modify/Create:** DB pool module, FastAPI lifespan integration, health route with DB ping
    - **Tests to Write:** test_pool_initializes_on_startup, test_pool_closes_on_shutdown, test_db_health_reports_unavailable_when_not_connected
    - **Steps:**
        1. Create asyncpg pool factory/getter helpers.
        2. Wire pool to FastAPI app state in lifespan startup/shutdown.
        3. Add DB health endpoint that validates connectivity safely.

3. **Phase 3: pgvector Schema Bootstrap and Store Helpers**
    - **Objective:** Bootstrap required extension/tables/indexes at startup and add vector store insert/query helpers.
    - **Agent tier:** Tier 3 - rag-retrieval-subagent foundation
    - **Files/Functions to Modify/Create:** schema bootstrap module, vector store helper module
    - **Tests to Write:** test_bootstrap_creates_vector_extension_idempotently, test_bootstrap_creates_embeddings_and_training_examples, test_similarity_query_uses_threshold_and_top_k
    - **Steps:**
        1. Create startup SQL for vector extension and required tables: sessions, embeddings, training_examples.
        2. Create ivfflat index on embeddings.embedding with vector_cosine_ops and lists=100.
        3. Add parameterized helper functions for vector insert and similarity retrieval.

4. **Phase 4: Minimal API Integration Route**
    - **Objective:** Expose one API route to verify PostgreSQL + pgvector operations through app runtime.
    - **Agent tier:** Tier 2 - Context Agent
    - **Files/Functions to Modify/Create:** API route module, request/response models, integration tests
    - **Tests to Write:** test_vector_round_trip_endpoint_success, test_vector_endpoint_handles_db_unavailable_gracefully
    - **Steps:**
        1. Add route that inserts sample embedding content and runs a similarity query.
        2. Return structured JSON response suitable for future agent integration.
        3. Ensure no WebSocket message schema changes are introduced.

**Open Questions 1**
1. None pending. Resolved by user approval: credentials left empty in template, startup bootstrap enabled, vector dimension fixed at 384, training_examples included.
