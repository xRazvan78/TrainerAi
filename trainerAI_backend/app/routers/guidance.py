"""
WebSocket endpoint for streaming AI guidance to the overlay client.
One connection per session_id. Guidance is pushed as tokens arrive from the LLM.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_broadcaster import (
    _PING_INTERVAL_SECONDS,
    _active_connections,
    broadcast_done,
    broadcast_token,
)

router = APIRouter(prefix="/api/guidance", tags=["guidance"])


@router.websocket("/ws/{session_id}")
async def guidance_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()

    # If a previous connection for this session is still tracked, close it first.
    existing = _active_connections.get(session_id)
    if existing is not None and existing is not websocket:
        try:
            await existing.close()
        except Exception:
            pass  # stale socket — ignore close errors

    _active_connections[session_id] = websocket
    try:
        while True:
            await asyncio.sleep(_PING_INTERVAL_SECONDS)
            await websocket.send_text('{"type":"ping"}')
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        # Only clear the registry if we still own the slot (we may have been
        # superseded by a reconnect during the sleep).
        if _active_connections.get(session_id) is websocket:
            _active_connections.pop(session_id, None)
