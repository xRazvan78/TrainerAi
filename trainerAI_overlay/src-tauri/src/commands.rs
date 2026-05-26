use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;
use std::time::Duration;

use serde_json::json;
use tauri::WebviewWindow;
use windows::Win32::Foundation::HWND;

use crate::capture::{capture_window_frame, find_autocad_hwnd, hamming};

static CAPTURE_RUNNING: AtomicBool = AtomicBool::new(false);
static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

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
    if !backend_url.starts_with("http://localhost") && !backend_url.starts_with("http://127.0.0.1") {
        eprintln!("[capture] BACKEND_URL must start with http://localhost or http://127.0.0.1, got: {backend_url}");
        CAPTURE_RUNNING.store(false, Ordering::SeqCst);
        return Err("invalid BACKEND_URL".into());
    }

    let session_id = std::env::var("SESSION_ID")
        .unwrap_or_else(|_| "default-session".into());
    // Temporary stub — Phase F replaces this with real session management.

    tokio::spawn(async move {
        // Guard: reset CAPTURE_RUNNING to false if this task exits for any reason.
        struct RunGuard;
        impl Drop for RunGuard {
            fn drop(&mut self) {
                CAPTURE_RUNNING.store(false, Ordering::SeqCst);
            }
        }
        let _guard = RunGuard;

        let client = HTTP_CLIENT.get_or_init(reqwest::Client::new);
        let mut last_hash: Option<u64> = None;
        let mut interval = tokio::time::interval(Duration::from_millis(500));

        while CAPTURE_RUNNING.load(Ordering::SeqCst) {
            interval.tick().await;

            // find_autocad_hwnd and capture_window_frame both use non-Send types
            // (HWND wraps *mut c_void). Run them on a blocking thread and pass
            // the result back as a Send-safe tuple.
            let frame_result = tokio::task::spawn_blocking(|| {
                let hwnd_isize: isize = find_autocad_hwnd().map(|h| h.0 as isize)?;
                let hwnd = HWND(hwnd_isize as *mut std::ffi::c_void);
                capture_window_frame(hwnd)
            })
            .await;

            let frame = match frame_result {
                Ok(Some(f)) => f,
                _ => continue,
            };

            if let Some(prev) = last_hash {
                if hamming(frame.hash, prev) < 10 {
                    continue;
                }
            }
            last_hash = Some(frame.hash);

            let payload = json!({
                "session_id": session_id,
                "timestamp": chrono::Utc::now().to_rfc3339(),
                "elements": [],
                "source": "wgc_capture",
                "frame_hash": format!("{:016x}", frame.hash),
                "frame_b64": frame.jpeg_b64,
            });

            match client
                .post(format!("{backend_url}/api/perception/state"))
                .json(&payload)
                .send()
                .await
                .and_then(|r| r.error_for_status())
            {
                Ok(_) => {}
                Err(err) => eprintln!("[capture] POST failed: {err}"),
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
pub async fn send_command(text: String) -> Result<(), String> {
    use chrono::Utc;
    let backend = std::env::var("BACKEND_URL")
        .unwrap_or_else(|_| "http://localhost:8000".to_string());
    if !backend.starts_with("http://localhost") && !backend.starts_with("http://127.0.0.1") {
        return Err("invalid BACKEND_URL".into());
    }
    let session_id = std::env::var("SESSION_ID")
        .unwrap_or_else(|_| "default-session".to_string());

    let body = serde_json::json!({
        "text": text,
        "timestamp": Utc::now().to_rfc3339(),
        "session_id": session_id,
    });

    let client = HTTP_CLIENT.get_or_init(reqwest::Client::new);
    client
        .post(format!("{backend}/api/command"))
        .json(&body)
        .send()
        .await
        .and_then(|r| r.error_for_status())
        .map(|_| ())
        .map_err(|e| e.to_string())
}
