# Sub-phase C.3 — WebSocket Router (`/api/guidance/ws/{session_id}`)

## Overview

Add the FastAPI WebSocket endpoint that the Tauri overlay will subscribe to in Phase F. One connection per `session_id`, kept alive with a 30-second server-side ping. Expose two module-level helpers (`broadcast_token`, `broadcast_done`) that the command pipeline calls to push tokens out as they arrive from the LLM.

Independent of C.2 — can be built and tested in parallel by a different developer.

## Prerequisites

- C.1 complete (so the codebase has a clean dependency state).
- Familiarity with FastAPI's `WebSocket` / `WebSocketDisconnect` API. No third-party WS library needed; FastAPI/Starlette is sufficient.

## Goals

- A WebSocket endpoint at `ws://<host>/api/guidance/ws/{session_id}` accepts and tracks one connection per session.
- `broadcast_token(session_id, token)` and `broadcast_done(session_id)` push messages to the connected client (no-op if no client connected).
- The endpoint survives 60+ seconds idle (keepalive ping fires at 30 s intervals).
- Re-connecting with the same `session_id` cleanly closes the old socket before replacing it.
- Disconnects do not leak entries in the in-memory registry.

## Technical Design

### File: `trainerAI_backend/app/routers/guidance.py`

```python
"""
WebSocket endpoint for streaming AI guidance to the overlay client.
One connection per session_id. Guidance is pushed as tokens arrive from the LLM.
"""
from __future__ import annotations

import asyncio
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/guidance", tags=["guidance"])

_active_connections: Dict[str, WebSocket] = {}
_PING_INTERVAL_SECONDS = 30


@router.websocket("/ws/{session_id}")
async def guidance_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()

    # If a previous connection for this session is still tracked, close it first.
    existing = _active_connections.get(session_id)
    if existing is not None and existing is not websocket:
        try:
            await existing.close()
        except Exception:
            pass

    _active_connections[session_id] = websocket
    try:
        while True:
            await asyncio.sleep(_PING_INTERVAL_SECONDS)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        # Only clear the registry if we still own the slot (we may have been
        # superseded by a reconnect during the sleep).
        if _active_connections.get(session_id) is websocket:
            _active_connections.pop(session_id, None)


async def broadcast_token(session_id: str, token: str) -> None:
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text(token)
    except Exception:
        _active_connections.pop(session_id, None)


async def broadcast_done(session_id: str) -> None:
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text('{"type":"done"}')
    except Exception:
        _active_connections.pop(session_id, None)
```

### Router registration (`app/main.py`)

Add the import next to the other router imports and call `app.include_router(...)` inside `create_app()`:

```python
from app.routers.guidance import router as guidance_router
...
def create_app() -> FastAPI:
    ...
    app.include_router(guidance_router)
    return app
```

### Design notes

- **String payload conventions**: regular content tokens are sent verbatim (no JSON wrapping); control messages (`ping`, `done`) are sent as JSON objects with a `"type"` field. The overlay client distinguishes them by attempting `JSON.parse` and falling back to "treat as token".
- **Per-session uniqueness**: enforced by the registry's key collision check at accept time. Sending broad concurrent connections is not a supported use case (single user, single overlay).
- **Broadcast helpers swallow exceptions and clean up the registry**: if a client died mid-stream, the next `broadcast_token` removes it without raising into the pipeline.

## Implementation Steps

1. Create `trainerAI_backend/app/routers/guidance.py` with the code above.
2. Edit `trainerAI_backend/app/main.py`: add the `guidance_router` import (next to existing router imports) and `app.include_router(guidance_router)` call (after the other `include_router` calls).
3. Start the server: `uvicorn app.main:app --reload`. Confirm `GET http://localhost:8000/docs` lists the WebSocket route at `/api/guidance/ws/{session_id}`.
4. Create `trainerAI_backend/tests/test_guidance_ws.py` with the tests described in §Testing.
5. Run `pytest tests/test_guidance_ws.py -v`.

## File & Directory Changes

| Path | Change |
|---|---|
| `trainerAI_backend/app/routers/guidance.py` | NEW — WebSocket router and broadcast helpers. |
| `trainerAI_backend/app/main.py` | Import and register `guidance_router`. |
| `trainerAI_backend/tests/test_guidance_ws.py` | NEW — connection + broadcast tests using `TestClient`. |

## Testing & Validation

Use `fastapi.testclient.TestClient`'s synchronous `websocket_connect` context manager. TestClient runs the app on a dedicated event loop, so `broadcast_token` (an `async` function) must be awaited via `asyncio.run` or — preferred — by calling it from within an `async` test that uses `httpx.ASGITransport`. Simpler approach using TestClient:

### `test_broadcast_token_reaches_connected_client`

```python
from fastapi.testclient import TestClient
import asyncio
from app.main import app
from app.routers.guidance import broadcast_token, broadcast_done

client = TestClient(app)
with client.websocket_connect("/api/guidance/ws/sess-1") as ws:
    # Schedule the broadcast on the TestClient's loop via portal:
    client.portal.call(broadcast_token, "sess-1", "Hello")
    client.portal.call(broadcast_token, "sess-1", " world")
    client.portal.call(broadcast_done, "sess-1")
    assert ws.receive_text() == "Hello"
    assert ws.receive_text() == " world"
    assert ws.receive_text() == '{"type":"done"}'
```

(If `client.portal` is unavailable in the installed FastAPI version, fall back to driving the test loop manually with `anyio.from_thread.start_blocking_portal`.)

### `test_broadcast_to_disconnected_session_is_noop`

```python
import asyncio
from app.routers.guidance import broadcast_token, _active_connections
assert "ghost" not in _active_connections
asyncio.run(broadcast_token("ghost", "anything"))  # must not raise
```

### `test_websocket_route_registered_in_openapi`

Use `TestClient(app)`; iterate `app.routes` and assert one of them is a `WebSocketRoute` with `path == "/api/guidance/ws/{session_id}"`. Guards against accidental router-registration regressions.

## Edge Cases & Risks

- **TestClient loop semantics**: `TestClient` runs FastAPI on a worker thread; awaiting our async helpers requires the portal. If the test stack does not expose a portal, the simplest workaround is to send a message *from the WebSocket handler itself* (e.g., a debug endpoint that triggers a broadcast) — but try the portal first; it is supported in fastapi ≥ 0.115 (which the project pins).
- **Idle disconnect by client-side keepalive timeouts**: 30 s ping is below the 60 s default for most browsers / proxies. If the Tauri client uses `tokio-tungstenite` with custom timeouts, the interval may need to drop further — track this in Phase F.
- **Connection leak on server restart**: not a concern; `_active_connections` is process-local and dies with the worker.

## Notes

- Do not introduce a connection-manager class. A flat dict with two helper functions is sufficient for the single-user, single-overlay scope and easier to test.
- The `WebSocketDisconnect` exception is the *only* normal-termination path; any other exception during `send_text` indicates a dead socket and triggers cleanup.
