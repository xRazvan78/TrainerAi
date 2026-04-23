import asyncio
from datetime import datetime
from time import perf_counter

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.main as main_module
import app.routers.command as command_router


async def _noop_lifespan(_: FastAPI) -> None:
    return None


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_module, "startup_database", _noop_lifespan)
    monkeypatch.setattr(main_module, "shutdown_database", _noop_lifespan)
    return TestClient(main_module.create_app())


def test_command_payload_requires_text_timestamp_session_id(monkeypatch) -> None:
    with _build_client(monkeypatch) as client:
        response = client.post("/api/command", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    missing_fields = {item["loc"][-1] for item in detail if item["type"] == "missing"}
    assert {"text", "timestamp", "session_id"}.issubset(missing_fields)


def test_command_payload_requires_iso_timestamp(monkeypatch) -> None:
    payload = {
        "text": "draw line",
        "timestamp": "22-04-2026 10:00:00",
        "session_id": "session-123",
    }

    with _build_client(monkeypatch) as client:
        response = client.post("/api/command", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "timestamp" for item in detail)


def test_command_payload_requires_timezone_in_timestamp(monkeypatch) -> None:
    payload = {
        "text": "draw line",
        "timestamp": "2026-04-22T10:00:00",
        "session_id": "session-123",
    }

    with _build_client(monkeypatch) as client:
        response = client.post("/api/command", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "timestamp" for item in detail)


def test_command_endpoint_returns_ack_immediately(monkeypatch) -> None:
    payload = {
        "text": "draw a wall line",
        "timestamp": "2026-04-22T10:00:00Z",
        "session_id": "session-abc",
    }

    started = perf_counter()
    with _build_client(monkeypatch) as client:
        response = client.post("/api/command", json=payload)
    elapsed = perf_counter() - started

    assert response.status_code == 202
    body = response.json()

    assert body["status"] == "accepted"
    assert isinstance(body["task_id"], str)
    assert body["task_id"]
    assert body["session_id"] == payload["session_id"]
    datetime.fromisoformat(body["received_at"].replace("Z", "+00:00"))
    assert elapsed < 0.5


def test_feedback_logger_non_blocking_from_command_ack(monkeypatch) -> None:
    async def fake_slow_process(task_id, payload, pool) -> None:
        _ = (task_id, payload, pool)
        await asyncio.sleep(0.3)

    monkeypatch.setattr(command_router, "process_command_placeholder", fake_slow_process)

    payload = {
        "text": "draw a wall line",
        "timestamp": "2026-04-22T10:00:00Z",
        "session_id": "session-feedback",
    }

    started = perf_counter()
    with _build_client(monkeypatch) as client:
        response = client.post("/api/command", json=payload)
    elapsed = perf_counter() - started

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert elapsed < 0.5


def test_command_ack_then_async_processing_path(monkeypatch) -> None:
    scheduled = {"count": 0}

    class DummyTask:
        def __init__(self, coro):
            self._coro = coro

    def fake_create_task(coro):
        scheduled["count"] += 1
        coro.close()
        return DummyTask(coro)

    monkeypatch.setattr(command_router.asyncio, "create_task", fake_create_task)

    payload = {
        "text": "trim wall",
        "timestamp": "2026-04-22T12:00:00Z",
        "session_id": "session-async-path",
    }

    with _build_client(monkeypatch) as client:
        response = client.post("/api/command", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert scheduled["count"] == 1


def test_command_pipeline_without_error_detect_week2_scope(monkeypatch) -> None:
    payload = {
        "text": "offset wall",
        "timestamp": "2026-04-22T13:00:00Z",
        "session_id": "session-week2-scope",
    }

    with _build_client(monkeypatch) as client:
        response = client.post("/api/command", json=payload)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert "error_type" not in body
    assert "severity" not in body
    assert "error_signal" not in body
