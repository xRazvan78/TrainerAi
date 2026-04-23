import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.db import crud
from app.models.perception_models import PerceptionStatePersistedResponse, PerceptionStateRequest

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
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PerceptionStatePersistedResponse:
    persisted = await crud.create_perception_state(
        pool=pool,
        session_id=payload.session_id,
        payload=payload.model_dump(mode="python"),
        observed_at=payload.timestamp,
    )
    if persisted is None:
        raise HTTPException(status_code=500, detail="Failed to persist perception state.")

    perception_id = persisted.get("id")
    session_id = persisted.get("session_id")
    observed_at = persisted.get("observed_at")
    if perception_id is None or session_id is None or observed_at is None:
        raise HTTPException(status_code=500, detail="Failed to persist perception state.")

    return PerceptionStatePersistedResponse(
        status="persisted",
        perception_id=int(perception_id),
        session_id=str(session_id),
        observed_at=str(observed_at),
    )
