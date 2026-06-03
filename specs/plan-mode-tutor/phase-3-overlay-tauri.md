# Phase 3: Overlay — Tauri Commands & Plan WebSocket Client

## Overview

This phase adds the Rust/Tauri plumbing the Dioxus UI (Phase 4) will drive: four `#[tauri::command]`
functions that POST to the new `/api/plan/*` endpoints, and a second WebSocket client that connects to
the Plan WS and emits typed Tauri events. It mirrors the existing guidance WS client and `send_command`
HTTP command exactly, so it carries low risk.

## Prerequisites

- Phase 2 backend running and reachable at `http://localhost:8000` / `ws://localhost:8000`.
- Familiarity with `trainerAI_overlay/src-tauri/src/commands.rs` (`send_command`, `HTTP_CLIENT`),
  `ws_client.rs` (`connect_and_stream`), and `lib.rs` (setup + `generate_handler!`).

## Goals

- Tauri commands `plan_create`, `plan_message`, `plan_advance`, `plan_clear` POST to the backend.
- A Plan WS client connects to `/api/plan/ws/{session_id}` and emits `plan-token`, `plan-update`,
  `plan-step`, `plan-done` Tauri events.
- `lib.rs` spawns the Plan WS client and registers the new commands.

## Technical Design

### Commands — `src-tauri/src/commands.rs`

Reuse the `HTTP_CLIENT: OnceLock<reqwest::Client>` singleton and the `send_command` shape (read
`BACKEND_URL` and `SESSION_ID` from env, build a JSON body, POST, `error_for_status`).

```rust
#[tauri::command]
pub async fn plan_create(goal: String) -> Result<(), String> {
    post_plan("create", json!({ "session_id": session_id(), "goal": goal })).await
}

#[tauri::command]
pub async fn plan_message(text: String) -> Result<(), String> {
    post_plan("message", json!({ "session_id": session_id(), "text": text })).await
}

#[tauri::command]
pub async fn plan_advance() -> Result<(), String> {
    post_plan("advance", json!({ "session_id": session_id() })).await
}

#[tauri::command]
pub async fn plan_clear() -> Result<(), String> {
    post_plan("clear", json!({ "session_id": session_id() })).await
}
```

Add small private helpers (keep consistent with existing style):

```rust
fn session_id() -> String {
    std::env::var("SESSION_ID").unwrap_or_else(|_| "default-session".into())
}

async fn post_plan(path: &str, body: serde_json::Value) -> Result<(), String> {
    let backend = std::env::var("BACKEND_URL").unwrap_or_else(|_| "http://localhost:8000".into());
    let client = HTTP_CLIENT.get_or_init(reqwest::Client::new);
    client.post(format!("{backend}/api/plan/{path}"))
        .json(&body).send().await
        .and_then(|r| r.error_for_status())
        .map(|_| ()).map_err(|e| e.to_string())
}
```

### Plan WS client — `src-tauri/src/ws_client.rs`

Add `connect_and_stream_plan(app, session_id, backend_ws_url)` mirroring `connect_and_stream`
(exponential backoff 1s→30s, localhost guard). It connects to
`{backend_ws_url}/api/plan/ws/{session_id}` and, on each `Message::Text`, parses JSON and emits by
`type`:

| Incoming `type` | Tauri event | Payload |
|---|---|---|
| `token` | `plan-token` | `{ content: String }` |
| `plan` | `plan-update` | the full `plan` object (serialize through as JSON value/string) |
| `step` | `plan-step` | `{ current_index, plan }` |
| `done` | `plan-done` | `{}` |
| `ping` | (ignored) | — |

Define matching `#[derive(Clone, Serialize)]` payload structs (or forward the raw JSON string as the
payload and let the frontend parse it — choose whichever keeps Phase 4 simplest; forwarding the raw
string for `plan-update`/`plan-step` avoids re-declaring the plan schema in Rust).

### Wiring — `src-tauri/src/lib.rs`

In `setup`, add a second `tauri::async_runtime::spawn` next to the existing guidance WS spawn:

```rust
let app_handle_plan = app.handle().clone();
tauri::async_runtime::spawn(async move {
    let session_id = std::env::var("SESSION_ID").unwrap_or_else(|_| "default-session".into());
    let backend_ws = std::env::var("BACKEND_WS_URL").unwrap_or_else(|_| "ws://localhost:8000".into());
    ws_client::connect_and_stream_plan(app_handle_plan, session_id, backend_ws).await;
});
```

Extend the existing `tauri::generate_handler![...]` to include the four new commands:

```rust
.invoke_handler(tauri::generate_handler![
    commands::set_clickthrough,
    commands::start_capture,
    commands::stop_capture,
    commands::send_command,
    commands::plan_create,
    commands::plan_message,
    commands::plan_advance,
    commands::plan_clear,
])
```

## Implementation Steps

1. Add `session_id()` + `post_plan()` helpers and the four commands to `commands.rs`.
2. Add `connect_and_stream_plan` to `ws_client.rs` (clone `connect_and_stream`, swap path + event names
   + typed dispatch).
3. In `lib.rs`, spawn the Plan WS client and register the four commands.
4. Build: `cd trainerAI_overlay; cargo build` (or `cargo tauri dev`) to confirm it compiles.

## File & Directory Changes

- **Modified:** `src-tauri/src/commands.rs` — four plan commands + helpers.
- **Modified:** `src-tauri/src/ws_client.rs` — `connect_and_stream_plan` + plan event payload structs.
- **Modified:** `src-tauri/src/lib.rs` — spawn Plan WS client + register commands.

## Testing & Validation

- `cargo build` succeeds with no warnings about unused commands (they'll be used in Phase 4).
- Run `cargo tauri dev` with the backend up; check the terminal logs show
  `[ws_client] connected to ws://localhost:8000/api/plan/ws/default-session`.
- Temporarily, you can invoke a command from the webview devtools console:
  `window.__TAURI__.core.invoke('plan_create', { goal: 'draw a hexagon' })` and watch backend logs +
  the `plan-update` event fire (devtools: `window.__TAURI__.event.listen('plan-update', e => console.log(e))`).

## Edge Cases & Risks

- **Two WS clients reconnecting** independently is fine (separate loops, separate registries on the
  backend). Ensure the localhost guard is duplicated in `connect_and_stream_plan`.
- **Arg name mismatch**: Tauri maps JS invoke args to Rust params by name — `plan_create` expects
  `goal`, `plan_message` expects `text`. Phase 4 must pass exactly those keys.
- **reqwest error surfaced as String** → fine for v1; the UI can show a generic failure.

## Notes

- Reused: `HTTP_CLIENT` singleton, `send_command` POST idiom, `connect_and_stream` backoff/guard,
  the env-var conventions (`BACKEND_URL`, `BACKEND_WS_URL`, `SESSION_ID`).
- Forwarding raw JSON strings for `plan-update`/`plan-step` keeps the plan schema defined in exactly one
  place (backend + Dioxus), avoiding a third Rust copy.
