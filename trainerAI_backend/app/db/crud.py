import json
from typing import Any, Sequence

import asyncpg

from app.db.schema import VECTOR_DIMENSION


def to_vector_literal(values: Sequence[float]) -> str:
    if len(values) != VECTOR_DIMENSION:
        raise ValueError(f"embedding must contain exactly {VECTOR_DIMENSION} values")

    normalized = [str(float(value)) for value in values]
    return "[" + ",".join(normalized) + "]"


def parse_vector_literal(value: str | None) -> list[float]:
    if not value:
        return []

    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]

    if not stripped:
        return []

    return [float(part) for part in stripped.split(",")]


def _record_to_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return dict(record)


def _embedding_record_to_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
    if record is None:
        return None

    payload = dict(record)
    payload["embedding"] = parse_vector_literal(payload.pop("embedding_text", None))
    return payload


def _affected_rows_from_status(status: str) -> int:
    try:
        return int(status.split()[-1])
    except (AttributeError, IndexError, ValueError):
        return 0


async def create_session(
    pool: asyncpg.Pool,
    session_id: str,
    user_id: str | None = None,
    active_tool: str | None = None,
    command_sequence: Sequence[str] | None = None,
    action_count: int = 0,
    skill_score: float | None = None,
    verbosity_level: str | None = None,
) -> dict[str, Any] | None:
    command_sequence_json = json.dumps(list(command_sequence or []))

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            INSERT INTO sessions (
                session_id, user_id, active_tool, command_sequence,
                action_count, skill_score, verbosity_level
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            RETURNING session_id, user_id, active_tool, command_sequence,
                      action_count, skill_score, verbosity_level,
                      started_at, updated_at;
            """,
            session_id,
            user_id,
            active_tool,
            command_sequence_json,
            action_count,
            skill_score,
            verbosity_level,
        )
    return _record_to_dict(record)


async def get_session(pool: asyncpg.Pool, session_id: str) -> dict[str, Any] | None:
    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            SELECT session_id, user_id, active_tool, command_sequence,
                   action_count, skill_score, verbosity_level,
                   started_at, updated_at
            FROM sessions
            WHERE session_id = $1;
            """,
            session_id,
        )
    return _record_to_dict(record)


async def list_sessions(pool: asyncpg.Pool, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT session_id, user_id, active_tool, command_sequence,
                   action_count, skill_score, verbosity_level,
                   started_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT $1 OFFSET $2;
            """,
            limit,
            offset,
        )
    return [dict(row) for row in rows]


async def update_session(
    pool: asyncpg.Pool,
    session_id: str,
    user_id: str | None = None,
    active_tool: str | None = None,
    command_sequence: Sequence[str] | None = None,
    action_count: int | None = None,
    skill_score: float | None = None,
    verbosity_level: str | None = None,
) -> dict[str, Any] | None:
    command_sequence_json = None
    if command_sequence is not None:
        command_sequence_json = json.dumps(list(command_sequence))

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            UPDATE sessions
            SET user_id = COALESCE($2, user_id),
                active_tool = COALESCE($3, active_tool),
                command_sequence = COALESCE($4::jsonb, command_sequence),
                action_count = COALESCE($5, action_count),
                skill_score = COALESCE($6, skill_score),
                verbosity_level = COALESCE($7, verbosity_level),
                updated_at = now()
            WHERE session_id = $1
            RETURNING session_id, user_id, active_tool, command_sequence,
                      action_count, skill_score, verbosity_level,
                      started_at, updated_at;
            """,
            session_id,
            user_id,
            active_tool,
            command_sequence_json,
            action_count,
            skill_score,
            verbosity_level,
        )
    return _record_to_dict(record)


async def delete_session(pool: asyncpg.Pool, session_id: str) -> bool:
    async with pool.acquire() as connection:
        status = await connection.execute("DELETE FROM sessions WHERE session_id = $1;", session_id)
    return _affected_rows_from_status(status) > 0


async def create_embedding(
    pool: asyncpg.Pool,
    doc_id: str,
    source: str,
    content: str,
    embedding: Sequence[float],
) -> dict[str, Any] | None:
    vector_literal = to_vector_literal(embedding)

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            INSERT INTO embeddings (doc_id, source, content, embedding)
            VALUES ($1, $2, $3, $4::vector)
            RETURNING doc_id, source, content, embedding::text AS embedding_text, created_at;
            """,
            doc_id,
            source,
            content,
            vector_literal,
        )
    return _embedding_record_to_dict(record)


async def get_embedding(pool: asyncpg.Pool, doc_id: str) -> dict[str, Any] | None:
    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            SELECT doc_id, source, content, embedding::text AS embedding_text, created_at
            FROM embeddings
            WHERE doc_id = $1;
            """,
            doc_id,
        )
    return _embedding_record_to_dict(record)


async def list_embeddings(pool: asyncpg.Pool, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT doc_id, source, content, embedding::text AS embedding_text, created_at
            FROM embeddings
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2;
            """,
            limit,
            offset,
        )

    return [_embedding_record_to_dict(row) for row in rows if row is not None]


async def update_embedding(
    pool: asyncpg.Pool,
    doc_id: str,
    source: str | None = None,
    content: str | None = None,
    embedding: Sequence[float] | None = None,
) -> dict[str, Any] | None:
    vector_literal = to_vector_literal(embedding) if embedding is not None else None

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            UPDATE embeddings
            SET source = COALESCE($2, source),
                content = COALESCE($3, content),
                embedding = COALESCE($4::vector, embedding)
            WHERE doc_id = $1
            RETURNING doc_id, source, content, embedding::text AS embedding_text, created_at;
            """,
            doc_id,
            source,
            content,
            vector_literal,
        )
    return _embedding_record_to_dict(record)


async def delete_embedding(pool: asyncpg.Pool, doc_id: str) -> bool:
    async with pool.acquire() as connection:
        status = await connection.execute("DELETE FROM embeddings WHERE doc_id = $1;", doc_id)
    return _affected_rows_from_status(status) > 0


async def query_similar_embeddings(
    pool: asyncpg.Pool,
    embedding: Sequence[float],
    min_similarity: float = 0.72,
    limit: int = 5,
) -> list[dict[str, Any]]:
    vector_literal = to_vector_literal(embedding)

    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT doc_id, source, content,
                   1 - (embedding <=> $1::vector) AS similarity_score
            FROM embeddings
            WHERE 1 - (embedding <=> $1::vector) >= $2
            ORDER BY similarity_score DESC
            LIMIT $3;
            """,
            vector_literal,
            min_similarity,
            limit,
        )

    return [dict(row) for row in rows]


async def create_perception_state(
    pool: asyncpg.Pool,
    session_id: str,
    payload: dict[str, Any],
    observed_at: str,
) -> dict[str, Any] | None:
    payload_json = json.dumps(payload)

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            INSERT INTO perception_states (session_id, payload, observed_at)
            VALUES ($1, $2::jsonb, $3::timestamptz)
            RETURNING id, session_id, payload, observed_at, created_at;
            """,
            session_id,
            payload_json,
            observed_at,
        )
    return _record_to_dict(record)


async def get_latest_perception_state(
    pool: asyncpg.Pool,
    session_id: str,
) -> dict[str, Any] | None:
    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            SELECT id, session_id, payload, observed_at, created_at
            FROM perception_states
            WHERE session_id = $1
            ORDER BY observed_at DESC, id DESC
            LIMIT 1;
            """,
            session_id,
        )
    return _record_to_dict(record)


async def create_training_example(
    pool: asyncpg.Pool,
    doc_id: str,
    session_id: str | None = None,
    context_label: str | None = None,
    active_tool: str | None = None,
    error_type: str | None = None,
    guidance_priority: str | None = None,
    prompt_used: str | None = None,
    response_given: str | None = None,
    context_retrieved: list[dict[str, Any]] | None = None,
    user_action_after: str | None = None,
    outcome: str | None = None,
    confidence: float | None = None,
    time_to_action_ms: int | None = None,
    source: str = "user_confirmed",
) -> dict[str, Any] | None:
    context_retrieved_json = None
    if context_retrieved is not None:
        context_retrieved_json = json.dumps(context_retrieved)

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            INSERT INTO training_examples (
                doc_id, session_id, context_label, active_tool,
                error_type, guidance_priority, prompt_used,
                response_given, context_retrieved, user_action_after,
                outcome, confidence, time_to_action_ms, source
            )
            VALUES (
                $1, $2, $3, $4,
                $5, $6, $7,
                $8, $9::jsonb, $10,
                $11, $12, $13, $14
            )
            RETURNING doc_id, session_id, context_label, active_tool,
                      error_type, guidance_priority, prompt_used,
                             response_given, context_retrieved, user_action_after, outcome,
                      confidence, time_to_action_ms, source, created_at;
            """,
            doc_id,
            session_id,
            context_label,
            active_tool,
            error_type,
            guidance_priority,
            prompt_used,
            response_given,
            context_retrieved_json,
            user_action_after,
            outcome,
            confidence,
            time_to_action_ms,
            source,
        )
    return _record_to_dict(record)


async def get_training_example(pool: asyncpg.Pool, doc_id: str) -> dict[str, Any] | None:
    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            SELECT doc_id, session_id, context_label, active_tool,
                   error_type, guidance_priority, prompt_used,
                   response_given, context_retrieved, user_action_after, outcome,
                   confidence, time_to_action_ms, source, created_at
            FROM training_examples
            WHERE doc_id = $1;
            """,
            doc_id,
        )
    return _record_to_dict(record)


async def list_training_examples(
    pool: asyncpg.Pool, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT doc_id, session_id, context_label, active_tool,
                   error_type, guidance_priority, prompt_used,
                   response_given, context_retrieved, user_action_after, outcome,
                   confidence, time_to_action_ms, source, created_at
            FROM training_examples
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2;
            """,
            limit,
            offset,
        )
    return [dict(row) for row in rows]


async def update_training_example(
    pool: asyncpg.Pool,
    doc_id: str,
    session_id: str | None = None,
    context_label: str | None = None,
    active_tool: str | None = None,
    error_type: str | None = None,
    guidance_priority: str | None = None,
    prompt_used: str | None = None,
    response_given: str | None = None,
    context_retrieved: list[dict[str, Any]] | None = None,
    user_action_after: str | None = None,
    outcome: str | None = None,
    confidence: float | None = None,
    time_to_action_ms: int | None = None,
    source: str | None = None,
) -> dict[str, Any] | None:
    context_retrieved_json = None
    if context_retrieved is not None:
        context_retrieved_json = json.dumps(context_retrieved)

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            UPDATE training_examples
            SET session_id = COALESCE($2, session_id),
                context_label = COALESCE($3, context_label),
                active_tool = COALESCE($4, active_tool),
                error_type = COALESCE($5, error_type),
                guidance_priority = COALESCE($6, guidance_priority),
                prompt_used = COALESCE($7, prompt_used),
                response_given = COALESCE($8, response_given),
                    context_retrieved = COALESCE($9::jsonb, context_retrieved),
                    user_action_after = COALESCE($10, user_action_after),
                    outcome = COALESCE($11, outcome),
                    confidence = COALESCE($12, confidence),
                    time_to_action_ms = COALESCE($13, time_to_action_ms),
                    source = COALESCE($14, source)
            WHERE doc_id = $1
            RETURNING doc_id, session_id, context_label, active_tool,
                      error_type, guidance_priority, prompt_used,
                        response_given, context_retrieved, user_action_after, outcome,
                      confidence, time_to_action_ms, source, created_at;
            """,
            doc_id,
            session_id,
            context_label,
            active_tool,
            error_type,
            guidance_priority,
            prompt_used,
            response_given,
              context_retrieved_json,
            user_action_after,
            outcome,
            confidence,
            time_to_action_ms,
            source,
        )
    return _record_to_dict(record)


async def delete_training_example(pool: asyncpg.Pool, doc_id: str) -> bool:
    async with pool.acquire() as connection:
        status = await connection.execute("DELETE FROM training_examples WHERE doc_id = $1;", doc_id)
    return _affected_rows_from_status(status) > 0
