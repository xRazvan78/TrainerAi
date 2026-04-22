import asyncpg
from fastapi import FastAPI, HTTPException, Request

from app.config import get_settings
from app.db.schema import bootstrap_schema


async def create_pool() -> asyncpg.Pool:
    settings = get_settings()
    dsn = settings.resolved_database_url()
    if not dsn:
        raise RuntimeError("DATABASE_URL is empty. Set DATABASE_URL or POSTGRES_* values.")

    return await asyncpg.create_pool(dsn=dsn)


async def startup_database(app: FastAPI) -> None:
    pool = await create_pool()
    await bootstrap_schema(pool)
    app.state.db_pool = pool


async def shutdown_database(app: FastAPI) -> None:
    pool: asyncpg.Pool | None = getattr(app.state, "db_pool", None)
    if pool is not None:
        await pool.close()
        app.state.db_pool = None


def get_pool_from_request(request: Request) -> asyncpg.Pool:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool is not initialized.")
    return pool
