# Phase F.3 — Dioxus UI

## Overview

Rewrite `trainerAI_overlay/src/main.rs` so the Dioxus panel listens for
the `guidance-token` Tauri events emitted by F.1/F.2, streams the text
into a signal token-by-token, and exposes buttons that drive the
pipeline (start/stop capture, send a manual command, clear). Also
delete the unused duplicate component at
`trainerAI_overlay/src/renderer/app.rs`.

This is the final code change in Phase F; F.4 is verification.

## Prerequisites

- F.1 and F.2 merged: the overlay holds a live WebSocket and
  `send_command` is a registered Tauri command.
- `tauri.conf.json` has `withGlobalTauri: true` (already set in Phase
  E) — required for `window.__TAURI__` to exist in the webview.

## Goals

- The Dioxus panel holds a `guidance_text: Signal<String>` and an
  `is_streaming: Signal<bool>`.
- A `use_effect` runs once at mount, registering a
  `window.__TAURI__.event.listen('guidance-token', ...)` callback via
  `js_sys::eval`. The callback pushes payloads into a global JS array
  (`window.__guidance_inbox`).
- A polling task (via `wasm_bindgen_futures::spawn_local` and
  `gloo_timers::future::TimeoutFuture` if needed) drains the inbox
  every ~50 ms and updates signals.
- New-stream semantics: when a token arrives while `is_streaming ==
  false`, clear `guidance_text` first, then append. When `done:true`
  arrives, set `is_streaming = false` and leave the final text on
  screen.
- Buttons:
  - **Start Capture / Stop Capture** — invoke the existing Tauri
    commands `start_capture` / `stop_capture` (mutually exclusive,
    label toggles).
  - **Send: LINE** — invokes `send_command` with `text: "LINE"`. This
    is the manual trigger that lets us exercise the pipeline without
    Phase G.
  - **Clear** — resets `guidance_text` to the placeholder.
- The header status dot is green and pulsing while `is_streaming`,
  grey otherwise.
- The transparent dark styling and ~320 px panel width from Phase E
  are preserved.

## Technical Design

### Why JS interop, not `tauri-sys`

`withGlobalTauri: true` puts the full Tauri JS API on `window`. We can
register one event listener via `js_sys::eval` and stash payloads in a
JS-side queue. Dioxus polls that queue. This avoids adding the
`tauri-sys` crate and wrestling with its WASM build for one event.

### Event listener registration (one-shot, on mount)

Inside the `App` component, run a `use_effect` that executes this JS
once:

```js
(function () {
  if (window.__guidance_inbox_init) return;
  window.__guidance_inbox_init = true;
  window.__guidance_inbox = [];
  window.__TAURI__.event.listen('guidance-token', (e) => {
    window.__guidance_inbox.push(e.payload);
  });
})();
```

Wrap the string in `js_sys::eval(...)` and `.ok()` (don't panic on
failure). The `__guidance_inbox_init` flag makes the effect
idempotent if Dioxus re-runs it.

### Polling loop

`wasm_bindgen_futures::spawn_local` an async block that loops forever:

```rust
loop {
    // Drain the inbox via js_sys::eval returning a JSON string of pending items
    // (eval is enough; we don't need full JsValue interop)
    let drained = js_sys::eval("(function(){const q=window.__guidance_inbox||[]; window.__guidance_inbox=[]; return JSON.stringify(q);})()");
    if let Ok(val) = drained {
        if let Some(s) = val.as_string() {
            // serde_json parse into Vec<GuidanceToken>; update signals
        }
    }
    gloo_timers::future::TimeoutFuture::new(50).await;
}
```

`GuidanceToken` mirrors the Rust struct from F.1:

```rust
#[derive(serde::Deserialize)]
struct GuidanceToken { token: String, done: bool }
```

If `gloo_timers` is not already in `Cargo.toml`, add it:

```toml
gloo-timers = { version = "0.3", features = ["futures"] }
```

(The overlay's frontend crate is the workspace-level `Cargo.toml`, not
`src-tauri/Cargo.toml`. Confirm before editing.)

### Stream state transitions

```
is_streaming = false, token arrives with done=false →
    guidance_text = token; is_streaming = true
is_streaming = true, token arrives with done=false →
    guidance_text += token
token arrives with done=true →
    is_streaming = false  (do NOT clear; leave final text visible)
```

### Invoking Tauri commands from Dioxus

For the buttons, use `js_sys::eval` again with
`window.__TAURI__.core.invoke('send_command', { text: 'LINE' })`. No
return value needed for these buttons; ignore the promise.

## Implementation Steps

1. Read the current `trainerAI_overlay/src/main.rs` to confirm the
   styles, the placeholder text ("Waiting for AutoCAD activity..." or
   the existing Romanian-language equivalent), and any existing
   imports. Preserve the dark theme + size + position.
2. Confirm whether the workspace-level `Cargo.toml` (the one that
   builds the WASM frontend) has `gloo-timers`. If not, add it with
   the `futures` feature. Confirm `wasm-bindgen` /
   `wasm-bindgen-futures` / `js-sys` are present (they should be —
   they're standard Dioxus deps).
3. Rewrite `src/main.rs`:
   - Imports: `dioxus::prelude::*`, `js_sys`, `serde::Deserialize`.
   - Define the local `GuidanceToken` deserializer struct.
   - In `App`, declare `let mut guidance_text = use_signal(|| String::from("<placeholder>"));`
     and `let mut is_streaming = use_signal(|| false);`.
   - Add the listener `use_effect` (idempotent registration via
     `js_sys::eval`).
   - Add the polling `use_effect` that spawns the drain loop with
     `wasm_bindgen_futures::spawn_local`.
   - Render the panel: header (label + status dot),
     guidance text region (white-space: pre-wrap, monospace optional),
     three buttons.
   - Wire button `onclick` handlers to `js_sys::eval` Tauri invokes
     for `start_capture`, `stop_capture`, `send_command`.
   - Local `Clear` button resets the signal in pure Rust.
4. Delete `trainerAI_overlay/src/renderer/app.rs` and, if `mod.rs` only
   re-exports it, delete `src/renderer/` entirely. If `mod.rs`
   contains anything else, leave it but remove the dead re-export.
5. Confirm `main.rs` no longer imports anything from `renderer`.
6. Run `dx build` (or `cargo tauri build`) to make sure the WASM
   bundle compiles.

## File & Directory Changes

| Path | Change |
| ---- | ------ |
| `trainerAI_overlay/src/main.rs` | Rewrite the `App` component: signals, listener effect, polling loop, buttons. Preserve Phase E styling. |
| `trainerAI_overlay/src/renderer/app.rs` | Delete (unused duplicate). |
| `trainerAI_overlay/src/renderer/mod.rs` | Delete if it only re-exports `app`. Otherwise remove the dead `pub use`. |
| `trainerAI_overlay/Cargo.toml` (workspace frontend) | Add `gloo-timers` if missing. |

Confirm via `cargo tree` or grep that nothing else references
`renderer::app`.

## Testing & Validation

- `dx build` (or `cargo tauri build`) succeeds.
- `cargo tauri dev` launches the overlay; the panel renders with the
  placeholder text and the status dot is grey.
- DevTools console for the webview shows no errors during the
  listener registration (right-click the overlay → Inspect, if the
  Tauri dev build allows it; otherwise rely on stderr).
- Clicking **Send: LINE** triggers a POST to `/api/command`; within
  ~2–4 s, tokens begin appearing in the panel. The dot turns green
  and pulses, then grey when `done` arrives.
- Clicking **Send: LINE** again clears the panel and a fresh stream
  appears.
- The **Start Capture** / **Stop Capture** toggle behaves as in Phase
  E (POSTs to `/api/perception/state` continue or stop).
- **Clear** resets the panel without affecting the WS connection.

## Edge Cases & Risks

- **Effect re-runs.** Dioxus may re-run `use_effect` on hot-reload.
  The `__guidance_inbox_init` flag must guard against double-
  registering the listener (would duplicate every token).
- **Polling cadence.** 50 ms is fine for localhost; tokens arrive at
  most tens per second. If panels feel sluggish, drop to 25 ms — do
  not go below 16 ms (one frame at 60 Hz).
- **`is_streaming` false-positive.** If the backend sends two `done`
  in a row (bug or reconnect), the second one is a no-op (already
  false). Safe.
- **Dropped `done` event.** If the WS dies mid-stream and reconnects,
  the next token starts a new stream — our "is_streaming==false →
  clear" rule handles this gracefully.
- **JS bridge missing.** If `window.__TAURI__` is undefined (e.g. the
  page is opened in a plain browser via `dx serve`), the listener
  registration fails silently. That's acceptable — the dev-only
  Dioxus-only path is not a supported run mode for the overlay.
- **Unicode tokens.** Qwen streams tokens that may include multi-byte
  UTF-8 (Romanian diacritics, code blocks). `String::push_str` and
  JSON-via-serde preserve them; no special handling needed.

## Notes

- The original spec offered a `wasm-bindgen` JsCast-heavy approach
  with a global `__dioxus_guidance_token`. We use a plain JS array
  inbox + JSON drain instead because (a) it's smaller, (b) it
  doesn't require Rust↔JsValue conversions for every token, and (c)
  the listener and the polling loop are decoupled — adding a future
  consumer (e.g. a transcript pane) is a matter of reading the inbox
  array, no new event wiring needed.
- Do not add a "reconnect" indicator in the UI for F.3 — the F.1
  reconnect loop is silent by design (out of scope for this phase;
  README lists it).
