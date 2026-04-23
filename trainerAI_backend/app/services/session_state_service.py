from typing import Any

import asyncpg

from app.db import crud
from app.models.command_models import CommandRequest
from app.models.context_models import ContextPacketFoundation, SessionSnapshot

MAX_COMMAND_SEQUENCE = 10
DEFAULT_CONTEXT_LABEL = "command_active"


def _extract_active_tool(command_text: str) -> str:
    first_token = command_text.strip().split(" ", 1)[0]
    cleaned = "".join(ch for ch in first_token if ch.isalnum() or ch in ("_", "-"))
    return cleaned.upper() if cleaned else "UNKNOWN"


def _normalize_command_sequence(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _build_next_command_sequence(existing_sequence: list[str], active_tool: str) -> list[str]:
    sequence = list(existing_sequence)
    if not sequence or sequence[-1] != active_tool:
        sequence.append(active_tool)
    return sequence[-MAX_COMMAND_SEQUENCE:]


async def _ensure_session_exists(pool: asyncpg.Pool, session_id: str) -> dict[str, Any]:
    current = await crud.get_session(pool=pool, session_id=session_id)
    if current is not None:
        return current

    created = await crud.create_session(
        pool=pool,
        session_id=session_id,
        command_sequence=[],
        action_count=0,
    )
    return created or {"session_id": session_id, "command_sequence": [], "action_count": 0}


async def update_session_from_command(
    pool: asyncpg.Pool,
    command: CommandRequest,
) -> SessionSnapshot:
    current = await _ensure_session_exists(pool=pool, session_id=command.session_id)

    active_tool = _extract_active_tool(command.text)
    existing_sequence = _normalize_command_sequence(current.get("command_sequence"))
    command_sequence = _build_next_command_sequence(existing_sequence, active_tool)
    action_count = int(current.get("action_count") or 0) + 1

    updated = await crud.update_session(
        pool=pool,
        session_id=command.session_id,
        active_tool=active_tool,
        command_sequence=command_sequence,
        action_count=action_count,
    )
    final_state = updated or current

    return SessionSnapshot(
        session_id=str(final_state.get("session_id", command.session_id)),
        active_tool=str(final_state.get("active_tool") or active_tool),
        command_sequence=_normalize_command_sequence(final_state.get("command_sequence", command_sequence)),
        action_count=int(final_state.get("action_count") or action_count),
        current_context_label=DEFAULT_CONTEXT_LABEL,
        skill_score=final_state.get("skill_score"),
        verbosity_level=final_state.get("verbosity_level"),
    )


async def build_context_packet_foundation(
    pool: asyncpg.Pool,
    task_id: str,
    command: CommandRequest,
) -> ContextPacketFoundation:
    session_snapshot = await update_session_from_command(pool=pool, command=command)
    latest_perception = await crud.get_latest_perception_state(
        pool=pool,
        session_id=command.session_id,
    )

    perception_payload = None
    if latest_perception is not None:
        payload = latest_perception.get("payload")
        if isinstance(payload, dict):
            perception_payload = payload

    return ContextPacketFoundation(
        task_id=task_id,
        session_id=command.session_id,
        command_text=command.text,
        command_timestamp=command.timestamp,
        session=session_snapshot,
        perception_state=perception_payload,
    )
