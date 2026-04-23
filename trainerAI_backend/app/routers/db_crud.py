from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.db import crud
from app.db.postgres import get_pool_from_request
from app.db.schema import VECTOR_DIMENSION

router = APIRouter(prefix="/db", tags=["database"])


def get_db_pool(request: Request) -> asyncpg.Pool:
    return get_pool_from_request(request)


class SessionCreate(BaseModel):
    session_id: str
    user_id: str | None = None
    active_tool: str | None = None
    command_sequence: list[str] = Field(default_factory=list)
    action_count: int = 0
    skill_score: float | None = None
    verbosity_level: str | None = None


class SessionUpdate(BaseModel):
    user_id: str | None = None
    active_tool: str | None = None
    command_sequence: list[str] | None = None
    action_count: int | None = None
    skill_score: float | None = None
    verbosity_level: str | None = None


class EmbeddingCreate(BaseModel):
    doc_id: str
    source: str
    content: str
    embedding: list[float] = Field(min_length=VECTOR_DIMENSION, max_length=VECTOR_DIMENSION)


class EmbeddingUpdate(BaseModel):
    source: str | None = None
    content: str | None = None
    embedding: list[float] | None = Field(
        default=None,
        min_length=VECTOR_DIMENSION,
        max_length=VECTOR_DIMENSION,
    )


class SimilarityQuery(BaseModel):
    embedding: list[float] = Field(min_length=VECTOR_DIMENSION, max_length=VECTOR_DIMENSION)
    min_similarity: float = Field(default=0.72, ge=0.0, le=1.0)
    limit: int = Field(default=5, ge=1, le=50)


class TrainingExampleCreate(BaseModel):
    doc_id: str
    session_id: str | None = None
    context_label: str | None = None
    active_tool: str | None = None
    error_type: str | None = None
    guidance_priority: str | None = None
    prompt_used: str | None = None
    response_given: str | None = None
    context_retrieved: list[dict[str, Any]] | None = None
    user_action_after: str | None = None
    outcome: str | None = None
    confidence: float | None = None
    time_to_action_ms: int | None = None
    source: str = "user_confirmed"


class TrainingExampleUpdate(BaseModel):
    session_id: str | None = None
    context_label: str | None = None
    active_tool: str | None = None
    error_type: str | None = None
    guidance_priority: str | None = None
    prompt_used: str | None = None
    response_given: str | None = None
    context_retrieved: list[dict[str, Any]] | None = None
    user_action_after: str | None = None
    outcome: str | None = None
    confidence: float | None = None
    time_to_action_ms: int | None = None
    source: str | None = None


@router.get("/health")
async def db_health(pool: asyncpg.Pool = Depends(get_db_pool)) -> dict[str, str]:
    try:
        async with pool.acquire() as connection:
            await connection.execute("SELECT 1;")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not reachable.") from exc

    return {"status": "ok"}


@router.post("/sessions", status_code=201)
async def create_session_endpoint(
    payload: SessionCreate,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    try:
        return await crud.create_session(
            pool=pool,
            session_id=payload.session_id,
            user_id=payload.user_id,
            active_tool=payload.active_tool,
            command_sequence=payload.command_sequence,
            action_count=payload.action_count,
            skill_score=payload.skill_score,
            verbosity_level=payload.verbosity_level,
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(status_code=409, detail="Session already exists.") from exc


@router.get("/sessions")
async def list_sessions_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    return await crud.list_sessions(pool=pool, limit=limit, offset=offset)


@router.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str, pool: asyncpg.Pool = Depends(get_db_pool)):
    result = await crud.get_session(pool=pool, session_id=session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return result


@router.patch("/sessions/{session_id}")
async def update_session_endpoint(
    session_id: str,
    payload: SessionUpdate,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    if not payload.model_fields_set:
        raise HTTPException(status_code=400, detail="At least one field must be provided.")

    result = await crud.update_session(
        pool=pool,
        session_id=session_id,
        user_id=payload.user_id,
        active_tool=payload.active_tool,
        command_sequence=payload.command_sequence,
        action_count=payload.action_count,
        skill_score=payload.skill_score,
        verbosity_level=payload.verbosity_level,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return result


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session_endpoint(session_id: str, pool: asyncpg.Pool = Depends(get_db_pool)):
    deleted = await crud.delete_session(pool=pool, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return Response(status_code=204)


@router.post("/embeddings", status_code=201)
async def create_embedding_endpoint(
    payload: EmbeddingCreate,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    try:
        return await crud.create_embedding(
            pool=pool,
            doc_id=payload.doc_id,
            source=payload.source,
            content=payload.content,
            embedding=payload.embedding,
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(status_code=409, detail="Embedding doc_id already exists.") from exc


@router.get("/embeddings")
async def list_embeddings_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    return await crud.list_embeddings(pool=pool, limit=limit, offset=offset)


@router.get("/embeddings/{doc_id}")
async def get_embedding_endpoint(doc_id: str, pool: asyncpg.Pool = Depends(get_db_pool)):
    result = await crud.get_embedding(pool=pool, doc_id=doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Embedding not found.")
    return result


@router.patch("/embeddings/{doc_id}")
async def update_embedding_endpoint(
    doc_id: str,
    payload: EmbeddingUpdate,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    if not payload.model_fields_set:
        raise HTTPException(status_code=400, detail="At least one field must be provided.")

    result = await crud.update_embedding(
        pool=pool,
        doc_id=doc_id,
        source=payload.source,
        content=payload.content,
        embedding=payload.embedding,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Embedding not found.")
    return result


@router.delete("/embeddings/{doc_id}", status_code=204)
async def delete_embedding_endpoint(doc_id: str, pool: asyncpg.Pool = Depends(get_db_pool)):
    deleted = await crud.delete_embedding(pool=pool, doc_id=doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Embedding not found.")
    return Response(status_code=204)


@router.post("/embeddings/query")
async def query_embeddings_endpoint(
    payload: SimilarityQuery,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    try:
        return await crud.query_similar_embeddings(
            pool=pool,
            embedding=payload.embedding,
            min_similarity=payload.min_similarity,
            limit=payload.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not reachable.") from exc


@router.post("/training-examples", status_code=201)
async def create_training_example_endpoint(
    payload: TrainingExampleCreate,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    try:
        return await crud.create_training_example(
            pool=pool,
            doc_id=payload.doc_id,
            session_id=payload.session_id,
            context_label=payload.context_label,
            active_tool=payload.active_tool,
            error_type=payload.error_type,
            guidance_priority=payload.guidance_priority,
            prompt_used=payload.prompt_used,
            response_given=payload.response_given,
            context_retrieved=payload.context_retrieved,
            user_action_after=payload.user_action_after,
            outcome=payload.outcome,
            confidence=payload.confidence,
            time_to_action_ms=payload.time_to_action_ms,
            source=payload.source,
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(status_code=409, detail="Training example doc_id already exists.") from exc


@router.get("/training-examples")
async def list_training_examples_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    return await crud.list_training_examples(pool=pool, limit=limit, offset=offset)


@router.get("/training-examples/{doc_id}")
async def get_training_example_endpoint(doc_id: str, pool: asyncpg.Pool = Depends(get_db_pool)):
    result = await crud.get_training_example(pool=pool, doc_id=doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Training example not found.")
    return result


@router.patch("/training-examples/{doc_id}")
async def update_training_example_endpoint(
    doc_id: str,
    payload: TrainingExampleUpdate,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    if not payload.model_fields_set:
        raise HTTPException(status_code=400, detail="At least one field must be provided.")

    result = await crud.update_training_example(
        pool=pool,
        doc_id=doc_id,
        session_id=payload.session_id,
        context_label=payload.context_label,
        active_tool=payload.active_tool,
        error_type=payload.error_type,
        guidance_priority=payload.guidance_priority,
        prompt_used=payload.prompt_used,
        response_given=payload.response_given,
        context_retrieved=payload.context_retrieved,
        user_action_after=payload.user_action_after,
        outcome=payload.outcome,
        confidence=payload.confidence,
        time_to_action_ms=payload.time_to_action_ms,
        source=payload.source,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Training example not found.")
    return result


@router.delete("/training-examples/{doc_id}", status_code=204)
async def delete_training_example_endpoint(
    doc_id: str,
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    deleted = await crud.delete_training_example(pool=pool, doc_id=doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Training example not found.")
    return Response(status_code=204)
