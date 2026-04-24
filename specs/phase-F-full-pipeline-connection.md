# Phase F — Full Pipeline Connection (End-to-End)

**Prerequisite for**: Phase G (AutoCAD-specific refinement)  
**Depends on**: Phase C (WebSocket endpoint), Phase E (screen capture working)  
**Estimated effort**: 4–6 hours  
**Outside VS Code work**: Minor (testing with AutoCAD open)

---

## Goal

Connect every piece built in earlier phases into a working end-to-end system:

1. Tauri overlay captures AutoCAD screen → sends to backend
2. Backend processes command → retrieves RAG docs → calls Qwen → streams tokens
3. WebSocket delivers tokens to Tauri overlay
4. Dioxus UI renders guidance text token-by-token in the overlay panel
5. User sees real-time guidance without leaving AutoCAD

---

## Full Data Flow After This Phase

```
User types "LINE" in AutoCAD
         │
         ▼ (detected by AutoCAD command-line OCR — Phase G)
         │ OR: user triggers from overlay UI in early testing
         ▼
POST /api/command  {"text":"LINE","session_id":"...","timestamp":"..."}
         │
         ▼ (background task in FastAPI)
session_state_service → updates active_tool = "LINE", command_sequence
rag_service → embeds "LINE" → pgvector similarity search → retrieves 4 docs
llm_service → builds prompt → streams from Ollama Qwen
         │
         ▼ per-token via WebSocket
ws://localhost:8000/api/guidance/ws/{session_id}
         │
         ▼
Tauri ws_client.rs → receives token → emits Tauri event
         │
         ▼
Dioxus UI (main.rs) → appends token to guidance_text signal → re-renders
         │
         ▼
User sees: "The LINE command draws straight segments. After specifying the
            first point, type the next point coordinates or click. Press
            Enter or Escape to end the command."
```

---

## In VS Code — Tauri Side

### New file: `src-tauri/src/ws_client.rs`

```rust
//! WebSocket client that connects to the FastAPI guidance endpoint
//! and forwards streaming tokens to the Dioxus frontend via Tauri events.

use std::time::Duration;
use tauri::{AppHandle, Manager};
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::StreamExt;

/// Payload emitted to the frontend for each received token.
#[derive(Clone, serde::Serialize)]
pub struct GuidanceToken {
    pub token: String,
    pub done: bool,
}

/// Connect to the backend WebSocket and forward tokens as Tauri events.
/// This should be called once at app startup in a background task.
pub async fn connect_and_stream(app: AppHandle, session_id: String, backend_ws_url: String) {
    let url = format!("{backend_ws_url}/api/guidance/ws/{session_id}");

    loop {
        match connect_async(&url).await {
            Ok((mut ws_stream, _)) => {
                while let Some(Ok(msg)) = ws_stream.next().await {
                    match msg {
                        Message::Text(text) => {
                            // Check if it's a done signal
                            let done = text.contains(r#""type":"done""#);
                            let token = if done {
                                String::new()
                            } else if text.contains(r#""type":"ping""#) {
                                continue;  // ignore keepalive pings
                            } else {
                                text.clone()
                            };

                            let _ = app.emit("guidance-token", GuidanceToken { token, done });
                        }
                        Message::Close(_) => break,
                        _ => {}
                    }
                }
            }
            Err(e) => {
                eprintln!("[ws_client] Connection failed: {e}. Retrying in 5s...");
            }
        }
        // Wait before reconnecting
        tokio::time::sleep(Duration::from_secs(5)).await;
    }
}
```

Add to `Cargo.toml`:

```toml
tokio-tungstenite = { version = "0.24", features = ["native-tls"] }
futures-util = "0.3"
chrono = { version = "0.4", features = ["serde"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

---

### Update `src-tauri/src/lib.rs`

In the `setup` closure where the app is initialised, spawn the WebSocket client:

```rust
// After the existing cursor polling thread setup:
let app_handle_ws = app.handle().clone();
tauri::async_runtime::spawn(async move {
    let session_id = std::env::var("SESSION_ID")
        .unwrap_or_else(|_| uuid::Uuid::new_v4().to_string());
    let backend_ws = std::env::var("BACKEND_WS_URL")
        .unwrap_or_else(|_| "ws://localhost:8000".into());

    crate::ws_client::connect_and_stream(app_handle_ws, session_id, backend_ws).await;
});
```

Add to `Cargo.toml`:

```toml
uuid = { version = "1", features = ["v4"] }
```

---

### Update `src-tauri/src/main.rs`

Register the new module:

```rust
mod capture;
mod ws_client;
```

---

## In VS Code — Dioxus UI (src/main.rs)

Rewrite the main UI to listen for `guidance-token` events and stream text into the panel:

```rust
use dioxus::prelude::*;

fn main() {
    dioxus::launch(App);
}

#[component]
fn App() -> Element {
    let guidance_text = use_signal(|| String::from("Waiting for AutoCAD activity..."));
    let is_streaming = use_signal(|| false);
    let capture_active = use_signal(|| false);

    // Listen for guidance-token events from the Tauri ws_client
    use_effect(move || {
        #[cfg(target_family = "wasm")]
        {
            use wasm_bindgen::prelude::*;
            // Listen for custom events emitted via Tauri's event system
            // The Tauri JS bridge fires window.__TAURI__.event.listen("guidance-token", ...)
            let guidance_text = guidance_text.clone();
            let is_streaming = is_streaming.clone();

            wasm_bindgen_futures::spawn_local(async move {
                // Use Tauri's event API via JS interop
                let _ = js_sys::eval(r#"
                    window.__TAURI__.event.listen('guidance-token', (event) => {
                        window.__dioxus_guidance_token = event.payload;
                    });
                "#);
            });
        }
    });

    rsx! {
        div {
            style: "
                position: fixed;
                top: 20px;
                left: 20px;
                width: 340px;
                background: rgba(15, 23, 42, 0.92);
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 12px;
                padding: 16px;
                font-family: 'Segoe UI', sans-serif;
                color: #e2e8f0;
                backdrop-filter: blur(8px);
            ",

            // Header
            div {
                style: "display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;",
                span {
                    style: "font-size: 13px; font-weight: 600; color: #818cf8;",
                    "TrainerAI"
                }
                div {
                    style: "display: flex; gap: 8px;",
                    // Status dot
                    span {
                        style: if *is_streaming.read() {
                            "width: 8px; height: 8px; border-radius: 50%; background: #34d399; animation: pulse 1s infinite;"
                        } else {
                            "width: 8px; height: 8px; border-radius: 50%; background: #64748b;"
                        }
                    }
                }
            }

            // Guidance text area
            div {
                style: "
                    font-size: 13px;
                    line-height: 1.6;
                    color: #cbd5e1;
                    min-height: 80px;
                    white-space: pre-wrap;
                    word-break: break-word;
                ",
                "{guidance_text}"
            }

            // Controls
            div {
                style: "margin-top: 14px; display: flex; gap: 8px;",
                button {
                    style: "
                        flex: 1;
                        padding: 7px 12px;
                        border-radius: 6px;
                        border: none;
                        background: rgba(99, 102, 241, 0.3);
                        color: #a5b4fc;
                        font-size: 12px;
                        cursor: pointer;
                    ",
                    onclick: move |_| {
                        capture_active.set(!*capture_active.read());
                        // Invoke start_capture or stop_capture Tauri command
                    },
                    if *capture_active.read() { "Stop Capture" } else { "Start Capture" }
                }
                button {
                    style: "
                        padding: 7px 12px;
                        border-radius: 6px;
                        border: 1px solid rgba(99, 102, 241, 0.3);
                        background: transparent;
                        color: #64748b;
                        font-size: 12px;
                        cursor: pointer;
                    ",
                    onclick: move |_| {
                        guidance_text.set(String::from("Waiting for AutoCAD activity..."));
                    },
                    "Clear"
                }
            }
        }
    }
}
```

> **Note on Tauri event bridging**: Dioxus WASM and Tauri communicate via the `__TAURI__` JS bridge. For a cleaner implementation, use the `tauri-sys` crate which provides typed Rust bindings for Tauri's JS API. The JS interop approach above is the quickest path to working code.

Add to `Cargo.toml` (root workspace):

```toml
tauri-sys = { version = "0.3", features = ["event"] }
```

---

## Outside VS Code — End-to-End Test

With everything running (Docker stack + FastAPI backend + Tauri overlay):

1. Open AutoCAD
2. Launch the Tauri overlay (`cargo tauri dev`)
3. Click "Start Capture" in the overlay
4. In the backend terminal, watch for POST requests to `/api/perception/state`
5. Type `LINE` in the AutoCAD command line
6. The backend should: detect the perception change → run pipeline → call Qwen → stream tokens
7. The overlay panel should show streaming guidance text

For manual testing without AutoCAD:

```powershell
# Manually POST a command to trigger the pipeline
$body = @{
    text = "LINE"
    timestamp = (Get-Date -Format o)
    session_id = "default-session"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/command -Body $body -ContentType "application/json"
```

Then watch the WebSocket for tokens (using a browser WebSocket test tool like `wscat`):

```powershell
# Install wscat
npm install -g wscat

# Connect and watch
wscat -c ws://localhost:8000/api/guidance/ws/default-session
```

---

## Environment Variables for Tauri

Add to `src-tauri/tauri.conf.json` under `"env"` (or set in a `.env` file loaded at runtime):

```json
{
  "env": {
    "BACKEND_URL": "http://localhost:8000",
    "BACKEND_WS_URL": "ws://localhost:8000",
    "SESSION_ID": "default-session"
  }
}
```

---

## Latency Budget

| Step                     | Target           | Notes                  |
| ------------------------ | ---------------- | ---------------------- |
| WGC capture + hash       | < 50ms           | Hardware-accelerated   |
| Frame diff check         | < 1ms            | Simple bit operation   |
| POST to backend          | < 30ms           | Localhost              |
| Session state update     | < 10ms           | In-memory + DB write   |
| RAG pgvector query       | < 50ms           | ivfflat index          |
| Qwen first token         | 1–3 seconds      | MoE model, 3.5B active |
| WebSocket delivery       | < 5ms            | Localhost              |
| **Total to first token** | **~2–4 seconds** |                        |

---

## Acceptance Criteria

- [ ] Typing a command in AutoCAD (or manually POSTing) causes guidance to appear in the overlay within 5 seconds
- [ ] Guidance text streams token-by-token (not all at once)
- [ ] The overlay panel clears and re-populates for each new command
- [ ] WebSocket reconnects automatically if the backend restarts
- [ ] Overlay stays click-through when cursor is not over the panel (existing logic preserved)
