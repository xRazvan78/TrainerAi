import asyncio

from app.models.command_models import CommandRequest
from app.models.context_models import ContextPacketFoundation, SessionSnapshot
from app.services import command_pipeline_service


def _foundation() -> ContextPacketFoundation:
    return ContextPacketFoundation(
        task_id="task-e2e",
        session_id="session-e2e",
        command_text="line draw",
        command_timestamp="2026-04-23T09:00:00Z",
        session=SessionSnapshot(
            session_id="session-e2e",
            active_tool="LINE",
            command_sequence=["LINE", "MOVE"],
            action_count=2,
            current_context_label="command_active",
        ),
        perception_state={
            "elements": [{"label": "button", "text": "Save"}],
            "source": "perception_pipeline",
        },
    )


def _command() -> CommandRequest:
    return CommandRequest(
        text="line draw",
        timestamp="2026-04-23T09:00:00Z",
        session_id="session-e2e",
    )


def test_e2e_context_logging_with_perception_and_rag(monkeypatch) -> None:
    captured = {"broadcast_tokens": [], "broadcast_done_calls": []}
    scheduled_tasks = []

    async def fake_build_context_packet_foundation(pool, task_id, command):
        _ = pool
        captured["task_id"] = task_id
        captured["command_text"] = command.text
        return _foundation()

    async def fake_safe_retrieve_context_documents(pool, foundation):
        _ = pool
        captured["perception_state"] = foundation.perception_state
        return [{"doc_id": "doc-rag-1", "content": "RAG line tool help"}]

    async def fake_safe_persist_command_feedback(pool, task_id, foundation, retrieved_context):
        _ = pool
        captured["logged_task_id"] = task_id
        captured["logged_session_id"] = foundation.session_id
        captured["logged_context"] = retrieved_context

    async def fake_stream_guidance(command_text, active_tool, context_docs, command_sequence):
        for token in ["Try ", "the ", "LINE ", "tool"]:
            yield token

    async def fake_broadcast_token(session_id, token):
        captured["broadcast_tokens"].append(token)

    async def fake_broadcast_done(session_id):
        captured["broadcast_done_calls"].append(session_id)

    def fake_create_task(coro):
        task = asyncio.get_running_loop().create_task(coro)
        scheduled_tasks.append(task)
        return task

    monkeypatch.setattr(
        command_pipeline_service,
        "build_context_packet_foundation",
        fake_build_context_packet_foundation,
    )
    monkeypatch.setattr(
        command_pipeline_service,
        "safe_retrieve_context_documents",
        fake_safe_retrieve_context_documents,
    )
    monkeypatch.setattr(
        command_pipeline_service.feedback_logger_service,
        "safe_persist_command_feedback",
        fake_safe_persist_command_feedback,
    )
    monkeypatch.setattr(command_pipeline_service, "stream_guidance", fake_stream_guidance)
    monkeypatch.setattr(command_pipeline_service, "broadcast_token", fake_broadcast_token)
    monkeypatch.setattr(command_pipeline_service, "broadcast_done", fake_broadcast_done)
    monkeypatch.setattr(command_pipeline_service.asyncio, "create_task", fake_create_task)

    async def run() -> None:
        await command_pipeline_service.run_week2_command_pipeline(
            pool=object(),
            task_id="task-e2e",
            command=_command(),
        )
        if scheduled_tasks:
            await asyncio.gather(*scheduled_tasks)

    asyncio.run(run())

    assert captured["task_id"] == "task-e2e"
    assert captured["command_text"] == "line draw"
    assert captured["perception_state"] is not None
    assert captured["logged_task_id"] == "task-e2e"
    assert captured["logged_session_id"] == "session-e2e"
    assert captured["logged_context"][0]["doc_id"] == "doc-rag-1"
    assert command_pipeline_service.WEEK2_ERROR_DETECT_ENABLED is False
    assert captured["broadcast_tokens"] == ["Try ", "the ", "LINE ", "tool"]
    assert captured["broadcast_done_calls"] == ["session-e2e"]
