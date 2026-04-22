from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.postgres import shutdown_database, startup_database
from app.routers.db_crud import router as db_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_database(app)
    yield
    await shutdown_database(app)


def create_app() -> FastAPI:
    app = FastAPI(title="trainerAI backend", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(db_router)
    return app


app = create_app()
