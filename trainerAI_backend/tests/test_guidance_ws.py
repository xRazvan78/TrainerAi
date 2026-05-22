import asyncio

from fastapi.testclient import TestClient
from starlette.routing import WebSocketRoute

from app.main import app
from app.services.ws_broadcaster import _active_connections, broadcast_done, broadcast_token


def test_broadcast_to_disconnected_session_is_noop():
    assert "ghost" not in _active_connections
    asyncio.run(broadcast_token("ghost", "anything"))  # must not raise


def test_websocket_route_registered():
    ws_paths = [
        r.path for r in app.routes
        if isinstance(r, WebSocketRoute)
    ]
    assert "/api/guidance/ws/{session_id}" in ws_paths


def test_broadcast_token_reaches_connected_client():
    with TestClient(app) as client:
        with client.websocket_connect("/api/guidance/ws/test-portal-sess") as ws:
            client.portal.call(broadcast_token, "test-portal-sess", "tok1")
            client.portal.call(broadcast_done, "test-portal-sess")
            assert ws.receive_text() == "tok1"
            assert ws.receive_text() == '{"type":"done"}'
