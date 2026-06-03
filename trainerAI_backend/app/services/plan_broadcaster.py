from __future__ import annotations

import json
import logging

from fastapi import WebSocket

from app.models.plan_models import Plan

logger = logging.getLogger(__name__)

_active_connections: dict[str, WebSocket] = {}


async def _safe_send(session_id: str, message: str) -> None:
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text(message)
    except Exception as exc:
        logger.debug("plan_broadcaster send failed for session %s: %s", session_id, exc)
        _active_connections.pop(session_id, None)


async def broadcast_chat_token(session_id: str, token: str) -> None:
    await _safe_send(session_id, json.dumps({"type": "token", "content": token}))


async def broadcast_plan(session_id: str, plan: Plan) -> None:
    await _safe_send(session_id, json.dumps({"type": "plan", "plan": plan.model_dump()}))


async def broadcast_step(session_id: str, plan: Plan) -> None:
    await _safe_send(
        session_id,
        json.dumps({"type": "step", "current_index": plan.current_index, "plan": plan.model_dump()}),
    )


async def broadcast_done(session_id: str) -> None:
    await _safe_send(session_id, json.dumps({"type": "done"}))
