use dioxus::prelude::*;
use serde::Deserialize;

fn main() {
    dioxus::launch(App);
}

#[derive(Deserialize)]
struct GuidanceToken {
    token: String,
    done: bool,
}

#[component]
fn App() -> Element {
    let mut guidance_text = use_signal(|| "Așteptând activitate AutoCAD...".to_string());
    let mut is_streaming = use_signal(|| false);
    let mut capturing = use_signal(|| false);

    // One-shot: register the JS event listener and inbox
    use_effect(move || {
        let js = r#"(function () {
  if (window.__guidance_inbox_init) return;
  window.__guidance_inbox_init = true;
  window.__guidance_inbox = [];
  if (window.__TAURI__ && window.__TAURI__.event) {
    window.__TAURI__.event.listen('guidance-token', function(e) {
      window.__guidance_inbox.push(e.payload);
    });
  }
})();"#;
        let _ = js_sys::eval(js);
    });

    // Polling loop: drain inbox every 50ms, update signals
    use_effect(move || {
        wasm_bindgen_futures::spawn_local(async move {
            loop {
                gloo_timers::future::TimeoutFuture::new(50).await;

                let result = js_sys::eval(
                    "(function(){ var q = window.__guidance_inbox || []; window.__guidance_inbox = []; return JSON.stringify(q); })()"
                );

                if let Ok(val) = result {
                    if let Some(s) = val.as_string() {
                        if let Ok(tokens) = serde_json::from_str::<Vec<GuidanceToken>>(&s) {
                            for t in tokens {
                                if t.done {
                                    is_streaming.set(false);
                                } else {
                                    if !*is_streaming.read() {
                                        guidance_text.set(t.token);
                                        is_streaming.set(true);
                                    } else {
                                        guidance_text.write().push_str(&t.token);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        });
    });

    let dot_style = if *is_streaming.read() {
        "display:inline-block;width:10px;height:10px;border-radius:50%;background:#4ade80;animation:pulse 1s infinite;margin-right:8px;"
    } else {
        "display:inline-block;width:10px;height:10px;border-radius:50%;background:#64748b;margin-right:8px;"
    };

    let capture_label = if *capturing.read() { "Stop Capture" } else { "Start Capture" };

    rsx! {
        style { "
            html, body, #main, #dioxus-root {{ background: transparent !important; background-color: transparent !important; margin: 0; padding: 0; overflow: hidden; width: 100vw; height: 100vh; }}
            .overlay-container {{ background-color: rgba(15, 23, 42, 0.85); color: white; padding: 24px; border-radius: 12px; width: 320px; margin: 20px; font-family: system-ui, sans-serif; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); }}
            .btn {{ width: 100%; padding: 10px; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 8px; }}
            .btn-blue {{ background: #3b82f6; }}
            .btn-blue:hover {{ background: #2563eb; }}
            .btn-green {{ background: #22c55e; }}
            .btn-green:hover {{ background: #16a34a; }}
            .btn-gray {{ background: #475569; }}
            .btn-gray:hover {{ background: #334155; }}
            .guidance-panel {{ background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 15px 0; min-height: 80px; white-space: pre-wrap; font-size: 0.95rem; line-height: 1.5; }}
            @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
        " }

        div { class: "overlay-container",
            div { style: "display:flex;align-items:center;border-bottom:1px solid #334155;padding-bottom:10px;margin-bottom:15px;",
                span { style: "{dot_style}" }
                h2 { style: "margin:0;font-size:1rem;", "AutoCAD Trainer AI" }
            }

            div { class: "guidance-panel",
                "{guidance_text}"
            }

            button {
                class: "btn btn-blue",
                onclick: move |_| {
                    let currently_capturing = *capturing.read();
                    let cmd = if currently_capturing { "stop_capture" } else { "start_capture" };
                    capturing.set(!currently_capturing);
                    let js = format!("window.__TAURI__.core.invoke('{cmd}', {{}})");
                    let _ = js_sys::eval(&js);
                },
                "{capture_label}"
            }

            button {
                class: "btn btn-green",
                onclick: move |_| {
                    let _ = js_sys::eval("window.__TAURI__.core.invoke('send_command', { text: 'LINE' })");
                },
                "Send: LINE"
            }

            button {
                class: "btn btn-gray",
                onclick: move |_| {
                    guidance_text.set("Așteptând activitate AutoCAD...".to_string());
                    is_streaming.set(false);
                },
                "Clear"
            }
        }
    }
}
