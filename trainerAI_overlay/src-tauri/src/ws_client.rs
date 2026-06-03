//! WebSocket client — connects to /api/guidance/ws/{session_id} and emits guidance-token events.

use std::time::Duration;
use futures_util::StreamExt;
use serde::Serialize;
use tokio_tungstenite::{connect_async, tungstenite::Message};

#[derive(Clone, Serialize)]
pub struct GuidanceToken {
    pub token: String,
    pub done: bool,
}

#[derive(Clone, Serialize)]
pub struct WsStatus {
    pub connected: bool,
}

pub async fn connect_and_stream(
    app: tauri::AppHandle,
    session_id: String,
    backend_ws_url: String,
) {
    if !backend_ws_url.starts_with("ws://localhost")
        && !backend_ws_url.starts_with("ws://127.0.0.1")
    {
        eprintln!("[ws_client] BACKEND_WS_URL must point to localhost, got: {backend_ws_url}");
        return;
    }
    if session_id.contains(|c: char| !c.is_ascii_alphanumeric() && c != '-' && c != '_') {
        eprintln!("[ws_client] SESSION_ID contains invalid characters: {session_id}");
        return;
    }

    let mut backoff = Duration::from_secs(1);
    const MAX_BACKOFF: Duration = Duration::from_secs(30);

    loop {
        let url = format!("{backend_ws_url}/api/guidance/ws/{session_id}");
        match connect_async(&url).await {
            Ok((mut ws, _)) => {
                eprintln!("[ws_client] connected to {url}");
                let _ = tauri::Emitter::emit(&app, "guidance-ws-status", WsStatus { connected: true });
                backoff = Duration::from_secs(1); // reset on successful connect
                while let Some(Ok(msg)) = ws.next().await {
                    if let Message::Text(text) = msg {
                        // Try JSON first for control messages
                        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&text) {
                            match val.get("type").and_then(|t| t.as_str()) {
                                Some("done") => {
                                    let _ = tauri::Emitter::emit(
                                        &app,
                                        "guidance-token",
                                        GuidanceToken { token: String::new(), done: true },
                                    );
                                }
                                Some("ping") => {} // keepalive, ignore
                                _ => {
                                    // Unknown JSON shape — treat as token
                                    let _ = tauri::Emitter::emit(
                                        &app,
                                        "guidance-token",
                                        GuidanceToken { token: text, done: false },
                                    );
                                }
                            }
                        } else {
                            // Raw text token (not JSON)
                            let _ = tauri::Emitter::emit(
                                &app,
                                "guidance-token",
                                GuidanceToken { token: text, done: false },
                            );
                        }
                    }
                }
                let _ = tauri::Emitter::emit(&app, "guidance-ws-status", WsStatus { connected: false });
                eprintln!("[ws_client] disconnected, reconnecting in {}s...", backoff.as_secs());
            }
            Err(e) => {
                eprintln!("[ws_client] connect failed: {e}, retrying in {}s...", backoff.as_secs());
                let _ = tauri::Emitter::emit(&app, "guidance-ws-status", WsStatus { connected: false });
            }
        }
        tokio::time::sleep(backoff).await;
        backoff = (backoff * 2).min(MAX_BACKOFF);
    }
}

pub async fn connect_and_stream_plan(
    app: tauri::AppHandle,
    session_id: String,
    backend_ws_url: String,
) {
    if !backend_ws_url.starts_with("ws://localhost")
        && !backend_ws_url.starts_with("ws://127.0.0.1")
    {
        eprintln!("[ws_client] plan BACKEND_WS_URL must point to localhost, got: {backend_ws_url}");
        let _ = tauri::Emitter::emit(&app, "plan-ws-status", WsStatus { connected: false });
        return;
    }
    if session_id.contains(|c: char| !c.is_ascii_alphanumeric() && c != '-' && c != '_') {
        eprintln!("[ws_client] plan SESSION_ID contains invalid characters: {session_id}");
        let _ = tauri::Emitter::emit(&app, "plan-ws-status", WsStatus { connected: false });
        return;
    }

    let mut backoff = Duration::from_secs(1);
    const MAX_BACKOFF: Duration = Duration::from_secs(30);

    loop {
        let url = format!("{backend_ws_url}/api/plan/ws/{session_id}");
        match connect_async(&url).await {
            Ok((mut ws, _)) => {
                eprintln!("[ws_client] connected to {url}");
                let _ = tauri::Emitter::emit(&app, "plan-ws-status", WsStatus { connected: true });
                backoff = Duration::from_secs(1);
                while let Some(Ok(msg)) = ws.next().await {
                    if let Message::Text(text) = msg {
                        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&text) {
                            match val.get("type").and_then(|t| t.as_str()) {
                                Some("token") => {
                                    let _ = tauri::Emitter::emit(&app, "plan-token", &text);
                                }
                                Some("plan") => {
                                    let _ = tauri::Emitter::emit(&app, "plan-update", &text);
                                }
                                Some("step") => {
                                    let _ = tauri::Emitter::emit(&app, "plan-step", &text);
                                }
                                Some("done") => {
                                    let _ = tauri::Emitter::emit(&app, "plan-done", &text);
                                }
                                Some("ping") => {}
                                other => {
                                    eprintln!("[ws_client] plan unrecognised message type: {other:?}");
                                }
                            }
                        } else {
                            eprintln!("[ws_client] plan received non-JSON message: {text}");
                        }
                    }
                }
                let _ = tauri::Emitter::emit(&app, "plan-ws-status", WsStatus { connected: false });
                eprintln!("[ws_client] plan disconnected, reconnecting in {}s...", backoff.as_secs());
            }
            Err(e) => {
                eprintln!("[ws_client] plan connect failed: {e}, retrying in {}s...", backoff.as_secs());
            }
        }
        tokio::time::sleep(backoff).await;
        backoff = (backoff * 2).min(MAX_BACKOFF);
    }
}
