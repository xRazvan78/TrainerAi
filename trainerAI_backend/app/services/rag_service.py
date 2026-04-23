import asyncio
from typing import Any

import asyncpg

from app.db import crud
from app.models.context_models import ContextPacketFoundation
from app.services.embedder_service import embed_text

DEFAULT_MIN_SIMILARITY = 0.72
DEFAULT_TOP_K = 4
DEFAULT_TOKEN_BUDGET = 1200


def _token_count(text: str) -> int:
    return len(text.split())


def _query_text_from_foundation(foundation: ContextPacketFoundation) -> str:
    sequence = " ".join(foundation.session.command_sequence)
    return (
        f"command:{foundation.command_text} "
        f"active_tool:{foundation.session.active_tool or ''} "
        f"context:{foundation.session.current_context_label} "
        f"history:{sequence}"
    ).strip()


def _apply_token_budget(results: list[dict[str, Any]], token_budget: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    total_tokens = 0

    for item in results:
        content = str(item.get("content") or "")
        item_tokens = _token_count(content)
        if selected and total_tokens + item_tokens > token_budget:
            break
        if not selected and item_tokens > token_budget:
            continue

        selected.append(item)
        total_tokens += item_tokens

    return selected


async def retrieve_context_documents(
    pool: asyncpg.Pool,
    foundation: ContextPacketFoundation,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    top_k: int = DEFAULT_TOP_K,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> list[dict[str, Any]]:
    query_text = _query_text_from_foundation(foundation)
    query_embedding = embed_text(query_text)

    results = await crud.query_similar_embeddings(
        pool=pool,
        embedding=query_embedding,
        min_similarity=min_similarity,
        limit=top_k,
    )
    return _apply_token_budget(results, token_budget)


async def safe_retrieve_context_documents(
    pool: asyncpg.Pool,
    foundation: ContextPacketFoundation,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    top_k: int = DEFAULT_TOP_K,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> list[dict[str, Any]]:
    try:
        return await retrieve_context_documents(
            pool=pool,
            foundation=foundation,
            min_similarity=min_similarity,
            top_k=top_k,
            token_budget=token_budget,
        )
    except (asyncpg.PostgresError, OSError, RuntimeError, asyncio.TimeoutError):
        return []
