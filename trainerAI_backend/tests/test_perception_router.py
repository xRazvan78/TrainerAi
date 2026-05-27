"""
Tests for the perception-driven guidance trigger added in Phase H.1.

These complement test_perception_api.py (which tests persistence behaviour)
and focus exclusively on the guidance trigger logic.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.main as main_module
import app.routers.perception as perception_router
from app.services import guidance_trigger_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_OBSERVED_AT = datetime(2026, 4, 22, 10, 0, 0, tzinfo=timezone.utc)

_VALID_PERSISTED = {
    "id": 1,
    "session_id": "default-session",
    "payload": {},
    "observed_at": _VALID_OBSERVED_AT,
    "created_at": _VALID_OBSERVED_AT,
}

_PERCEPTION_PAYLOAD = {
    "session_id": "default-session",
    "timestamp": "2026-04-22T10:00:00Z",
    "elements": [
        {
            "label": "command_line",
            "bbox": [0, 170, 200, 200],
            "text": "LINE",
            "confidence": 1.0,
        }
    ],
}

_PERCEPTION_PAYLOAD_NO_TOOL = {
    "session_id": "default-session",
    "timestamp": "2026-04-22T10:00:00Z",
    "elements": [],
}


async def _noop_lifespan(_: FastAPI) -> None:
    return None


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_module, "startup_database", _noop_lifespan)
    monkeypatch.setattr(main_module, "shutdown_database", _noop_lifespan)
    app = main_module.create_app()
    app.state.db_pool = object()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Autouse fixture — reset module-level trigger state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_trigger_state():
    guidance_trigger_service._last_triggered_tool.clear()
    guidance_trigger_service._inflight.clear()
    yield
    guidance_trigger_service._last_triggered_tool.clear()
    guidance_trigger_service._inflight.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_trigger_fires_on_new_tool(monkeypatch) -> None:
    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        return dict(_VALID_PERSISTED, session_id=session_id)

    mock_pipeline = AsyncMock()

    monkeypatch.setattr(perception_router.crud, "create_perception_state", fake_create_perception_state)
    monkeypatch.setattr(perception_router, "safe_run_week2_command_pipeline", mock_pipeline)
    monkeypatch.setattr(perception_router, "_extract_active_tool_from_perception", lambda _: "LINE")

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=_PERCEPTION_PAYLOAD)

    assert response.status_code == 201
    mock_pipeline.assert_called_once()
    _, kwargs = mock_pipeline.call_args
    assert kwargs["command"].text == "LINE"
    assert kwargs["command"].session_id == "default-session"
    assert isinstance(kwargs["task_id"], str) and len(kwargs["task_id"]) > 0


def test_trigger_skipped_on_same_tool(monkeypatch) -> None:
    # Mark the tool as already triggered before the request
    guidance_trigger_service.mark_triggered("default-session", "LINE")

    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        return dict(_VALID_PERSISTED, session_id=session_id)

    mock_pipeline = AsyncMock()

    monkeypatch.setattr(perception_router.crud, "create_perception_state", fake_create_perception_state)
    monkeypatch.setattr(perception_router, "safe_run_week2_command_pipeline", mock_pipeline)
    monkeypatch.setattr(perception_router, "_extract_active_tool_from_perception", lambda _: "LINE")

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=_PERCEPTION_PAYLOAD)

    assert response.status_code == 201
    mock_pipeline.assert_not_called()


def test_trigger_skipped_while_in_flight(monkeypatch) -> None:
    # Simulate an in-flight pipeline by patching try_acquire to return False.
    # This avoids cross-event-loop asyncio.Lock issues between the test's outer loop
    # and the anyio loop used internally by TestClient.
    async def fake_try_acquire(session_id: str) -> bool:
        return False

    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        return dict(_VALID_PERSISTED, session_id=session_id)

    mock_pipeline = AsyncMock()

    monkeypatch.setattr(perception_router.crud, "create_perception_state", fake_create_perception_state)
    monkeypatch.setattr(perception_router, "safe_run_week2_command_pipeline", mock_pipeline)
    monkeypatch.setattr(perception_router, "_extract_active_tool_from_perception", lambda _: "LINE")
    monkeypatch.setattr(guidance_trigger_service, "try_acquire", fake_try_acquire)

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=_PERCEPTION_PAYLOAD)

    assert response.status_code == 201
    mock_pipeline.assert_not_called()


def test_no_trigger_when_no_active_tool(monkeypatch) -> None:
    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        return dict(_VALID_PERSISTED, session_id=session_id)

    mock_pipeline = AsyncMock()

    monkeypatch.setattr(perception_router.crud, "create_perception_state", fake_create_perception_state)
    monkeypatch.setattr(perception_router, "safe_run_week2_command_pipeline", mock_pipeline)
    monkeypatch.setattr(perception_router, "_extract_active_tool_from_perception", lambda _: None)

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=_PERCEPTION_PAYLOAD_NO_TOOL)

    assert response.status_code == 201
    mock_pipeline.assert_not_called()


def test_persistence_still_happens_regardless(monkeypatch) -> None:
    # Same tool already triggered — trigger is skipped but persistence must succeed
    guidance_trigger_service.mark_triggered("default-session", "LINE")

    crud_called = []

    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        crud_called.append(True)
        return dict(_VALID_PERSISTED, session_id=session_id)

    mock_pipeline = AsyncMock()

    monkeypatch.setattr(perception_router.crud, "create_perception_state", fake_create_perception_state)
    monkeypatch.setattr(perception_router, "safe_run_week2_command_pipeline", mock_pipeline)
    monkeypatch.setattr(perception_router, "_extract_active_tool_from_perception", lambda _: "LINE")

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=_PERCEPTION_PAYLOAD)

    assert response.status_code == 201
    assert crud_called == [True]
    mock_pipeline.assert_not_called()
