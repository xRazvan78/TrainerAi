# Phase F.2 — Tauri Wiring (`lib.rs` + `commands.rs`)

## Overview

Wire the F.1 module into the Tauri app lifecycle and add a Tauri
command that lets the UI trigger the backend pipeline. After F.2, the
overlay process maintains a live WebSocket to the backend and exposes
a `send_command` command that the Dioxus UI (F.3) will call.

## Prerequisites

- F.1 merged: `ws_client.rs` exists and compiles, `tokio-tungstenite`
  and `futures-util` are in `Cargo.toml`.
- The existing cursor-polling click-through thread in
  `trainerAI_overlay/src-tauri/src/lib.rs` (Phase E) must continue to
  work unchanged.

## Goals

- `lib.rs` declares `mod ws_client;`.
- The Tauri `setup` closure spawns one long-lived async task that
  calls `ws_client::connect_and_stream(app_handle, session_id,
  backend_ws_url)`.
- `session_id` is read from `SESSION_ID` (default `"default-session"`)
  — the same default already used in `commands.rs:20` so capture and
  WS share the same session.
- `backend_ws_url` is read from `BACKEND_WS_URL` (default
  `"ws://localhost:8000"`).
- A new Tauri command `send_command(text: String) -> Result<(),
  String>` POSTs `{text, timestamp, session_id}` to
  `${BACKEND_URL}/api/command` and is registered in the
  `invoke_handler!` macro.
- The deprecated `get_ai_advice` stub is removed from `commands.rs`
  and from the `invoke_handler!` list.

## Technical Design

### `lib.rs` additions

After the existing `mod capture;` / `mod commands;` declarations:

```rust
mod ws_client;
```

Inside `pub fn run()`'s `Builder::default()....setup(|app| { ... })`
closure, after the cursor-polling thread spawn (do not touch it), add:

```rust
let app_handle_ws = app.handle().clone();
tauri::async_runtime::spawn(async move {
    let session_id = std::env::var("SESSION_ID")
        .unwrap_or_else(|_| "default-session".to_string());
    let backend_ws = std::env::var("BACKEND_WS_URL")
        .unwrap_or_else(|_| "ws://localhost:8000".to_string());
    ws_client::connect_and_stream(app_handle_ws, session_id, backend_ws).await;
});
```

Update the `.invoke_handler(tauri::generate_handler![...])` list to
remove `commands::get_ai_advice` and add `commands::send_command`.
Final list (order is cosmetic):

```rust
.invoke_handler(tauri::generate_handler![
    commands::set_clickthrough,
    commands::start_capture,
    commands::stop_capture,
    commands::send_command,
])
```

### `commands.rs` changes

1. Delete the existing `get_ai_advice` function (Phase F replaces it
   with a stream — no longer a request/response shape).
2. Add a new async command:

   ```rust
   #[tauri::command]
   pub async fn send_command(text: String) -> Result<(), String> {
       use chrono::Utc;
       let backend = std::env::var("BACKEND_URL")
           .unwrap_or_else(|_| "http://localhost:8000".to_string());
       let session_id = std::env::var("SESSION_ID")
           .unwrap_or_else(|_| "default-session".to_string());

       let body = serde_json::json!({
           "text": text,
           "timestamp": Utc::now().to_rfc3339(),
           "session_id": session_id,
       });

       let client = reqwest::Client::new();
       client
           .post(format!("{backend}/api/command"))
           .json(&body)
           .send()
           .await
           .map_err(|e| e.to_string())?;
       Ok(())
   }
   ```

3. Reuse the existing `reqwest::Client` import style — match how
   `capture.rs` builds and uses the client. If `capture.rs` keeps a
   long-lived `Client`, use a fresh one here (this is one-shot and not
   on the hot path).

4. Keep the existing `BACKEND_URL` localhost validation pattern from
   `start_capture` if it exists — do not regress on that
   safety check.

## Implementation Steps

1. Open `trainerAI_overlay/src-tauri/src/lib.rs`. Add `mod ws_client;`
   alongside the other module declarations.
2. Locate the `setup` closure. Find the end of the cursor-polling
   thread spawn block. Immediately after it (still inside `setup`),
   add the `tauri::async_runtime::spawn` block from the design above.
3. Update the `invoke_handler!` macro list: remove
   `commands::get_ai_advice`, add `commands::send_command`.
4. Open `trainerAI_overlay/src-tauri/src/commands.rs`. Delete the
   `get_ai_advice` function entirely (no callers remain after step 3).
5. Add the `send_command` function from the design above. Place it
   after `stop_capture` to keep ordering consistent.
6. Run `cargo check --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`.
   Fix any import errors (likely need `use chrono::Utc;` and
   `serde_json` already in deps).
7. Run `cargo tauri dev` once and confirm:
   - The overlay window opens (cursor click-through behavior
     unchanged).
   - The terminal logs `[ws_client] connect failed: ...` (because no
     event listener has been set up in JS yet — that's expected; what
     matters is the spawn happened and the function is looping).
   - Backend logs show a new WebSocket connection accepted at
     `/api/guidance/ws/default-session`.

## File & Directory Changes

| Path | Change |
| ---- | ------ |
| `trainerAI_overlay/src-tauri/src/lib.rs` | Add `mod ws_client;`. Spawn WS task in `setup`. Update `invoke_handler!` list. |
| `trainerAI_overlay/src-tauri/src/commands.rs` | Remove `get_ai_advice`. Add `send_command`. |

No backend changes. No `Cargo.toml` changes (deps came in F.1).

## Testing & Validation

- `cargo check` passes.
- `cargo tauri dev` launches the overlay and the backend logs a
  successful WebSocket accept on `/api/guidance/ws/default-session`.
- Click-through behavior still works: cursor outside the panel passes
  clicks through to AutoCAD; cursor inside the panel captures clicks.
- Invoking `send_command` from the dev console (`window.__TAURI__.core
  .invoke('send_command', { text: 'LINE' })`) returns without error and
  the backend logs the POST being processed. The token stream will
  appear in the overlay's terminal once F.3 emits events to the
  webview — for F.2 alone, it's enough that no error is raised.

## Edge Cases & Risks

- **Backend offline.** The spawned WS task logs and retries; the
  overlay starts normally. The cursor polling thread is independent
  and unaffected.
- **`get_ai_advice` callers.** Confirm via grep that no JS / Dioxus
  code still invokes `get_ai_advice` before deleting it. If F.3 or
  any other file references it, remove that reference in the same
  commit.
- **Session id mismatch.** If the user sets `SESSION_ID` for capture
  but not for the WS spawn (or vice versa), guidance for one session
  is sent and the other one listens. We mitigate by reading the env
  var once and giving both code paths the same default
  (`"default-session"`).
- **AppHandle clone semantics.** `app.handle().clone()` returns a
  cheap handle clone; passing it into `tokio::spawn` is the standard
  Tauri pattern. Do not pass `&AppHandle` references across the
  await boundary.

## Notes

- The original spec uses `uuid::Uuid::new_v4().to_string()` as the
  session-id fallback. We deliberately use the literal
  `"default-session"` so that capture (`commands.rs:20`) and ws_client
  agree without ceremony. UUID-per-session can be added later when
  multi-session UX is needed (out of scope; see README).
