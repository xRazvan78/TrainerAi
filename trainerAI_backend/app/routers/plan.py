from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.models.plan_models import PlanAdvanceRequest, PlanClearRequest, PlanCreateRequest, PlanMessageRequest
from app.services import plan_broadcaster, plan_service

logger = logging.getLogger(__name__)

_bg_tasks: set[asyncio.Task] = set()

def _schedule(coro) -> None:
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)

router = APIRouter(prefix="/api/plan", tags=["plan"])

_PING_INTERVAL_SECONDS = 20


@router.websocket("/ws/{session_id}")
async def plan_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()

    existing = plan_broadcaster._active_connections.get(session_id)
    if existing is not None and existing is not websocket:
        try:
            await existing.close()
        except Exception:
            pass

    plan_broadcaster._active_connections[session_id] = websocket
    try:
        while True:
            await asyncio.sleep(_PING_INTERVAL_SECONDS)
            await websocket.send_text('{"type":"ping"}')
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if plan_broadcaster._active_connections.get(session_id) is websocket:
            plan_broadcaster._active_connections.pop(session_id, None)


@router.post("/create", status_code=202)
async def plan_create(payload: PlanCreateRequest, request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    _schedule(_run_create(pool, payload.session_id, payload.goal))
    return {"status": "accepted", "session_id": payload.session_id}


@router.post("/message", status_code=202)
async def plan_message(payload: PlanMessageRequest, request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    _schedule(_run_message(pool, payload.session_id, payload.text))
    return {"status": "accepted", "session_id": payload.session_id}


@router.post("/advance")
async def plan_advance(payload: PlanAdvanceRequest):
    plan = plan_service.advance_manual(payload.session_id)
    if plan:
        await plan_broadcaster.broadcast_step(payload.session_id, plan)
    return {"status": "ok"}


@router.post("/clear")
async def plan_clear(payload: PlanClearRequest):
    plan_service.clear(payload.session_id)
    return {"status": "ok"}


async def _run_create(pool, session_id: str, goal: str) -> None:
    try:
        plan = await plan_service.generate_plan(pool, session_id, goal)
        await plan_broadcaster.broadcast_plan(session_id, plan)
    except Exception as exc:
        logger.error("_run_create failed for session %s: %s", session_id, exc)
        await plan_broadcaster.broadcast_done(session_id)


async def _run_message(pool, session_id: str, text: str) -> None:
    try:
        async for token in plan_service.chat(pool, session_id, text):
            await plan_broadcaster.broadcast_chat_token(session_id, token)
        await plan_broadcaster.broadcast_done(session_id)
    except Exception as exc:
        logger.error("_run_message failed for session %s: %s", session_id, exc)
        await plan_broadcaster.broadcast_done(session_id)
