import asyncio

from app.models.context_models import ContextPacketFoundation, SessionSnapshot
from app.services import rag_service


def _foundation(command_text: str = "line draw") -> ContextPacketFoundation:
    return ContextPacketFoundation(
        task_id="task-1",
        session_id="session-1",
        command_text=command_text,
        command_timestamp="2026-04-22T10:00:00Z",
        session=SessionSnapshot(
            session_id="session-1",
            active_tool="LINE",
            command_sequence=["LINE", "MOVE"],
            action_count=2,
            current_context_label="command_active",
        ),
    )


def test_rag_retrieval_returns_top_k_docs(monkeypatch) -> None:
    async def fake_query_similar_embeddings(pool, embedding, min_similarity, limit):
        _ = (pool, embedding, min_similarity)
        return [
            {"doc_id": f"doc-{index}", "content": f"content {index}", "similarity_score": 0.9}
            for index in range(10)
        ][:limit]

    monkeypatch.setattr(
        rag_service.crud,
        "query_similar_embeddings",
        fake_query_similar_embeddings,
    )

    results = asyncio.run(
        rag_service.retrieve_context_documents(
            pool=object(),
            foundation=_foundation(),
            top_k=4,
        )
    )

    assert len(results) == 4


def test_rag_retrieval_applies_similarity_threshold(monkeypatch) -> None:
    captured = {}

    async def fake_query_similar_embeddings(pool, embedding, min_similarity, limit):
        _ = (pool, embedding, limit)
        captured["min_similarity"] = min_similarity
        return [{"doc_id": "doc-1", "content": "ok", "similarity_score": 0.95}]

    monkeypatch.setattr(
        rag_service.crud,
        "query_similar_embeddings",
        fake_query_similar_embeddings,
    )

    results = asyncio.run(
        rag_service.retrieve_context_documents(
            pool=object(),
            foundation=_foundation(),
            min_similarity=0.81,
            top_k=4,
        )
    )

    assert results
    assert captured["min_similarity"] == 0.81


def test_rag_retrieval_handles_db_failure_non_blocking(monkeypatch) -> None:
    async def fake_query_similar_embeddings(pool, embedding, min_similarity, limit):
        _ = (pool, embedding, min_similarity, limit)
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        rag_service.crud,
        "query_similar_embeddings",
        fake_query_similar_embeddings,
    )

    results = asyncio.run(
        rag_service.safe_retrieve_context_documents(
            pool=object(),
            foundation=_foundation(),
        )
    )

    assert results == []
