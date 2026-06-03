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

#[derive(Clone, Deserialize, PartialEq)]
struct ChatMsg {
    role: String,
    content: String,
}

#[derive(Clone, Deserialize, PartialEq)]
struct StepView {
    index: usize,
    instruction: String,
    expected_tool: Option<String>,
    status: String,
}

#[derive(Deserialize)]
struct PlanPayload {
    plan: PlanData,
}

#[derive(Deserialize)]
struct StepPayload {
    current_index: usize,
    plan: PlanData,
}

#[derive(Deserialize)]
struct PlanData {
    steps: Vec<StepView>,
    messages: Vec<ChatMsg>,
    current_index: usize,
}

#[derive(Deserialize)]
struct TokenPayload {
    content: String,
}

#[component]
fn App() -> Element {
    let mut guidance_text = use_signal(|| "Așteptând activitate AutoCAD...".to_string());
    let mut is_streaming = use_signal(|| false);
    let mut capturing = use_signal(|| false);
    let mut ws_connected = use_signal(|| false);

    // Plan Mode signals
    let mut plan_mode = use_signal(|| false);
    let mut plan_input = use_signal(String::new);
    let mut plan_messages = use_signal(Vec::<ChatMsg>::new);
    let mut plan_steps = use_signal(Vec::<StepView>::new);
    let mut plan_current = use_signal(|| 0usize);
    let mut plan_streaming = use_signal(|| false);

    use_hook(|| {
        let js = r#"(function () {
  if (window.__guidance_inbox_init) return;
  window.__guidance_inbox_init = true;
  window.__guidance_inbox = [];
  window.__ws_status_inbox = [];
  window.__plan_token_inbox  = [];
  window.__plan_update_inbox = [];
  window.__plan_step_inbox   = [];
  window.__plan_done_inbox   = [];
  if (window.__TAURI__ && window.__TAURI__.event) {
    window.__TAURI__.event.listen('guidance-token', function(e) {
      window.__guidance_inbox.push(e.payload);
    });
    window.__TAURI__.event.listen('guidance-ws-status', function(e) {
      window.__ws_status_inbox.push(e.payload);
    });
    window.__TAURI__.event.listen('plan-token',  function(e) {
      window.__plan_token_inbox.push(e.payload);
    });
    window.__TAURI__.event.listen('plan-update', function(e) {
      window.__plan_update_inbox.push(e.payload);
    });
    window.__TAURI__.event.listen('plan-step',   function(e) {
      window.__plan_step_inbox.push(e.payload);
    });
    window.__TAURI__.event.listen('plan-done',   function(e) {
      window.__plan_done_inbox.push(e.payload);
    });
  }
})();"#;
        let _ = js_sys::eval(js);
    });

    use_hook(move || {
        wasm_bindgen_futures::spawn_local(async move {
            loop {
                gloo_timers::future::TimeoutFuture::new(50).await;

                // Guidance tokens
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

                // WS status
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

                // Plan tokens
                let plan_token_result = js_sys::eval(
                    "(function(){ var q = window.__plan_token_inbox || []; window.__plan_token_inbox = []; return JSON.stringify(q); })()"
                );
                if let Ok(val) = plan_token_result {
                    if let Some(s) = val.as_string() {
                        if let Ok(raw_tokens) = serde_json::from_str::<Vec<String>>(&s) {
                            for raw in raw_tokens {
                                if let Ok(t) = serde_json::from_str::<TokenPayload>(&raw) {
                                    if !*plan_streaming.read() {
                                        if *plan_mode.read() {
                                            plan_messages.write().push(ChatMsg {
                                                role: "assistant".into(),
                                                content: t.content,
                                            });
                                            plan_streaming.set(true);
                                        }
                                    } else if *plan_mode.read() {
                                        if let Some(last) = plan_messages.write().last_mut() {
                                            last.content.push_str(&t.content);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Plan update (full plan)
                let plan_update_result = js_sys::eval(
                    "(function(){ var q = window.__plan_update_inbox || []; window.__plan_update_inbox = []; return JSON.stringify(q); })()"
                );
                if let Ok(val) = plan_update_result {
                    if let Some(s) = val.as_string() {
                        if let Ok(updates) = serde_json::from_str::<Vec<String>>(&s) {
                            if let Some(last) = updates.last() {
                                if let Ok(p) = serde_json::from_str::<PlanPayload>(last) {
                                    plan_steps.set(p.plan.steps);
                                    plan_current.set(p.plan.current_index);
                                    if let Some(msg) = p.plan.messages.last() {
                                        plan_messages.write().push(msg.clone());
                                    }
                                }
                            }
                        }
                    }
                }

                // Plan step advance
                let plan_step_result = js_sys::eval(
                    "(function(){ var q = window.__plan_step_inbox || []; window.__plan_step_inbox = []; return JSON.stringify(q); })()"
                );
                if let Ok(val) = plan_step_result {
                    if let Some(s) = val.as_string() {
                        if let Ok(steps) = serde_json::from_str::<Vec<String>>(&s) {
                            if let Some(last) = steps.last() {
                                if let Ok(p) = serde_json::from_str::<StepPayload>(last) {
                                    plan_current.set(p.current_index);
                                    plan_steps.set(p.plan.steps);
                                }
                            }
                        }
                    }
                }

                // Plan done
                let plan_done_result = js_sys::eval(
                    "(function(){ var q = window.__plan_done_inbox || []; window.__plan_done_inbox = []; return JSON.stringify(q); })()"
                );
                if let Ok(val) = plan_done_result {
                    if let Some(s) = val.as_string() {
                        if let Ok(dones) = serde_json::from_str::<Vec<serde_json::Value>>(&s) {
                            if !dones.is_empty() {
                                plan_streaming.set(false);
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
    let plan_btn_label = if *plan_mode.read() { "Close Plan" } else { "Plan" };

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
            .btn-green {{ background: linear-gradient(135deg, #22c55e, #16a34a); }}
            .btn-green:hover {{ background: linear-gradient(135deg, #16a34a, #15803d); }}
            .guidance-panel {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); box-shadow: inset 0 1px 0 rgba(255,255,255,0.08); padding: 15px; border-radius: 10px; margin: 15px 0; min-height: 80px; white-space: pre-wrap; font-size: 0.95rem; line-height: 1.6; }}
            .plan-panel {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin: 10px 0; padding: 12px; }}
            .plan-step {{ padding: 4px 0; font-size: 0.85rem; line-height: 1.4; display: flex; align-items: flex-start; gap: 6px; }}
            .plan-step.active {{ color: #4ade80; font-weight: 600; }}
            .plan-step.done {{ color: #64748b; text-decoration: line-through; }}
            .plan-step.pending {{ color: #94a3b8; }}
            .chat-transcript {{ max-height: 160px; overflow-y: auto; margin-bottom: 8px; }}
            .chat-msg {{ padding: 6px 8px; border-radius: 8px; margin: 4px 0; font-size: 0.85rem; line-height: 1.4; }}
            .chat-msg.user {{ background: rgba(59,130,246,0.25); text-align: right; }}
            .chat-msg.assistant {{ background: rgba(255,255,255,0.08); }}
            .plan-input-row {{ display: flex; gap: 6px; margin-top: 8px; }}
            .plan-input-row input {{ flex: 1; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; padding: 8px; color: white; font-size: 0.85rem; }}
            .plan-input-row input::placeholder {{ color: rgba(255,255,255,0.4); }}
            .btn-sm {{ width: auto; padding: 8px 12px; margin-top: 0; font-size: 0.8rem; border-radius: 8px; }}
            .tool-chip {{ font-size: 0.7rem; background: rgba(99,102,241,0.35); border-radius: 4px; padding: 1px 5px; margin-left: 4px; color: #a5b4fc; }}
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
                class: "btn btn-green",
                onclick: move |_| {
                    let active = *plan_mode.read();
                    plan_mode.set(!active);
                    if active {
                        let _ = js_sys::eval("window.__TAURI__.core.invoke('plan_clear', {})");
                        plan_steps.set(vec![]);
                        plan_messages.set(vec![]);
                        plan_current.set(0);
                        plan_streaming.set(false);
                    }
                },
                "{plan_btn_label}"
            }

            button {
                class: "btn btn-gray",
                onclick: move |_| {
                    guidance_text.set("Așteptând activitate AutoCAD...".to_string());
                    is_streaming.set(false);
                },
                "Clear"
            }

            if *plan_mode.read() {
                div { class: "plan-panel",
                    // Checklist
                    {plan_steps.read().iter().map(|step| {
                        let glyph = match step.status.as_str() {
                            "done" => "✓",
                            "active" => "▸",
                            "pending" => "·",
                            other => {
                                eprintln!("[plan] unknown step status: {other}");
                                "·"
                            }
                        };
                        let cls = format!("plan-step {}", step.status);
                        let tool = step.expected_tool.clone().unwrap_or_default();
                        let instruction = step.instruction.clone();
                        rsx! {
                            div { class: "{cls}",
                                span { "{glyph}" }
                                span {
                                    "{instruction}"
                                    if !tool.is_empty() {
                                        span { class: "tool-chip", "{tool}" }
                                    }
                                }
                            }
                        }
                    })}

                    // Chat transcript
                    div { class: "chat-transcript",
                        {plan_messages.read().iter().map(|msg| {
                            let cls = format!("chat-msg {}", msg.role);
                            let content = msg.content.clone();
                            rsx! {
                                div { class: "{cls}", "{content}" }
                            }
                        })}
                    }

                    // Input row
                    div { class: "plan-input-row",
                        input {
                            r#type: "text",
                            placeholder: "Describe your goal or ask a question...",
                            value: "{plan_input}",
                            oninput: move |e| plan_input.set(e.value()),
                        }
                        button {
                            class: "btn btn-blue btn-sm",
                            onclick: move |_| {
                                let text = plan_input.read().clone();
                                if text.trim().is_empty() { return; }
                                plan_messages.write().push(ChatMsg {
                                    role: "user".into(),
                                    content: text.clone(),
                                });
                                let args = serde_json::json!({ "goal": text }).to_string();
                                let msg_args = serde_json::json!({ "text": text }).to_string();
                                let steps_empty = plan_steps.read().is_empty();
                                let js = if steps_empty {
                                    format!("window.__TAURI__.core.invoke('plan_create', {})", args)
                                } else {
                                    format!("window.__TAURI__.core.invoke('plan_message', {})", msg_args)
                                };
                                let _ = js_sys::eval(&js);
                                plan_input.set(String::new());
                            },
                            "Send"
                        }
                        button {
                            class: "btn btn-gray btn-sm",
                            onclick: move |_| {
                                let steps_len = plan_steps.read().len();
                                let current = *plan_current.read();
                                if steps_len > 0 && current < steps_len {
                                    let _ = js_sys::eval("window.__TAURI__.core.invoke('plan_advance', {})");
                                }
                            },
                            "Next"
                        }
                    }
                }
            }
        }
    }
}
