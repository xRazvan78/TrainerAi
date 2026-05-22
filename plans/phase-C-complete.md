# Phase C — Completion Report

**Date:** 2026-05-21
**Branch:** feature/phase-c
**Tests (post-phase):** 33 passing (27 from prior phases + 6 new across C.1–C.4)

---

## What Shipped

- **C.1 — Config + httpx**: Added `docker_model_runner_url` and `llm_model` pydantic-settings fields to `app/config.py` with safe defaults pointing to the Docker Desktop Model Runner. Added `httpx>=0.27.0` to `requirements.txt`.

- **C.2 — LLM Service**: New `app/services/llm_service.py` — async SSE streaming client for the Qwen 3.5 model (OpenAI-compatible endpoint). Exposes `stream_guidance()` (async generator) and `generate_guidance()` (buffered string wrapper). 60 s client timeout, `temperature=0.3`, `max_tokens=256`. Malformed SSE lines and the `[DONE]` sentinel are handled gracefully.

- **C.3 — WebSocket Router**: New `app/routers/guidance.py` — WebSocket endpoint at `/api/guidance/ws/{session_id}` with 30-second server-side keepalive ping. Module-level `broadcast_token()` and `broadcast_done()` helpers push tokens to connected clients; both are no-ops if no client is connected. Reconnecting with the same `session_id` cleanly closes the prior socket. Registered in `app/main.py`.

- **C.4 — Pipeline Wiring**: `command_pipeline_service.py` now calls `stream_guidance()` after RAG retrieval, broadcasts each token via `broadcast_token()`, and signals completion with `broadcast_done()`. Feedback logging remains a fire-and-forget background task running after streaming. `httpx.HTTPError` added to `safe_run_week2_command_pipeline`'s exception tuple so a downed Model Runner degrades gracefully.

- **C.5 — Verification**: `scripts/smoke_phase_c.py` created as a manual end-to-end smoke runner.

---

## Deviations from Original Spec

1. **`foundation.session` vs `context_packet.session_snapshot`**: The original spec referenced `context_packet.session_snapshot.active_tool`, but the real model uses `ContextPacketFoundation.session: SessionSnapshot`. Implementation uses the correct attribute path (documented in the phase-C README).

2. **`get_settings()` pattern**: The spec snippet showed `from app.config import settings` (module-level singleton), but the codebase convention is `get_settings()` inside functions. Implementation follows the convention.

3. **`.env.example` already had LLM vars**: The file already contained uncommented `DOCKER_MODEL_RUNNER_URL` and `LLM_MODEL` entries from a prior commit, so no change was needed.

---

## Test Count

| Phase | New tests |
|---|---|
| C.1 | 1 (config field defaults) |
| C.2 | 2 (SSE parsing, prompt building) |
| C.3 | 3 (broadcast noop, route registered, broadcast reaches client) |
| C.4 | 0 new; existing E2E test updated with stream/broadcast fakes + 2 new assertions |
| **Total new** | **6** |

---

## Open Issues for Phase F

- **No WS client on Tauri side**: The overlay does not yet consume the WebSocket — deferred to Phase F.
- **Architectural issue (flag for Phase F)**: `command_pipeline_service` imports `broadcast_token`/`broadcast_done` from `app/routers/guidance` (service→router dependency inversion). Recommend extracting to `app/services/ws_broadcaster.py` before Phase F adds more callers.
- **Silent LLM failure on WebSocket**: When the Model Runner is down, `broadcast_done` is never sent, leaving the overlay client in an indefinite wait. A `{"type":"error"}` frame should be sent from the safe-wrapper except path.
- **Test gap**: `test_broadcast_token_reaches_connected_client` takes a no-op fallback path and does not verify actual message delivery. Needs restructuring with anyio or pytest-asyncio.
- **Cold-start latency**: First request after `docker compose up` can take 30–60 s while Qwen loads; subsequent requests are 2–5 s. Not a defect — document in the operator runbook.
- **LLM cost on no-client path**: `stream_guidance` is always called even when no WebSocket client is connected (inference cost wasted). Optimisation deferred to avoid coupling the service to the router's private `_active_connections` dict.
