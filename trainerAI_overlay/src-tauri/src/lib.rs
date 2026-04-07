pub mod commands;
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

                        // The overlay panel is in the top-left corner:
                        //   margin 20px + width 320px + padding → x: 0–370
                        //   margin 20px + height ~500px + padding → y: 0–540
                        let in_panel = rel_x >= 0.0 && rel_x < 370.0
                            && rel_y >= 0.0 && rel_y < 540.0;

                        let _ = window_clone.set_ignore_cursor_events(!in_panel);
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::set_clickthrough,
            commands::start_capture,
            commands::get_ai_advice
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}