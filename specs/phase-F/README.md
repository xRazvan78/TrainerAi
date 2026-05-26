# Phase F — Full Pipeline Connection (Execution Plan)

## Why this exists

`specs/phase-F-full-pipeline-connection.md` sketches the end-to-end flow
but assumes a lot of backend work that has, in fact, already shipped in
Phase C. After auditing the code on `feature/phase-f`, the real Phase F
scope is much narrower than the spec suggests: the **backend half of the
loop is complete** and the only missing pieces live in the Tauri overlay.
This execution plan replaces the spec's broad sketch with a concrete,
verified scope split into four sub-phases.

## Context

What already works (do **not** rebuild):

- `trainerAI_backend/app/services/command_pipeline_service.py:19`
  (`run_week2_command_pipeline`) drives the full pipeline: session
  state → RAG → LLM streaming → broadcast → feedback log.
- `trainerAI_backend/app/services/llm_service.py:39`
  (`stream_guidance(...) -> AsyncIterator[str]`) talks to Docker Model
  Runner over SSE and yields tokens.
- `trainerAI_backend/app/services/ws_broadcaster.py` keeps an
  `_active_connections: dict[str, WebSocket]` registry and exposes
  `broadcast_token` / `broadcast_done`, already wired into the pipeline.
- `trainerAI_backend/app/routers/guidance.py:21` —
  `/api/guidance/ws/{session_id}` accept/register/cleanup.
- `trainerAI_overlay/src-tauri/src/capture.rs` — WGC capture +
  `POST /api/perception/state` every ~500 ms (Phase E).
- Existing Tauri commands `start_capture`, `stop_capture`,
  `set_clickthrough` in `commands.rs` (keep). The stale
  `get_ai_advice` stub is removed in F.2.

What is missing (this phase fills it):

1. A Tauri-side WebSocket client that connects to the guidance endpoint
   and forwards each token to the frontend as a Tauri event.
2. A Dioxus listener that subscribes to that event, appends tokens to a
   signal, and re-renders the panel token-by-token.
3. A way to trigger the pipeline from the overlay (a `send_command`
   Tauri command + a button) so the loop is exercisable end-to-end
   without waiting for Phase G's AutoCAD command-line OCR.

After Phase F ships:

- A user clicks "Send: LINE" (or `Invoke-RestMethod`s manually) and
  within ~2–4 s sees Qwen's guidance stream into the overlay panel
  token-by-token.
- If the backend restarts, the overlay reconnects within ~5 s without a
  UI restart.
- Phase E's capture + click-through behavior is unaffected.

## Two reconciliations with the original spec

1. **Perception does NOT trigger the pipeline in Phase F.** The
   spec's data-flow diagram is ambiguous on this. We keep perception as
   a passive frame log (Phase E behavior) and trigger the pipeline only
   from `POST /api/command`. Auto-triggering on every perception POST
   would fire LLM calls 2/sec and duplicate work that Phase G is meant
   to handle (AutoCAD command-line OCR → command text → POST). This
   keeps the trigger surface clean and matches the existing backend
   plumbing.

2. **Dioxus↔Tauri bridge via `__TAURI__.event.listen` in `js_sys::eval`,
   not `tauri-sys`.** The spec mentions both options. We pick raw JS
   interop because (a) it avoids adding `tauri-sys` to the workspace,
   (b) Tauri's `withGlobalTauri: true` is already enabled in
   `tauri.conf.json`, and (c) the surface we need is one `listen` call
   plus a polled inbox — not enough to justify a typed-bindings crate.

Capture cadence, aHash, JPEG quality, and Phase E behavior are not
touched.

## Phase dependency graph

```
F.1 (deps + ws_client) ──► F.2 (lib.rs + commands.rs wiring) ──► F.3 (Dioxus UI) ──► F.4 (verify)
```

F.2 imports the module added in F.1. F.3 listens for the event emitted
by F.1/F.2. F.4 is pure verification.

## Sub-phase index

| File | Phase | Summary |
| ---- | ----- | ------- |
| [01-deps-and-ws-client.md](01-deps-and-ws-client.md) | F.1 | Cargo deps for the overlay; new `ws_client.rs` module that connects, parses envelopes, and emits `guidance-token` events. |
| [02-tauri-wiring.md](02-tauri-wiring.md) | F.2 | Spawn the WS client in `lib.rs::setup`; add `send_command` Tauri command; drop `get_ai_advice` stub. |
| [03-dioxus-ui.md](03-dioxus-ui.md) | F.3 | Rewrite `src/main.rs` to listen for `guidance-token`, stream tokens into a signal, wire buttons. Delete dead `src/renderer/app.rs`. |
| [04-verification-acceptance.md](04-verification-acceptance.md) | F.4 | End-to-end smoke test with manual POST, reconnect test, Phase E regression checks. |

## Definition of done for the whole phase

- POSTing a command (or clicking "Send: LINE" in the overlay) causes
  guidance text to appear in the overlay panel within 5 seconds.
- Tokens stream incrementally (the panel grows char-by-char / chunk-by-
  chunk, not all at once).
- Killing and restarting the backend with the overlay still open: the
  WebSocket reconnects within ~5 s and the next command streams
  normally — no UI restart needed.
- `start_capture` / `stop_capture` still work; Phase E POSTs to
  `/api/perception/state` continue at the existing cadence.
- Cursor click-through behavior outside the panel is unchanged.
- No edits to `trainerAI_backend/`. No new backend deps. No DB changes.

## Out of scope for Phase F

- YOLOv8 / EasyOCR perception (Phase G).
- AutoCAD command-line OCR triggering the pipeline automatically
  (Phase G).
- Multi-session UI (one `SESSION_ID` per overlay process is enough).
- Token-rate / latency metrics in the UI.
- Authentication on the WebSocket (localhost-only).
- Persisting guidance text across overlay restarts.

## Tech stack additions

- Rust (overlay only): `tokio-tungstenite` 0.24
  (`rustls-tls-native-roots`), `futures-util` 0.3.
- Python: none.
- JS: none (uses the global `window.__TAURI__` already exposed by
  `withGlobalTauri: true`).

`reqwest`, `tokio`, `chrono`, `serde`, `serde_json` are already in
`src-tauri/Cargo.toml` from Phase E and are reused.

## Reused existing code

- `reqwest::Client` and the POST pattern in `capture.rs` — the new
  `send_command` Tauri command in F.2 follows the same shape.
- `SESSION_ID` / `BACKEND_URL` env-var reads in `commands.rs:20` — F.2
  adds a `BACKEND_WS_URL` companion that defaults to
  `ws://localhost:8000`, sharing the same `SESSION_ID`.
- The cursor-polling click-through thread in
  `trainerAI_overlay/src-tauri/src/lib.rs` is unrelated and must not be
  touched.
- `tauri.conf.json` is not edited; env vars are read from the process
  environment as in Phase E.
