# Phase F.1 — Dependencies and `ws_client.rs`

## Overview

Add the two crates required for a WebSocket client in the Tauri sidecar
and create a new `ws_client` module that connects to the backend's
`/api/guidance/ws/{session_id}` endpoint, parses each frame's JSON
envelope, and emits a `guidance-token` Tauri event for the frontend.

This is the foundation for F.2 (which spawns the client) and F.3 (which
listens to the event). Nothing else can land until F.1 is in.

## Prerequisites

- Phase E shipped — `trainerAI_overlay/src-tauri/Cargo.toml` already has
  `tokio`, `reqwest`, `serde`, `serde_json`, `chrono`.
- Backend `guidance.py` WebSocket endpoint is reachable at
  `ws://localhost:8000/api/guidance/ws/{session_id}` (verified by the
  Phase C completion report).
- The backend envelope format is whatever `guidance.py` sends. Before
  hard-coding parsing, read the router source and confirm shape — the
  graph node `_active_connections` and the broadcaster functions are
  the source of truth.

## Goals

- `tokio-tungstenite` and `futures-util` available in the overlay.
- A new `src-tauri/src/ws_client.rs` module exposing one async fn:

  ```rust
  pub async fn connect_and_stream(
      app: tauri::AppHandle,
      session_id: String,
      backend_ws_url: String,
  );
  ```

- On every text message received, the module emits a Tauri event named
  `guidance-token` whose payload is:

  ```rust
  #[derive(Clone, serde::Serialize)]
  pub struct GuidanceToken {
      pub token: String,   // empty when done = true
      pub done: bool,
  }
  ```

- On disconnect or error, the function logs to stderr and reconnects
  after a 5-second sleep — runs forever.

## Technical Design

### Cargo.toml additions

In `trainerAI_overlay/src-tauri/Cargo.toml`, under `[dependencies]`:

```toml
tokio-tungstenite = { version = "0.24", features = ["rustls-tls-native-roots"] }
futures-util = "0.3"
```

Do **not** add `uuid` — `SESSION_ID` is env-driven and `capture.rs`
already reads it as a plain string. Do **not** add `tauri-sys` — JS
interop in Dioxus is used instead (see F.3).

### Envelope parsing

Phase C's `guidance.py` sends three message types. Verify against the
file before coding, but the expected shapes are:

```jsonc
{"type": "token", "content": "..."}   // streaming chunk
{"type": "done"}                       // stream complete
{"type": "ping"}                       // keepalive — ignore
```

Parse with `serde_json::Value` and field lookups; string-matching on
the raw text (as the original spec sketched) is brittle.

### Reconnect loop shape

```rust
loop {
    let url = format!("{backend_ws_url}/api/guidance/ws/{session_id}");
    match connect_async(&url).await {
        Ok((mut ws, _)) => {
            while let Some(Ok(msg)) = ws.next().await {
                if let Message::Text(text) = msg {
                    // parse envelope, build GuidanceToken, app.emit("guidance-token", payload)
                }
            }
        }
        Err(e) => eprintln!("[ws_client] connect failed: {e}"),
    }
    tokio::time::sleep(Duration::from_secs(5)).await;
}
```

Use `tauri::Emitter::emit` (Tauri v2) — the same API the overlay
already exposes elsewhere. `app.emit("guidance-token", payload)` fires
to every webview window in the app.

## Implementation Steps

1. Open `trainerAI_overlay/src-tauri/Cargo.toml`. Under `[dependencies]`,
   add the two crates from the snippet above. Save.
2. Run `cargo check --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`
   from the project root to confirm the deps resolve before writing
   code.
3. Read `trainerAI_backend/app/routers/guidance.py` end-to-end and
   confirm the exact JSON envelope keys. Adjust the parser in step 5
   if they differ from the assumption above.
4. Create `trainerAI_overlay/src-tauri/src/ws_client.rs`. Add module
   docstring (one line).
5. Define the `GuidanceToken` struct with `derive(Clone, Serialize)`
   and the `connect_and_stream` async fn per the design above. Use
   `use futures_util::StreamExt;` for `ws.next()`. Use
   `tokio_tungstenite::tungstenite::Message`.
6. Do **not** register the module yet — F.2 adds `mod ws_client;` to
   `lib.rs` and spawns the task. F.1 is just file + deps.
7. Run `cargo check` again to confirm the module compiles in
   isolation. The crate won't emit any events yet because nothing
   calls `connect_and_stream`.

## File & Directory Changes

| Path | Change |
| ---- | ------ |
| `trainerAI_overlay/src-tauri/Cargo.toml` | Add `tokio-tungstenite`, `futures-util`. |
| `trainerAI_overlay/src-tauri/src/ws_client.rs` | New file (~50 lines). |

No other files touched in F.1.

## Testing & Validation

- `cargo check --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`
  succeeds.
- `cargo clippy` (if it's part of the project's normal flow) reports
  no new warnings in `ws_client.rs`.
- Visual inspection: the module file compiles, exposes
  `connect_and_stream` and `GuidanceToken`, and contains no `unwrap()`
  on network results.

No runtime test in F.1 — the module is dead code until F.2 wires it
in. End-to-end verification happens in F.4.

## Edge Cases & Risks

- **TLS feature flag.** We use `rustls-tls-native-roots` because the
  project already uses `rustls-tls` on `reqwest` in Phase E. Picking
  the matching feature avoids dragging in two TLS stacks. For
  `ws://localhost` we don't actually need TLS, but the feature flag
  is needed to keep `tokio-tungstenite`'s default-features sane.
- **Envelope format drift.** If `guidance.py` ever changes the key
  names, the parser must be updated. Keep parsing tolerant: missing
  `type` → log and skip; unknown `type` → skip.
- **Backend offline at startup.** First `connect_async` fails fast.
  The 5-second retry loop covers it; the function never returns.
- **Tauri event flood.** Token streams are bursty (tens to hundreds of
  events per command). Tauri's event bus handles this fine on
  localhost; no batching needed at this layer. F.3 polls a JS inbox
  to keep Dioxus re-renders cheap.

## Notes

- `tokio-tungstenite` 0.24 matches the version pinned in the original
  Phase F spec (`Phase F Full Pipeline Connection Spec` node in the
  graph).
- Reuse, do not duplicate, the `reqwest` HTTP path from `capture.rs`
  — `ws_client.rs` is WebSocket-only.
