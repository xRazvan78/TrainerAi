import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Request, status

from app.models.command_models import CommandAcceptedResponse, CommandRequest
from app.services.command_pipeline_service import safe_run_week2_command_pipeline


router = APIRouter(prefix="/api", tags=["command"])


async def process_command_placeholder(
    task_id: str,
    payload: CommandRequest,
    pool: Optional[asyncpg.Pool],
) -> None:
    if pool is None:
        await asyncio.sleep(0)
        return

    await safe_run_week2_command_pipeline(
        pool=pool,
        task_id=task_id,
        command=payload,
    )


def _utc_now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post(
    "/command",
    response_model=CommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def command_endpoint(payload: CommandRequest, request: Request) -> CommandAcceptedResponse:
    task_id = str(uuid4())
    pool = getattr(request.app.state, "db_pool", None)
    asyncio.create_task(process_command_placeholder(task_id=task_id, payload=payload, pool=pool))

    return CommandAcceptedResponse(
        status="accepted",
        task_id=task_id,
        session_id=payload.session_id,
        received_at=_utc_now_iso8601(),
    )
