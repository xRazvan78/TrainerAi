from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.main as main_module
import app.routers.perception as perception_router


async def _noop_lifespan(_: FastAPI) -> None:
    return None


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_module, "startup_database", _noop_lifespan)
    monkeypatch.setattr(main_module, "shutdown_database", _noop_lifespan)
    app = main_module.create_app()
    app.state.db_pool = object()
    return TestClient(app)


def test_perception_payload_requires_iso_timestamp(monkeypatch) -> None:
    payload = {
        "session_id": "session-iso",
        "timestamp": "22-04-2026 10:00:00",
        "elements": [],
    }

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "timestamp" for item in detail)


def test_perception_payload_requires_timezone_in_timestamp(monkeypatch) -> None:
    payload = {
        "session_id": "session-iso",
        "timestamp": "2026-04-22T10:00:00",
        "elements": [],
    }

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "timestamp" for item in detail)


def test_perception_payload_persisted_jsonb(monkeypatch) -> None:
    captured = {}

    async def fake_create_perception_state(pool, session_id, payload, observed_at):
        captured["pool"] = pool
        captured["session_id"] = session_id
        captured["payload"] = payload
        captured["observed_at"] = observed_at
        return {
            "id": 7,
            "session_id": session_id,
            "payload": payload,
            "observed_at": observed_at,
            "created_at": observed_at,
        }

    monkeypatch.setattr(
        perception_router.crud,
        "create_perception_state",
        fake_create_perception_state,
    )

    payload = {
        "session_id": "session-jsonb",
        "timestamp": "2026-04-22T10:00:00Z",
        "elements": [
            {
                "label": "button",
                "bbox": [10, 20, 110, 80],
                "text": "Login",
                "confidence": 0.95,
            }
        ],
        "source": "perception_pipeline",
        "frame_hash": "frame-abc",
    }

    with _build_client(monkeypatch) as client:
        response = client.post("/api/perception/state", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "persisted"
    assert body["perception_id"] == 7
    assert body["session_id"] == payload["session_id"]

    assert captured["session_id"] == payload["session_id"]
    assert isinstance(captured["payload"], dict)
    assert captured["payload"]["elements"][0]["text"] == "Login"
