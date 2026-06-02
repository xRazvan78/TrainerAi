# Phase H — Perception-Driven Guidance Display (Execution Plan)

## Why this exists

Phases A–G shipped every component of the end-to-end pipeline, but **nothing connects perception ingestion to guidance generation**, so the overlay panel never updates. Verified by tracing the code on `feature/phase-g`:

- `trainerAI_overlay/src-tauri/src/commands.rs::start_capture` posts perception frames to `/api/perception/state` every 500 ms (with aHash dedup).
- `trainerAI_backend/app/routers/perception.py` persists those rows and returns. **It does not call the LLM pipeline.**
- `trainerAI_backend/app/services/command_pipeline_service.py::run_week2_command_pipeline` is the only path that calls `stream_guidance(...)` → `broadcast_token(...)`, and it is wired exclusively to `POST /api/command`.
- `POST /api/command` is invoked only when the user clicks "Send: LINE" in the Dioxus UI (`trainerAI_overlay/src/main.rs:115`).

Result: in the user's intended autonomous-capture workflow, no command is ever sent, so no tokens ever reach the WebSocket, so the overlay stays on the placeholder text forever.

User constraints confirmed at planning time:
- **Scope: auto-capture only.** The manual "Send: LINE" button can stay as-is.
- **Qwen LLM is live** at `http://localhost:12434`. The LLM, RAG, embedder, and WS broadcaster paths are all known-working; this phase does not touch them.

## Context

What already works (do **not** rebuild):

- `trainerAI_backend/app/services/session_state_service.py:19` — `_extract_active_tool_from_perception(state)` already pulls the AutoCAD command from a `command_line` perception element's OCR'd text.
- `trainerAI_backend/app/services/command_pipeline_service.py:55` — `safe_run_week2_command_pipeline(pool, task_id, command)` is the central, error-swallowing entry point used by the command router. Reuse this exact function.
- `trainerAI_backend/app/services/ws_broadcaster.py` — `broadcast_token` / `broadcast_done` already write to the correct per-session WebSocket, and `routers/guidance.py` already accepts and tracks overlay connections by `session_id`.
- `trainerAI_overlay/src-tauri/src/ws_client.rs` — connects to `/api/guidance/ws/{session_id}` on startup, emits Tauri events `guidance-token` with `{token, done}` payloads, has exponential-backoff reconnect.
- `trainerAI_overlay/src/main.rs` — Dioxus UI already subscribes to `guidance-token` via `window.__TAURI__.event.listen`, drains an inbox every 50 ms, accumulates tokens into a signal, and renders them in `div.guidance-panel`.

What is missing (this phase fills it):

1. A **perception → guidance trigger** in the backend: when an ingested perception state yields a new `active_tool`, fire `safe_run_week2_command_pipeline` as a background task on a synthesised `CommandRequest`. De-dup so the same tool isn't re-triggered, and lock per-session so overlapping frames don't pile up overlapping LLM calls.
2. A small **WS-connection-status signal** in the overlay (Rust emits `guidance-ws-status`, Dioxus shows a "WS ●" badge) so verification can distinguish "WebSocket not connected" from "WebSocket connected but no tokens arriving".
3. A one-line **fix for a latent re-spawn leak** in the Dioxus polling effect that re-runs `spawn_local` on every render.

After Phase H ships:

- With the overlay running and AutoCAD open, typing `LINE` at the command prompt causes the panel to replace "Așteptând…" with streaming Qwen guidance within ~1 s of the next captured frame.
- Switching tools (`LINE` → `CIRCLE`) regenerates guidance for the new tool. Staying on the same tool does not re-trigger.
- The "WS ●" badge turns green when the backend WebSocket is up, red otherwise — usable as a live diagnostic during demos.

## One reconciliation with prior phase specs

`specs/phase-F-full-pipeline-connection.md` implied that the perception-state ingestion would itself drive guidance, but the shipped code on `feature/phase-f`/`feature/phase-g` left perception ingestion as a pure-persist operation. Phase H is the small, surgical patch that closes that gap; it does **not** rewrite Phase F's design, and the existing `/api/command` path remains untouched for manual use.

## Phase dependency graph

```
H.1 (backend trigger)
       │
       ├──► H.2 (ws-status events)  ──┐
       │                              │
       └──► H.3 (overlay UI + leak fix) ──► H.4 (verification)
```

H.1 is independent and end-to-end functional on its own (guidance will reach the existing WS path even without H.2/H.3). H.2 and H.3 are diagnostic/quality-of-life work that can be done in parallel after H.1 lands. H.4 verifies the whole chain.

## Sub-phase index

| File | Purpose |
|---|---|
| `01-backend-perception-trigger.md` | Add the perception → guidance bridge and per-session trigger service. |
| `02-overlay-ws-status-events.md` | Emit `guidance-ws-status` events from `ws_client.rs` on connect / disconnect. |
| `03-overlay-ui-status-and-leak-fix.md` | Add WS badge to the Dioxus UI; make the polling loop one-shot. |
| `04-verification-acceptance.md` | End-to-end smoke + pytest commands and acceptance criteria. |

## Definition of done for the whole phase

- Starting `cargo tauri dev` against a running backend and a foreground AutoCAD with a typed `LINE` command produces visible streaming tokens in `div.guidance-panel` without any manual button click.
- Changing the AutoCAD command to `CIRCLE` triggers a second streaming response; re-typing `LINE` does not.
- The new `pytest tests/test_perception_router.py` cases for "trigger fires on new tool", "trigger skipped on same tool", and "trigger skipped while pipeline already in flight" pass, and the rest of the suite stays green.
- The "WS ●" badge accurately reflects WebSocket connection state across a kill/restart of the backend.

## Out of scope for Phase H

- Replacing the in-memory trigger state with Redis or any cross-process store (the backend is single-process today).
- Throttling beyond "active tool changed" (frame-diff dedup in `commands.rs` already keeps the call rate well below the perception cadence).
- Any rework of the manual "Send: LINE" path, the capture loop, the LLM/RAG/embedder services, or the WebSocket broadcaster.
- Persisting "last triggered tool" across backend restarts.
- UX polish beyond the diagnostic WS badge.
