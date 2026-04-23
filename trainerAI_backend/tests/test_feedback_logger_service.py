import asyncio
import json

import pytest

from app.models.context_models import ContextPacketFoundation, SessionSnapshot
from app.services import feedback_logger_service


def _foundation(timestamp: str = "2026-04-23T10:00:00Z") -> ContextPacketFoundation:
    return ContextPacketFoundation(
        task_id="task-logger",
        session_id="session-logger",
        command_text="line draw wall",
        command_timestamp=timestamp,
        session=SessionSnapshot(
            session_id="session-logger",
            active_tool="LINE",
            command_sequence=["LINE"],
            action_count=1,
            current_context_label="command_active",
        ),
    )


def test_training_example_logs_context_retrieved_separately(monkeypatch) -> None:
    captured = {}

    async def fake_create_training_example(**kwargs):
        captured.update(kwargs)
        return {"doc_id": kwargs.get("doc_id"), "context_retrieved": kwargs.get("context_retrieved")}

    monkeypatch.setattr(
        feedback_logger_service.crud,
        "create_training_example",
        fake_create_training_example,
    )

    retrieved_context = [{"doc_id": "doc-1", "content": "line command reference"}]

    result = asyncio.run(
        feedback_logger_service.persist_command_feedback(
            pool=object(),
            task_id="task-1",
            foundation=_foundation(),
            retrieved_context=retrieved_context,
        )
    )

    assert result is not None
    assert captured["context_retrieved"] == retrieved_context

    prompt_payload = json.loads(captured["prompt_used"])
    assert prompt_payload["task_id"] == "task-1"
    assert prompt_payload["session_id"] == "session-logger"
    assert "context_retrieved" not in prompt_payload


def test_feedback_logger_persists_iso_timestamp(monkeypatch) -> None:
    captured = {}

    async def fake_create_training_example(**kwargs):
        captured.update(kwargs)
        return {"doc_id": kwargs.get("doc_id")}

    monkeypatch.setattr(
        feedback_logger_service.crud,
        "create_training_example",
        fake_create_training_example,
    )

    foundation = _foundation(timestamp="2026-04-23T10:00:00+00:00")
    asyncio.run(
        feedback_logger_service.persist_command_feedback(
            pool=object(),
            task_id="task-iso",
            foundation=foundation,
            retrieved_context=[],
        )
    )

    payload = json.loads(captured["prompt_used"])
    assert payload["command_timestamp"] == "2026-04-23T10:00:00+00:00"

    with pytest.raises(ValueError):
        asyncio.run(
            feedback_logger_service.persist_command_feedback(
                pool=object(),
                task_id="task-invalid-iso",
                foundation=_foundation(timestamp="2026-04-23T10:00:00"),
                retrieved_context=[],
            )
        )


def test_safe_feedback_logger_swallows_persistence_errors(monkeypatch) -> None:
    async def fake_create_training_example(**kwargs):
        _ = kwargs
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(
        feedback_logger_service.crud,
        "create_training_example",
        fake_create_training_example,
    )

    asyncio.run(
        feedback_logger_service.safe_persist_command_feedback(
            pool=object(),
            task_id="task-safe",
            foundation=_foundation(),
            retrieved_context=[],
        )
    )
