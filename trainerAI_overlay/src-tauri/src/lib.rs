pub mod commands;
use tauri::Manager; // <-- Crucial new import to manage windows

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // 1. Find our transparent overlay window
            let window = app.get_webview_window("main").unwrap();
            
            // 2. Tell the OS to let all mouse clicks pass straight through it!
            window.set_ignore_cursor_events(true).unwrap();
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::start_capture,
            commands::get_ai_advice
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}