from __future__ import annotations

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_active_connections: dict[str, WebSocket] = {}
_PING_INTERVAL_SECONDS = 30


async def broadcast_token(session_id: str, token: str) -> None:
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text(token)
    except Exception as exc:
        logger.debug("broadcast_token failed for session %s: %s", session_id, exc)
        _active_connections.pop(session_id, None)


async def broadcast_done(session_id: str) -> None:
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text('{"type":"done"}')
    except Exception as exc:
        logger.debug("broadcast_done failed for session %s: %s", session_id, exc)
        _active_connections.pop(session_id, None)
