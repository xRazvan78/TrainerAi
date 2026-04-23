import asyncpg

VECTOR_DIMENSION = 384

SCHEMA_STATEMENTS = (
    "CREATE EXTENSION IF NOT EXISTS vector;",
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT,
        active_tool TEXT,
        command_sequence JSONB,
        action_count INTEGER DEFAULT 0,
        skill_score DOUBLE PRECISION DEFAULT 0.40,
        verbosity_level TEXT DEFAULT 'standard',
        started_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    );
    """,
    f"""
    CREATE TABLE IF NOT EXISTS embeddings (
        id SERIAL PRIMARY KEY,
        doc_id TEXT UNIQUE,
        source TEXT,
        content TEXT,
        embedding vector({VECTOR_DIMENSION}),
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_embeddings_embedding_ivfflat
    ON embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
    """,
    """
    CREATE TABLE IF NOT EXISTS training_examples (
        id SERIAL PRIMARY KEY,
        doc_id TEXT UNIQUE,
        session_id TEXT,
        context_label TEXT,
        active_tool TEXT,
        error_type TEXT,
        guidance_priority TEXT,
        prompt_used TEXT,
        response_given TEXT,
        context_retrieved JSONB,
        user_action_after TEXT,
        outcome TEXT,
        confidence DOUBLE PRECISION,
        time_to_action_ms INTEGER,
        source TEXT DEFAULT 'user_confirmed',
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """,
    """
    ALTER TABLE training_examples
    -- Backward-compatible migration for databases created before Phase 5.
    ADD COLUMN IF NOT EXISTS context_retrieved JSONB;
    """,
    """
    CREATE TABLE IF NOT EXISTS perception_states (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        payload JSONB NOT NULL,
        observed_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_perception_states_session_observed
    ON perception_states (session_id, observed_at DESC);
    """,
)


async def bootstrap_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection:
        for statement in SCHEMA_STATEMENTS:
            await connection.execute(statement)
