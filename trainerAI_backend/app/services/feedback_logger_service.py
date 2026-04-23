import asyncio
import json
from datetime import datetime
from typing import Any

import asyncpg

from app.db import crud
from app.models.context_models import ContextPacketFoundation

ISO_TIMESTAMP_ERROR = "timestamp must be a valid ISO-8601 string"


def _validate_iso8601_timestamp(value: str) -> str:
    normalized = value.replace("Z", "+00:00")
    if "T" not in value:
        raise ValueError(ISO_TIMESTAMP_ERROR)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(ISO_TIMESTAMP_ERROR) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(ISO_TIMESTAMP_ERROR)
    return value


def _build_prompt_payload(task_id: str, foundation: ContextPacketFoundation) -> str:
    # Defensive validation protects this service when called outside request-model flows.
    command_timestamp = _validate_iso8601_timestamp(foundation.command_timestamp)
    payload = {
        "task_id": task_id,
        "session_id": foundation.session_id,
        "command_text": foundation.command_text,
        "command_timestamp": command_timestamp,
    }
    return json.dumps(payload)


async def persist_command_feedback(
    pool: asyncpg.Pool,
    task_id: str,
    foundation: ContextPacketFoundation,
    retrieved_context: list[dict[str, Any]],
) -> dict[str, Any] | None:
    prompt_payload = _build_prompt_payload(task_id=task_id, foundation=foundation)

    return await crud.create_training_example(
        pool=pool,
        doc_id=f"feedback-{task_id}",
        session_id=foundation.session_id,
        context_label=foundation.session.current_context_label,
        active_tool=foundation.session.active_tool,
        guidance_priority="context_retrieval",
        prompt_used=prompt_payload,
        response_given="context_documents_retrieved",
        context_retrieved=retrieved_context,
        outcome="retrieved",
        source="command_feedback",
    )


async def safe_persist_command_feedback(
    pool: asyncpg.Pool,
    task_id: str,
    foundation: ContextPacketFoundation,
    retrieved_context: list[dict[str, Any]],
) -> None:
    try:
        await persist_command_feedback(
            pool=pool,
            task_id=task_id,
            foundation=foundation,
            retrieved_context=retrieved_context,
        )
    except (
        asyncpg.PostgresError,
        OSError,
        RuntimeError,
        asyncio.TimeoutError,
        ValueError,
        TypeError,
    ):
        return
