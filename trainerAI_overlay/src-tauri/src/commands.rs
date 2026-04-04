use tauri::command;

#[command]
pub async fn start_capture() -> Result<String, String> {
    // Aici vei inițializa captura de ecran (WGC)
    println!("Starting screen capture...");
    Ok("Capture started".to_string())
}

#[command]
pub async fn get_ai_advice() -> Result<String, String> {
    // Aici vei apela modelul AI local (Qwen/Granite)
    // Pentru acum returnăm un mock
    Ok("Atenție: Ai desenat pe stratul '0'. Mută pe 'A-WALL'.".to_string())
}