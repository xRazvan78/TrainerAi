# Phase 4: Overlay — Dioxus Plan Panel (chat + live checklist)

## Overview

This phase builds the user-facing Plan Mode UI inside the monolithic Dioxus `App` in
`trainerAI_overlay/src/main.rs`: a **Plan** toggle button, a chat panel (transcript + input + Send +
Next), and a live plan checklist that reflects step statuses. It consumes the Tauri events emitted in
Phase 3 via the existing JS-inbox bridge.

## Prerequisites

- Phase 3 complete (commands registered, Plan WS client emitting `plan-token` / `plan-update` /
  `plan-step` / `plan-done`).
- Understanding of the current `main.rs` patterns: `use_signal` state, the `js_sys::eval` invoke
  pattern, and the `window.__guidance_inbox` listener + 50ms polling loop.

## Goals

- A **Plan** button toggles a Plan panel without disrupting the existing reactive guidance panel.
- The panel shows a chat transcript, a text input with **Send**, and a **Next** button.
- A live checklist renders each step with a status glyph (done ✓ / active ▸ / pending ·).
- Incoming Tauri events update the UI in near real-time.

## Technical Design

### New signals (top of `App`)

```rust
let mut plan_mode      = use_signal(|| false);
let mut plan_input     = use_signal(String::new);
let mut plan_messages  = use_signal(Vec::<ChatMsg>::new);   // {role, content}
let mut plan_steps     = use_signal(Vec::<StepView>::new);  // {index, instruction, expected_tool, status}
let mut plan_current   = use_signal(|| 0usize);
let mut plan_streaming = use_signal(|| false);
```

Define lightweight `#[derive(Clone, Deserialize, PartialEq)] ChatMsg` and `StepView` structs in
`main.rs` matching the backend `Plan`/`PlanStep`/`ChatMessage` JSON field names.

### Event intake (extend the existing JS-inbox bridge)

In the existing `use_hook` that registers `window.__guidance_inbox`, add listeners + buffers for the
plan events:

```js
window.__plan_token_inbox  = [];
window.__plan_update_inbox = [];
window.__plan_step_inbox   = [];
window.__plan_done_inbox   = [];
if (window.__TAURI__ && window.__TAURI__.event) {
  window.__TAURI__.event.listen('plan-token',  e => window.__plan_token_inbox.push(e.payload));
  window.__TAURI__.event.listen('plan-update', e => window.__plan_update_inbox.push(e.payload));
  window.__TAURI__.event.listen('plan-step',   e => window.__plan_step_inbox.push(e.payload));
  window.__TAURI__.event.listen('plan-done',   e => window.__plan_done_inbox.push(e.payload));
}
```

In the existing 50ms polling loop, drain each buffer (same `js_sys::eval` "return JSON, clear array"
trick already used for `__guidance_inbox`) and apply:

- **plan-token**: if not currently streaming, push a new assistant `ChatMsg`; set `plan_streaming=true`;
  append `content` to the last assistant message.
- **plan-update**: parse the full plan → replace `plan_steps`, set `plan_current`, and append the
  assistant's rendered plan summary as a `ChatMsg` (so the plan also appears in chat).
- **plan-step**: update `plan_current` and the per-step `status` (done/active/pending) from the payload.
- **plan-done**: `plan_streaming=false` (end of a chat turn).

### UI — rendering

1. **Plan toggle button** next to "Start Capture", reusing the existing `btn` classes and invoke
   pattern:
   ```rust
   button { class: "btn btn-blue",
     onclick: move |_| {
        let active = *plan_mode.read();
        plan_mode.set(!active);
        if active { let _ = js_sys::eval("window.__TAURI__.core.invoke('plan_clear', {})"); }
     },
     if *plan_mode.read() { "Close Plan" } else { "Plan" }
   }
   ```

2. **Plan panel** rendered only `if *plan_mode.read()`:
   - **Checklist**: iterate `plan_steps`, render glyph by status:
     `done → "✓"`, `active → "▸"`, `pending → "·"`, plus the instruction (and `expected_tool` chip).
   - **Transcript**: iterate `plan_messages`, style user vs assistant.
   - **Input row**: a Dioxus text `input` bound to `plan_input` via `oninput` (use **native Dioxus
     input handling**, not the JS bridge), a **Send** button, and a **Next** button.

3. **Send** behavior: read `plan_input`; if `plan_steps` is empty → first message is the goal →
   invoke `plan_create` with it; otherwise → invoke `plan_message`. Append the user's text to
   `plan_messages` immediately for responsiveness, then clear `plan_input`.
   Because args must be passed, escape the text into the invoke call, e.g.:
   ```rust
   let text = plan_input.read().clone();
   let payload = serde_json::json!({ "goal": text }).to_string(); // or {"text": text}
   let js = format!("window.__TAURI__.core.invoke('plan_create', {})", payload);
   let _ = js_sys::eval(&js);
   ```
   (Use `serde_json` to build the args object so quotes/newlines are safely escaped — do **not**
   string-concatenate raw user text into JS.)

4. **Next** button: `js_sys::eval("window.__TAURI__.core.invoke('plan_advance', {})")`.

### Layout / styling

Reuse existing CSS classes; add minimal styles for `.plan-panel`, `.plan-step`,
`.plan-step.active`, `.chat-msg.user`, `.chat-msg.assistant`. Keep the overlay's transparent dark
theme. The reactive guidance panel stays visible (secondary) while Plan Mode is open.

## Implementation Steps

1. Add `ChatMsg` / `StepView` structs and the new signals to `App`.
2. Extend the JS-inbox `use_hook` with the four plan listeners + buffers.
3. Extend the 50ms polling loop to drain plan buffers and update signals (token append, plan replace,
   step update, done).
4. Add the Plan toggle button.
5. Add the conditional Plan panel: checklist + transcript + input/Send/Next.
6. Add CSS for the new elements.
7. `cd trainerAI_overlay; cargo tauri dev` and exercise the flow.

## File & Directory Changes

- **Modified:** `src/main.rs` — new signals, plan event intake, Plan button, Plan panel, helper structs.
- **Modified:** (inline `<style>` in `main.rs`, or the existing CSS asset) — Plan panel styles.

## Testing & Validation

Manual (covered end-to-end in Phase 5):
1. Backend up; `cargo tauri dev`.
2. Click **Plan** → panel opens.
3. Type "draw a hexagon", **Send** → checklist populates from `plan-update`, plan summary appears in chat.
4. Type a follow-up question, **Send** → assistant tokens stream into the transcript, ends on `plan-done`.
5. Click **Next** → current step marked done ✓, next becomes active ▸ (`plan-step` applied).
6. Click **Close Plan** → panel hides and `plan_clear` is invoked (backend drops the plan; reactive
   guidance resumes).

## Edge Cases & Risks

- **Unescaped user text in invoke** → always build args via `serde_json::json!(...).to_string()`; never
  interpolate raw text into the JS string.
- **Token ordering** → the 50ms poll preserves push order within a buffer; drain token buffer before
  applying `plan-done` in the same tick so the final tokens aren't dropped.
- **First-message ambiguity** (goal vs chat) → gate on `plan_steps.is_empty()`; once a plan exists, all
  sends go to `plan_message`. Mirror the backend `chat` contract from Phase 1.
- **Dioxus input handling** → prefer `oninput` binding to a signal; the existing JS-eval bridge is only
  for *invoking* commands and *receiving* events, not for reading input values.
- **Panel + click-through**: the overlay sets `set_ignore_cursor_events(true)`. Ensure the Plan panel /
  input is interactive — reuse whatever mechanism the existing buttons use to receive clicks (the app
  already has working buttons, so follow that exact pattern; if buttons work, the input will too within
  the same interactive region).

## Notes

- Reused: `use_signal` state model, `btn`/`btn-blue` classes, `js_sys::eval` invoke pattern, the
  `window.__guidance_inbox` listener + 50ms drain loop (the single most important pattern to copy).
- `src/renderer/app.rs` is an unused stub — ignore it; all UI lives in `main.rs`.
