pub mod capture;
pub mod commands;
pub mod ws_client;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();

            // Start fully click-through — the polling thread will disable it
            // only when the cursor is over the interactive panel.
            window.set_ignore_cursor_events(true).unwrap();

            // Spawn a background thread that polls the OS cursor position every 50ms.
            // JS mouse events (onmouseenter/onmouseleave) never fire when OS-level
            // click-through is active, so we must detect hover here in Rust instead.
            let window_clone = window.clone();
            std::thread::spawn(move || {
                loop {
                    std::thread::sleep(std::time::Duration::from_millis(50));

                    if let (Ok(cursor), Ok(win_pos)) = (
                        window_clone.cursor_position(),
                        window_clone.outer_position(),
                    ) {
                        let rel_x = cursor.x - win_pos.x as f64;
                        let rel_y = cursor.y - win_pos.y as f64;

                        // Interactive region is driven dynamically by the frontend via
                        // set_interactive_region — updated when the panel toggles between
                        // full sidebar and minimized square.
                        let (rx, ry, rw, rh) = commands::interactive_rect();
                        let in_panel = (rx..rx + rw).contains(&rel_x) && (ry..ry + rh).contains(&rel_y);

                        let _ = window_clone.set_ignore_cursor_events(!in_panel);
                    }
                }
            });

            let app_handle_ws = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let session_id = std::env::var("SESSION_ID")
                    .unwrap_or_else(|_| "default-session".to_string());
                let backend_ws = std::env::var("BACKEND_WS_URL")
                    .unwrap_or_else(|_| "ws://localhost:8000".to_string());
                ws_client::connect_and_stream(app_handle_ws, session_id, backend_ws).await;
            });

            let app_handle_plan = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let session_id = std::env::var("SESSION_ID")
                    .unwrap_or_else(|_| "default-session".to_string());
                let backend_ws = std::env::var("BACKEND_WS_URL")
                    .unwrap_or_else(|_| "ws://localhost:8000".to_string());
                ws_client::connect_and_stream_plan(app_handle_plan, session_id, backend_ws).await;
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::set_clickthrough,
            commands::start_capture,
            commands::stop_capture,
            commands::send_command,
            commands::plan_create,
            commands::plan_message,
            commands::plan_advance,
            commands::plan_clear,
            commands::set_interactive_region,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
