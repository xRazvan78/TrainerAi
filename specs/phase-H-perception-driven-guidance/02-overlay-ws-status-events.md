# Phase H.2 — Overlay WebSocket Status Events

## Overview

Make the Rust-side WebSocket client emit a Tauri event whenever it connects to or disconnects from `/api/guidance/ws/{session_id}`. This gives the Dioxus UI (H.3) something concrete to render so a developer running the overlay can immediately distinguish three failure modes: backend down, backend up but WS broken, backend up but no tokens being broadcast.

Pure diagnostic plumbing — does not change connection logic, retry behaviour, or token forwarding.

## Prerequisites

- H.1 merged (optional — H.2 is independent, but verification reads better against a backend that actually streams).

## Goals

- `ws_client.rs` emits a `guidance-ws-status` Tauri event with payload `{ "connected": bool }` immediately after a successful `connect_async` and again when the connection drops.
- No regression in reconnect-backoff behaviour.
- Event payload is stable enough that the Dioxus listener in H.3 can `serde::Deserialize` it directly.

## Technical Design

### New event

- **Name:** `"guidance-ws-status"` (mirrors the existing `"guidance-token"` naming).
- **Payload:** `WsStatus { connected: bool }` — `Clone + Serialize`.

Emit points inside `connect_and_stream`'s outer `loop` in `trainerAI_overlay/src-tauri/src/ws_client.rs`:

1. Immediately after `Ok((mut ws, _)) = connect_async(&url).await` succeeds and the existing `eprintln!("[ws_client] connected …")` log line — emit `WsStatus { connected: true }`.
2. Immediately after the inner `while let Some(Ok(msg)) = ws.next().await { … }` loop exits (i.e. just before the existing "disconnected, reconnecting" log line) — emit `WsStatus { connected: false }`.
3. In the `Err(e) = connect_async(...)` arm (connect failed) — also emit `WsStatus { connected: false }` so the badge stays accurate during the very first failed attempts before any successful connect.

All three emits use `tauri::Emitter::emit(&app, "guidance-ws-status", WsStatus { connected: … })`; ignore the `Result` like the existing `guidance-token` emits do.

### Why not `tauri::async_runtime::spawn` heartbeats?

Tempting, but unnecessary. The backend already sends a `{"type":"ping"}` every 30 s (`ws_broadcaster._PING_INTERVAL_SECONDS`). If the connection silently goes stale, `ws.next().await` will eventually error and the inner loop exits — at which point emit point (2) fires. Heartbeats from the overlay side would only protect against a wedged tokio task, which is not a failure mode we have evidence of.

## Implementation Steps

1. In `trainerAI_overlay/src-tauri/src/ws_client.rs`, add a new struct alongside `GuidanceToken`:
   ```rust
   #[derive(Clone, Serialize)]
   pub struct WsStatus {
       pub connected: bool,
   }
   ```
2. Add the three emits described above. Each is a single line plus the struct literal.
3. `cargo check` from `trainerAI_overlay/src-tauri/`. Fix any rustc complaints (likely none — same `Serialize` derive as `GuidanceToken`).
4. Manual smoke:
   - Start the overlay with the backend down. Observe `[ws_client] connect failed: …` repeating.
   - Start the backend. Observe `[ws_client] connected to ws://localhost:8000/...`.
   - Kill the backend. Observe `[ws_client] disconnected, reconnecting in 1s...`.
   - (H.3 will surface these visually; for H.2 alone, console logs are the proof.)

## File & Directory Changes

| File | Change |
|---|---|
| `trainerAI_overlay/src-tauri/src/ws_client.rs` | Add `WsStatus` struct + 3 `Emitter::emit` calls in `connect_and_stream`. |

No new dependencies. No `Cargo.toml` changes. No changes anywhere else.

## Testing & Validation

No unit tests — `ws_client.rs` has no test coverage today and adding a tokio-tungstenite test harness is out of scope. Validation is manual via the smoke steps above and the visible UI badge introduced in H.3.

If a reviewer wants automated coverage in a future phase, the right shape is a `tokio::test` that stands up a `tokio-tungstenite` server, runs `connect_and_stream` against it, and asserts on emitted events via a custom `tauri::Manager` test harness — explicitly out of scope here.

## Edge Cases & Risks

- **Spurious flapping during backoff.** Each failed `connect_async` will now emit `connected: false`. The UI in H.3 only cares about the most recent value, so repeated `false` emits are harmless. If this gets noisy in console output we can suppress identical consecutive emits — defer until proven annoying.
- **App handle still valid during emit.** `app: tauri::AppHandle` is `Clone`-safe and lives for the lifetime of the spawned task (`tauri::async_runtime::spawn` from `lib.rs:44`). No teardown ordering risk.
- **First emit lands before Dioxus is listening.** Possible if the WS connects before the JS listener registers. Mitigated by the existing `window.__guidance_inbox_init` guard pattern: H.3 will start the connection state at `false` in the signal default, and the next real status (success or fail) will update it within the backoff window (≤ 1 s on the first retry).

## Notes

- Resist adding a `reason: String` field to `WsStatus`. The console logs already carry the reason; the UI badge only needs a boolean. Smaller payload, simpler deserialization, easier to reason about.
- Do **not** also emit a `guidance-token` with `done: true` on disconnect — that would corrupt the streaming state machine in the Dioxus listener. Status is a separate channel.
