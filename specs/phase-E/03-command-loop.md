# Phase E.3 — Command Loop & Tauri Wiring

## Overview

Replace the stub `start_capture` in
`trainerAI_overlay/src-tauri/src/commands.rs` with a real background
loop that ticks every 500 ms, drives the `capture::*` functions from
E.2, diffs frames, and POSTs changed ones to the backend's
`/api/perception/state` endpoint. Add a `stop_capture` command. Wire the
new module and the new command into `lib.rs`.

After this sub-phase the Tauri app exposes three production commands
(`set_clickthrough`, `start_capture`, `stop_capture`) plus whatever
existed before, and the end-to-end "frame → HTTP POST → DB row" path is
live.

## Prerequisites

- Phase E.1 merged (Cargo dependencies present).
- Phase E.2 merged (`src/capture.rs` exists and is functional).
- Backend reachable at `http://localhost:8000` during testing.
- A session row exists for the configured `SESSION_ID`, or the backend
  accepts unknown session IDs (today
  `crud.create_perception_state` does not require a pre-existing
  session row).

## Goals

- `start_capture()` returns `"started"` and spawns a tokio task that
  loops until `stop_capture()` is called.
- Each tick: find HWND → capture frame → diff against `last_hash` →
  skip if `hamming < 10` → otherwise POST to backend.
- Double-start is a no-op (returns `"already_running"`).
- `stop_capture()` flips an atomic and the loop exits within ~1 tick.
- The previous mock `get_ai_advice` is replaced with a one-line
  deprecation stub (Phase F replaces it with a WebSocket client).
- `lib.rs` exposes the new module and registers `stop_capture` in
  `invoke_handler`.

## Technical Design

### `commands.rs` — full rewrite

```rust
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use serde_json::json;
use tauri::WebviewWindow;

use crate::capture::{capture_window_frame, find_autocad_hwnd, hamming};

static CAPTURE_RUNNING: AtomicBool = AtomicBool::new(false);

#[tauri::command]
pub fn set_clickthrough(window: WebviewWindow, enabled: bool) -> Result<(), String> {
    window.set_ignore_cursor_events(enabled).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn start_capture() -> Result<String, String> {
    if CAPTURE_RUNNING.swap(true, Ordering::SeqCst) {
        return Ok("already_running".into());
    }

    let backend_url = std::env::var("BACKEND_URL")
        .unwrap_or_else(|_| "http://localhost:8000".into());
    let session_id = std::env::var("SESSION_ID")
        .unwrap_or_else(|_| "default-session".into());

    tokio::spawn(async move {
        let client = reqwest::Client::new();
        let mut last_hash: u64 = 0;
        let mut interval = tokio::time::interval(Duration::from_millis(500));

        while CAPTURE_RUNNING.load(Ordering::SeqCst) {
            interval.tick().await;

            let Some(hwnd) = find_autocad_hwnd() else { continue };
            let Some(frame) = capture_window_frame(hwnd).await else { continue };

            if last_hash != 0 && hamming(frame.hash, last_hash) < 10 {
                continue;
            }
            last_hash = frame.hash;

            let payload = json!({
                "session_id": session_id,
                "timestamp": chrono::Utc::now().to_rfc3339(),
                "elements": [],
                "source": "wgc_capture",
                "frame_hash": format!("{:016x}", frame.hash),
                "frame_b64": frame.jpeg_b64,
            });

            if let Err(err) = client
                .post(format!("{backend_url}/api/perception/state"))
                .json(&payload)
                .send()
                .await
            {
                eprintln!("[capture] POST failed: {err}");
            }
        }
    });

    Ok("started".into())
}

#[tauri::command]
pub fn stop_capture() -> String {
    CAPTURE_RUNNING.store(false, Ordering::SeqCst);
    "stopped".into()
}

#[tauri::command]
pub async fn get_ai_advice() -> Result<String, String> {
    // Deprecated in Phase E; Phase F replaces this with a WebSocket client
    // streaming guidance from /api/guidance/ws/{session_id}.
    Ok("get_ai_advice is deprecated — Phase F wires WebSocket streaming.".into())
}
```

Design choices worth calling out:

- `last_hash == 0` is treated as "first frame ever" and is never
  filtered. Without this guard the very first POST could be skipped
  whenever `frame.hash` happens to be < 10 bits away from zero.
- The loop reads `CAPTURE_RUNNING` at the top of each iteration so
  `stop_capture` is honoured within one tick.
- POST failures are logged but do not abort the loop — transient
  backend restarts during dev must not require restarting the overlay.
  No retry/backoff is added; that belongs to Phase F.
- `set_clickthrough` keeps its existing `WebviewWindow` signature
  (matches the current code at `commands.rs:4`); do not regress to the
  spec's snippet which uses raw `Window` and `GetWindowLongPtrW`.
- Env-var configuration is intentional — Phase E does not need a UI
  for session selection.

### `lib.rs` edits

Two changes inside `trainerAI_overlay/src-tauri/src/lib.rs`:

1. Add `pub mod capture;` next to the existing `pub mod commands;`
   (line 1).
2. Extend the `invoke_handler!` macro list:

```rust
.invoke_handler(tauri::generate_handler![
    commands::set_clickthrough,
    commands::start_capture,
    commands::stop_capture,
    commands::get_ai_advice
])
```

Do not touch the cursor-polling thread (`lib.rs:18`) or any other
existing setup logic.

## Implementation Steps

1. Open `trainerAI_overlay/src-tauri/src/commands.rs`. Replace the
   entire file contents with the code in the Technical Design section.
2. Open `trainerAI_overlay/src-tauri/src/lib.rs`. Add `pub mod capture;`
   on line 2 (right after `pub mod commands;`). Add `commands::stop_capture`
   to the `invoke_handler!` list.
3. Run `cargo build --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`.
   Expect a clean build. If a `tokio::spawn` complaint surfaces about a
   missing runtime, confirm `tokio` features include `rt-multi-thread`
   from E.1.
4. Run `cargo clippy --manifest-path trainerAI_overlay/src-tauri/Cargo.toml -- -D warnings`.
   Fix any warning inside `commands.rs`.
5. (Optional but recommended) Expose the env vars in a `.env.local`
   the developer sources before `cargo tauri dev`:
   ```
   BACKEND_URL=http://localhost:8000
   SESSION_ID=phase-e-dev
   ```
6. Hand off to Phase E.4 for the full end-to-end manual validation.

## File & Directory Changes

| Path | Change |
| ---- | ------ |
| `trainerAI_overlay/src-tauri/src/commands.rs` | Full rewrite — see Technical Design. |
| `trainerAI_overlay/src-tauri/src/lib.rs` | Add `pub mod capture;` and register `commands::stop_capture` in `invoke_handler!`. |

No new files. No deletions.

## Testing & Validation

- `cargo build` clean.
- `cargo clippy -- -D warnings` clean for `commands.rs` and `lib.rs`.
- Launch `cargo tauri dev`. From the overlay UI invoke
  `start_capture`; the dev console should print no panics and the
  backend's uvicorn log should show `POST /api/perception/state 201`
  entries appearing roughly when AutoCAD changes.
- Invoke `stop_capture`; subsequent POST entries must cease within ~1
  second.
- Re-invoke `start_capture`; expect a new burst (the static atomic
  resets cleanly because we set it back to `false` in `stop_capture`).

## Edge Cases & Risks

- **AutoCAD closed mid-loop**: `find_autocad_hwnd` returns `None` →
  the loop sleeps one tick and retries. Correct behaviour.
- **Backend down**: POST returns `Err`, we log and continue. The next
  successful POST sends a fresh `frame_hash`, so the backend does not
  miss state transitions permanently — only the window during downtime.
- **HWND becomes invalid between lookup and capture**: WGC will fail
  the session start; `capture_window_frame` returns `None`; we skip.
- **CAPTURE_RUNNING leaks across panics**: the spawned task is the only
  thing that observes the atomic, and the task only exits via the
  while-condition. A panic inside the loop terminates the task but
  leaves `CAPTURE_RUNNING == true`, blocking restart. Wrap the body in
  `let _ = tokio::task::spawn(async move { ... }).await;` is overkill;
  instead, set `CAPTURE_RUNNING.store(false, ...)` in a `Drop` guard
  struct created at task entry. Document the fix here and implement it.
- **chrono::Utc::now().to_rfc3339()** emits e.g.
  `2026-05-22T13:45:01.123456789+00:00`. The backend validator at
  `perception_models.py:42` accepts `+00:00` offset and the literal
  `T` separator — verified compatible.

## Notes

- The spec's snippet uses `tauri::Window`; that type does not exist on
  Tauri 2 (it is `WebviewWindow`). Stick with `WebviewWindow` to match
  the existing `set_clickthrough` signature.
- Do not register a Tauri-managed state (`tauri::State`) for the
  running flag — a `static AtomicBool` is simpler and sufficient.
