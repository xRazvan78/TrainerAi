use dioxus::prelude::*;
use dioxus::document::eval;

fn main() {
    dioxus::launch(app);
}

#[component]
fn app() -> Element {
    let mut status = use_signal(|| "Ready".to_string());
    let mut advice = use_signal(|| String::new());

    rsx! {
        style {
            // Force every background layer to be completely transparent
            "html, body, #main, #dioxus-root {{ background: transparent !important; background-color: transparent !important; margin: 0; padding: 0; overflow: hidden; width: 100vw; height: 100vh; }}"
            
            // Make the UI look like a sleek, modern overlay
            ".overlay-container {{ background-color: rgba(15, 23, 42, 0.85); color: white; padding: 24px; border-radius: 12px; width: 320px; margin: 20px; font-family: system-ui, sans-serif; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); }}"
            
            ".btn-primary {{ width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; }}"
            ".btn-primary:hover {{ background: #2563eb; }}"
        }

        div { class: "overlay-container",
            h2 { style: "margin-top: 0; border-bottom: 1px solid #334155; padding-bottom: 10px;", "AutoCAD Trainer AI" }
            
            div { class: "status-bar", style: "margin-bottom: 15px; color: #4ade80; font-weight: bold;",
                "Status: {status}"
            }

            div { class: "advice-panel", style: "background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-bottom: 20px;",
                h4 { style: "margin-top: 0; color: #fbbf24;", "Sfat AI:" }
                p { style: "margin: 0; font-size: 0.95rem; line-height: 1.4;", "{advice}" }
            }

            button { 
                class: "btn-primary",
                onclick: move |_| async move {
                    if let Ok(msg) = eval("return await window.__TAURI__.core.invoke('start_capture')").join::<String>().await {
                        status.set(msg);
                    }
                },
                "Start Monitorizare"
            }
        }
    }
}