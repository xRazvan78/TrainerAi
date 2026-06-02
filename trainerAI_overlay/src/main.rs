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

#[derive(Deserialize)]
struct WsStatus {
    connected: bool,
}

#[component]
fn App() -> Element {
    let mut guidance_text = use_signal(|| "Așteptând activitate AutoCAD...".to_string());
    let mut is_streaming = use_signal(|| false);
    let mut capturing = use_signal(|| false);
    let mut ws_connected = use_signal(|| false);

    // One-shot: register the JS event listener and inbox.
    // The __guidance_inbox_init guard is unreachable with use_hook (runs exactly once per
    // component instance), but is retained as a safety net against HMR / future remounts.
    use_hook(|| {
        let js = r#"(function () {
  if (window.__guidance_inbox_init) return;
  window.__guidance_inbox_init = true;
  window.__guidance_inbox = [];
  window.__ws_status_inbox = [];
  if (window.__TAURI__ && window.__TAURI__.event) {
    window.__TAURI__.event.listen('guidance-token', function(e) {
      window.__guidance_inbox.push(e.payload);
    });
    window.__TAURI__.event.listen('guidance-ws-status', function(e) {
      window.__ws_status_inbox.push(e.payload);
    });
  }
})();"#;
        let _ = js_sys::eval(js);
    });

    // Polling loop: drain inbox every 50ms, update signals
    use_hook(move || {
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

                let status_result = js_sys::eval(
                    "(function(){ var q = window.__ws_status_inbox || []; window.__ws_status_inbox = []; return JSON.stringify(q); })()"
                );
                if let Ok(val) = status_result {
                    if let Some(s) = val.as_string() {
                        if let Ok(events) = serde_json::from_str::<Vec<WsStatus>>(&s) {
                            if let Some(last) = events.last() {
                                ws_connected.set(last.connected);
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

    let ws_dot_style = if *ws_connected.read() {
        "display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;margin-right:6px;"
    } else {
        "display:inline-block;width:8px;height:8px;border-radius:50%;background:#ef4444;margin-right:6px;"
    };

    let capture_label = if *capturing.read() { "Stop Capture" } else { "Start Capture" };

    rsx! {
        style { "
            html, body, #main, #dioxus-root {{ background: transparent !important; background-color: transparent !important; margin: 0; padding: 0; overflow: hidden; width: 100vw; height: 100vh; }}
            .overlay-container {{ background: rgba(15, 23, 42, 0.72); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-radius: 16px; width: 320px; margin: 20px; padding: 24px; font-family: system-ui, sans-serif; color: white; border: 1px solid rgba(255,255,255,0.18); box-shadow: 0 8px 32px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.05) inset, 0 1px 0 rgba(255,255,255,0.12) inset; }}
            .btn {{ width: 100%; padding: 10px 16px; color: white; border: none; border-radius: 20px; cursor: pointer; font-weight: 600; margin-top: 8px; transition: transform 0.15s, opacity 0.15s; }}
            .btn:hover {{ transform: translateY(-1px); opacity: 0.9; }}
            .btn-blue {{ background: linear-gradient(135deg, #3b82f6, #2563eb); }}
            .btn-blue:hover {{ background: linear-gradient(135deg, #2563eb, #1d4ed8); }}
            .btn-gray {{ background: rgba(71, 85, 105, 0.7); }}
            .btn-gray:hover {{ background: rgba(51, 65, 85, 0.85); }}
            .guidance-panel {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); box-shadow: inset 0 1px 0 rgba(255,255,255,0.08); padding: 15px; border-radius: 10px; margin: 15px 0; min-height: 80px; white-space: pre-wrap; font-size: 0.95rem; line-height: 1.6; }}
            @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
        " }

        div { class: "overlay-container",
            div { style: "display:flex;align-items:center;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:10px;margin-bottom:15px;gap:6px;",
                span { style: "{dot_style}" }
                span { style: "{ws_dot_style}" }
                h2 { style: "margin:0;font-size:1rem;letter-spacing:0.03em;font-weight:600;", "AutoCAD Trainer AI" }
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
