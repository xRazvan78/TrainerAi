import asyncio

from app.models.command_models import CommandRequest
from app.services import session_state_service


def _install_fake_crud(monkeypatch):
    store = {}
    perception_store = {}

    async def fake_get_session(pool, session_id):
        _ = pool
        record = store.get(session_id)
        return None if record is None else dict(record)

    async def fake_create_session(pool, session_id, **kwargs):
        _ = pool
        record = {
            "session_id": session_id,
            "user_id": kwargs.get("user_id"),
            "active_tool": kwargs.get("active_tool"),
            "command_sequence": list(kwargs.get("command_sequence") or []),
            "action_count": int(kwargs.get("action_count") or 0),
            "skill_score": kwargs.get("skill_score"),
            "verbosity_level": kwargs.get("verbosity_level"),
        }
        store[session_id] = record
        return dict(record)

    async def fake_update_session(pool, session_id, **kwargs):
        _ = pool
        record = store.get(session_id)
        if record is None:
            return None

        for key, value in kwargs.items():
            if key == "session_id":
                continue
            if value is not None:
                if key == "command_sequence":
                    record[key] = list(value)
                else:
                    record[key] = value

        store[session_id] = record
        return dict(record)

    async def fake_get_latest_perception_state(pool, session_id):
        _ = pool
        payload = perception_store.get(session_id)
        if payload is None:
            return None
        return {"id": 1, "session_id": session_id, "payload": payload}

    monkeypatch.setattr(session_state_service.crud, "get_session", fake_get_session)
    monkeypatch.setattr(session_state_service.crud, "create_session", fake_create_session)
    monkeypatch.setattr(session_state_service.crud, "update_session", fake_update_session)
    monkeypatch.setattr(
        session_state_service.crud,
        "get_latest_perception_state",
        fake_get_latest_perception_state,
    )

    return {"sessions": store, "perception": perception_store}


def _build_command(text: str, timestamp: str, session_id: str) -> CommandRequest:
    return CommandRequest(text=text, timestamp=timestamp, session_id=session_id)


def test_session_state_creates_if_missing(monkeypatch) -> None:
    _install_fake_crud(monkeypatch)

    command = _build_command(
        text="line draw wall",
        timestamp="2026-04-22T10:00:00Z",
        session_id="session-create",
    )

    snapshot = asyncio.run(session_state_service.update_session_from_command(pool=object(), command=command))

    assert snapshot.session_id == "session-create"
    assert snapshot.action_count == 1
    assert snapshot.active_tool == "LINE"


def test_session_state_updates_action_count(monkeypatch) -> None:
    _install_fake_crud(monkeypatch)

    command_1 = _build_command(
        text="line draw",
        timestamp="2026-04-22T10:00:00Z",
        session_id="session-count",
    )
    command_2 = _build_command(
        text="move object",
        timestamp="2026-04-22T10:01:00Z",
        session_id="session-count",
    )

    asyncio.run(session_state_service.update_session_from_command(pool=object(), command=command_1))
    snapshot = asyncio.run(session_state_service.update_session_from_command(pool=object(), command=command_2))

    assert snapshot.action_count == 2
    assert snapshot.active_tool == "MOVE"


def test_session_state_tracks_recent_commands(monkeypatch) -> None:
    _install_fake_crud(monkeypatch)

    snapshot = None
    for index in range(12):
        command = _build_command(
            text=f"tool{index} execute",
            timestamp=f"2026-04-22T10:{index:02d}:00Z",
            session_id="session-sequence",
        )
        snapshot = asyncio.run(session_state_service.update_session_from_command(pool=object(), command=command))

    assert snapshot is not None
    assert len(snapshot.command_sequence) == 10
    assert snapshot.command_sequence == [f"TOOL{index}" for index in range(2, 12)]


def test_command_context_reads_latest_persisted_perception(monkeypatch) -> None:
    stores = _install_fake_crud(monkeypatch)
    stores["perception"]["session-context"] = {
        "source": "perception_pipeline",
        "elements": [{"label": "button", "text": "Save"}],
    }

    command = _build_command(
        text="save drawing",
        timestamp="2026-04-22T11:00:00Z",
        session_id="session-context",
    )

    foundation = asyncio.run(
        session_state_service.build_context_packet_foundation(
            pool=object(),
            task_id="task-context",
            command=command,
        )
    )

    assert foundation.perception_state == stores["perception"]["session-context"]
