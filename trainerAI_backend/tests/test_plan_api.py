"""
Tests for the /api/plan router — HTTP endpoints and WebSocket connection.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.routing import WebSocketRoute

import app.main as main_module
import app.routers.plan as plan_router_module
import app.routers.perception as perception_router_module
from app.models.plan_models import Plan, PlanStep
from app.services import plan_service
from app.services.plan_broadcaster import _active_connections as plan_ws_registry


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


async def _noop_lifespan(_: FastAPI) -> None:
    return None


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_module, "startup_database", _noop_lifespan)
    monkeypatch.setattr(main_module, "shutdown_database", _noop_lifespan)
    app = main_module.create_app()
    app.state.db_pool = object()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Autouse fixture — reset plan state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_plan_state():
    plan_service._plans.clear()
    plan_ws_registry.clear()
    yield
    plan_service._plans.clear()
    plan_ws_registry.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_plan_create_returns_202(monkeypatch):
    scheduled = {"count": 0}

    def fake_create_task(coro):
        scheduled["count"] += 1
        coro.close()
        return MagicMock()

    monkeypatch.setattr(plan_router_module.asyncio, "create_task", fake_create_task)

    with _build_client(monkeypatch) as client:
        response = client.post(
            "/api/plan/create",
            json={"session_id": "s1", "goal": "draw hexagon"},
        )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "session_id": "s1"}
    assert scheduled["count"] == 1


def test_plan_advance_ok(monkeypatch):
    plan = Plan(
        session_id="s1",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Step 1", expected_tool="POLYGON", status="active"),
            PlanStep(index=1, instruction="Step 2", expected_tool="TRIM", status="pending"),
        ],
        current_index=0,
    )
    plan_service._plans["s1"] = plan

    with _build_client(monkeypatch) as client:
        response = client.post("/api/plan/advance", json={"session_id": "s1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert plan_service._plans["s1"].current_index == 1


def test_plan_clear_ok(monkeypatch):
    plan = Plan(
        session_id="s1",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Step 1", expected_tool="LINE", status="active"),
        ],
        current_index=0,
    )
    plan_service._plans["s1"] = plan

    with _build_client(monkeypatch) as client:
        response = client.post("/api/plan/clear", json={"session_id": "s1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "s1" not in plan_service._plans


def test_plan_ws_accepts_connection(monkeypatch):
    with _build_client(monkeypatch) as client:
        with client.websocket_connect("/api/plan/ws/test-ws-sess") as ws:
            pass  # connection accepted, no exception


def test_perception_with_active_plan_auto_advances(monkeypatch):
    plan = Plan(
        session_id="default-session",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Draw a line", expected_tool="LINE", status="active"),
            PlanStep(index=1, instruction="Trim it", expected_tool="TRIM", status="pending"),
        ],
        current_index=0,
    )
    plan_service._plans["default-session"] = plan

    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        return dict(_VALID_PERSISTED, session_id=session_id)

    mock_pipeline = AsyncMock()
    mock_broadcast = AsyncMock()

    monkeypatch.setattr(
        perception_router_module.crud,
        "create_perception_state",
        fake_create_perception_state,
    )
    monkeypatch.setattr(
        perception_router_module,
        "_extract_active_tool_from_perception",
        lambda _: "LINE",
    )
    monkeypatch.setattr(
        perception_router_module,
        "safe_run_week2_command_pipeline",
        mock_pipeline,
    )
    monkeypatch.setattr(
        perception_router_module.plan_broadcaster,
        "broadcast_step",
        mock_broadcast,
    )

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=_PERCEPTION_PAYLOAD)

    assert response.status_code == 201
    assert plan_service._plans["default-session"].current_index == 1
    mock_pipeline.assert_not_called()
    mock_broadcast.assert_called_once()


def test_plan_message_returns_202(monkeypatch):
    scheduled = {"count": 0}

    def fake_create_task(coro):
        scheduled["count"] += 1
        coro.close()
        return MagicMock()

    monkeypatch.setattr(plan_router_module.asyncio, "create_task", fake_create_task)

    with _build_client(monkeypatch) as client:
        response = client.post(
            "/api/plan/message",
            json={"session_id": "s1", "text": "what is POLYGON?"},
        )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "session_id": "s1"}
    assert scheduled["count"] == 1


def test_advance_manual_last_step_becomes_inactive(monkeypatch):
    plan = Plan(
        session_id="s1",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Only step", expected_tool="LINE", status="active"),
        ],
        current_index=0,
    )
    plan_service._plans["s1"] = plan

    with _build_client(monkeypatch) as client:
        response = client.post("/api/plan/advance", json={"session_id": "s1"})

    assert response.status_code == 200
    assert plan_service._plans["s1"].current_index == 1
    assert plan_service.has_active_plan("s1") is False


def test_perception_with_completed_plan_resumes_reactive_guidance(monkeypatch):
    """When current_index == len(steps), has_active_plan is False and reactive guidance fires."""
    completed_plan = Plan(
        session_id="default-session",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Done step", expected_tool="LINE", status="done"),
        ],
        current_index=1,  # == len(steps) — plan is complete
    )
    plan_service._plans["default-session"] = completed_plan

    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        return dict(_VALID_PERSISTED, session_id=session_id)

    mock_pipeline = AsyncMock()

    monkeypatch.setattr(
        perception_router_module.crud,
        "create_perception_state",
        fake_create_perception_state,
    )
    monkeypatch.setattr(
        perception_router_module,
        "_extract_active_tool_from_perception",
        lambda _: "LINE",
    )
    monkeypatch.setattr(
        perception_router_module,
        "safe_run_week2_command_pipeline",
        mock_pipeline,
    )

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=_PERCEPTION_PAYLOAD)

    assert response.status_code == 201
    # Reactive guidance should have been triggered (plan is complete, not active)
    mock_pipeline.assert_called_once()
