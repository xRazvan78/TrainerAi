import asyncio
import logging

import asyncpg
import httpx

logger = logging.getLogger(__name__)

from app.models.command_models import CommandRequest
from app.services.ws_broadcaster import broadcast_done, broadcast_token
from app.services import feedback_logger_service
from app.services.llm_service import stream_guidance
from app.services.rag_service import safe_retrieve_context_documents
from app.services.session_state_service import build_context_packet_foundation

WEEK2_ERROR_DETECT_ENABLED = False


async def run_week2_command_pipeline(
    pool: asyncpg.Pool,
    task_id: str,
    command: CommandRequest,
) -> None:
    foundation = await build_context_packet_foundation(
        pool=pool,
        task_id=task_id,
        command=command,
    )
    retrieved_context = await safe_retrieve_context_documents(
        pool=pool,
        foundation=foundation,
    )

    context_texts = [doc.get("content", "") for doc in retrieved_context]
    session = foundation.session
    async for token in stream_guidance(
        command_text=foundation.command_text,
        active_tool=session.active_tool,
        context_docs=context_texts,
        command_sequence=session.command_sequence,
    ):
        await broadcast_token(session.session_id, token)
    await broadcast_done(session.session_id)

    _feedback_task = asyncio.create_task(
        feedback_logger_service.safe_persist_command_feedback(
            pool=pool,
            task_id=task_id,
            foundation=foundation,
            retrieved_context=retrieved_context,
        )
    )


async def safe_run_week2_command_pipeline(
    pool: asyncpg.Pool,
    task_id: str,
    command: CommandRequest,
) -> None:
    try:
        await run_week2_command_pipeline(
            pool=pool,
            task_id=task_id,
            command=command,
        )
    except (
        asyncpg.PostgresError,
        OSError,
        RuntimeError,
        asyncio.TimeoutError,
        ValueError,
        TypeError,
        AttributeError,
        httpx.HTTPError,
    ) as exc:
        logger.error("pipeline failed: %s: %s", type(exc).__name__, exc)