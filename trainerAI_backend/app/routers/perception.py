import asyncio
import logging
import uuid
from datetime import timezone

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.db import crud
from app.models.command_models import CommandRequest
from app.models.perception_models import PerceptionStatePersistedResponse, PerceptionStateRequest
from app.services import guidance_trigger_service, plan_broadcaster, plan_service
from app.services.command_pipeline_service import safe_run_week2_command_pipeline
from app.services.perception_service import analyse_frame
from app.services.session_state_service import _extract_active_tool_from_perception

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/perception", tags=["perception"])


def get_db_pool(request: Request) -> asyncpg.Pool:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool is not initialized.")
    return pool


@router.post(
    "/state",
    response_model=PerceptionStatePersistedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_perception_state(
    payload: PerceptionStateRequest,
    background_tasks: BackgroundTasks,
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PerceptionStatePersistedResponse:
    if payload.frame_b64 and not payload.elements:
        detected = await asyncio.to_thread(analyse_frame, payload.frame_b64)
        print(f"[perception] analyse_frame → {len(detected)} elements: {[e.label for e in detected]}", flush=True)
        if detected:
            payload = payload.model_copy(update={"elements": detected})

    persisted = await crud.create_perception_state(
        pool=pool,
        session_id=payload.session_id,
        payload=payload.model_dump(mode="python", exclude={"frame_b64"}),
        observed_at=payload.timestamp,
    )
    if persisted is None:
        raise HTTPException(status_code=500, detail="Failed to persist perception state.")

    perception_id = persisted.get("id")
    session_id = persisted.get("session_id")
    observed_at = persisted.get("observed_at")
    if perception_id is None or session_id is None or observed_at is None:
        raise HTTPException(status_code=500, detail="Failed to persist perception state.")

    active_tool = _extract_active_tool_from_perception(payload.model_dump(mode="python"))
    print(f"[perception] active_tool={active_tool!r} should_trigger={guidance_trigger_service.should_trigger(session_id, active_tool) if active_tool else 'n/a'}", flush=True)

    if plan_service.has_active_plan(session_id):
        if active_tool:
            advanced = plan_service.try_advance(session_id, active_tool)
            if advanced is not None:
                await plan_broadcaster.broadcast_step(session_id, advanced)
        return PerceptionStatePersistedResponse(
            status="persisted",
            perception_id=int(perception_id),
            session_id=str(session_id),
            observed_at=str(observed_at),
        )

    if active_tool and guidance_trigger_service.should_trigger(session_id, active_tool):
        guidance_trigger_service.mark_triggered(session_id, active_tool)
        print(f"[perception] TRIGGER FIRED for tool={active_tool!r} session={session_id}", flush=True)
        background_tasks.add_task(
            _run_guidance_for_perception,
            pool=pool,
            session_id=session_id,
            active_tool=active_tool,
            observed_at=observed_at,
        )

    return PerceptionStatePersistedResponse(
        status="persisted",
        perception_id=int(perception_id),
        session_id=str(session_id),
        observed_at=str(observed_at),
    )


async def _run_guidance_for_perception(
    *, pool: asyncpg.Pool, session_id: str, active_tool: str, observed_at,
) -> None:
    if not await guidance_trigger_service.try_acquire(session_id):
        return
    try:
        if hasattr(observed_at, "tzinfo") and observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        if hasattr(observed_at, "isoformat"):
            timestamp_str = observed_at.isoformat()
        else:
            timestamp_str = str(observed_at)
        synthetic_command = CommandRequest(
            text=active_tool,
            timestamp=timestamp_str,
            session_id=session_id,
        )
        task_id = str(uuid.uuid4())
        await safe_run_week2_command_pipeline(
            pool=pool,
            task_id=task_id,
            command=synthetic_command,
        )
    finally:
        guidance_trigger_service.release(session_id)
