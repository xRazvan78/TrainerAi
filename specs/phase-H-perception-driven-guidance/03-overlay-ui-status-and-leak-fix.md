# Phase H.3 — Overlay UI WS Badge + Polling-Loop Leak Fix

## Overview

Two small changes to `trainerAI_overlay/src/main.rs`:

1. Listen for the new `guidance-ws-status` Tauri event from H.2 and surface it as a tiny "WS ●" badge next to the existing streaming-state dot.
2. Fix a latent bug in the polling effect that spawns a fresh 50 ms `wasm_bindgen_futures::spawn_local` future on every render.

Neither change is strictly required for guidance tokens to display — H.1 alone is sufficient for the end-to-end happy path — but together they make verification deterministic and prevent the streaming panel from updating raggedly once render frequency rises.

## Prerequisites

- H.2 merged (the event is meaningless without an emitter).

## Goals

- A visible 8 px coloured dot in the overlay header reflects WebSocket connection state: green when connected, red when not. Default state is red until the first event arrives.
- The 50 ms inbox-drain `spawn_local` runs **once** per component lifetime, not once per render.
- No regression in token-streaming display behaviour.

## Technical Design

### 1. WS-status listener and signal

Mirror the existing `guidance-token` plumbing: extend the `window.__guidance_inbox_init` IIFE to also register a listener for `guidance-ws-status`, pushing payloads into a sibling `window.__ws_status_inbox` array. Then drain it inside the same 50 ms polling loop.

New signal:

```rust
let mut ws_connected = use_signal(|| false);
```

Inbox-init JS (extend the existing block in `use_effect`):

```js
if (window.__TAURI__ && window.__TAURI__.event) {
  window.__TAURI__.event.listen('guidance-token', function(e) {
    window.__guidance_inbox.push(e.payload);
  });
  window.__ws_status_inbox = [];
  window.__TAURI__.event.listen('guidance-ws-status', function(e) {
    window.__ws_status_inbox.push(e.payload);
  });
}
```

Polling-loop drain (add inside the existing loop, after the existing token drain):

```rust
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
```

Plus a new local struct mirroring the Rust-side payload:

```rust
#[derive(Deserialize)]
struct WsStatus { connected: bool }
```

Only the **last** event in the drain matters — intermediate flaps are uninteresting noise.

### 2. WS badge rendering

In the header (current `div { style: "display:flex;…", span { style: "{dot_style}" } … }`), insert a sibling span after the existing dot:

```rust
let ws_dot_style = if *ws_connected.read() {
    "display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;margin-right:6px;"
} else {
    "display:inline-block;width:8px;height:8px;border-radius:50%;background:#ef4444;margin-right:6px;"
};
```

Render order: streaming dot → WS dot → "AutoCAD Trainer AI" title. Both dots use the same shape; the WS dot is 2 px smaller and never pulses, so they read as distinct at a glance.

No CSS class additions — inline styles keep the diff tight.

### 3. Polling-loop leak fix

Current code:

```rust
use_effect(move || {
    wasm_bindgen_futures::spawn_local(async move {
        loop { … }
    });
});
```

`use_effect` re-runs whenever any signal it reads changes. Today it reads no signals, so in practice it runs once on mount and stays put — but the moment H.3 (or any future change) reads a signal inside, Dioxus will respawn the loop on every change. Make it explicitly one-shot:

```rust
use_hook(|| {
    wasm_bindgen_futures::spawn_local(async move {
        loop { … }
    });
});
```

`use_hook` runs exactly once per component instance and never re-executes. Same effect, no foot-gun.

Apply the same change to the inbox-init effect (`use_hook` instead of `use_effect`) for consistency, even though the `window.__guidance_inbox_init` guard already makes it idempotent.

### 4. Signals captured by the closure

The polling closure now writes to `guidance_text`, `is_streaming`, **and** `ws_connected`. Add `let mut ws_connected = ws_connected;` capture if the borrow checker complains; with `use_hook` and `move ||`, the existing `mut` bindings should flow through unchanged.

## Implementation Steps

1. In `trainerAI_overlay/src/main.rs`:
   - Add `#[derive(Deserialize)] struct WsStatus { connected: bool }` near the existing `GuidanceToken` struct.
   - Add `let mut ws_connected = use_signal(|| false);` next to the existing signals.
   - Replace `use_effect(move || { let _ = js_sys::eval(js); });` with `use_hook(move || { let _ = js_sys::eval(js); });` and extend the embedded JS to register the second listener and init `__ws_status_inbox`.
   - Replace the polling `use_effect(...)` with `use_hook(...)` and add the status-drain block inside the loop.
   - Add `ws_dot_style` and a second `span` in the header div.
2. `cd trainerAI_overlay; dx serve --port 1420` and verify the UI renders without runtime errors. (Without a backend connection, the WS dot should be red.)
3. Bring up the backend; the WS dot should turn green within ~1 s.
4. Kill the backend; the WS dot should turn red within ~1 s plus backoff.
5. Restart the backend; the WS dot should return to green.

## File & Directory Changes

| File | Change |
|---|---|
| `trainerAI_overlay/src/main.rs` | Add `WsStatus` struct, `ws_connected` signal, second listener registration, status-drain in polling loop, header WS dot. Convert two `use_effect` to `use_hook`. |

No changes elsewhere. No new dependencies.

## Testing & Validation

No new automated tests — the Dioxus UI has no test harness in this repo. Validation is the four manual UI states from step 2–5 above, plus a side-by-side check that the existing "Send: LINE" button still streams tokens (regression guard for the `use_effect` → `use_hook` swap).

## Edge Cases & Risks

- **`use_hook` semantics.** It captures by move, runs exactly once, and is the documented escape hatch for "fire-and-forget side effects keyed to component identity". Reference: Dioxus 0.6 docs. If a future Dioxus upgrade renames it, the lint will catch it loudly.
- **Race between first event and first render.** If the WS connects before the JS listener registers, the badge will be red until the next status emit. H.2 emits on every (re)connect *and* on every failed connect attempt, so the worst case is "red for ≤ 1 backoff cycle".
- **`ws_connected.set(...)` triggering re-render that re-runs `use_hook`.** It does not. `use_hook` runs exactly once per component instance regardless of signal writes inside the spawned future.
- **`__ws_status_inbox` not present when the JS listener hasn't initialised yet.** The drain expression already returns `[]` via `window.__ws_status_inbox || []`, matching the existing token-inbox pattern. Safe.
- **Token-display regression.** The two-`use_hook` change preserves the same `spawn_local` body; the only delta is "guaranteed one-shot" instead of "approximately one-shot". Manual smoke (step 5) catches any breakage.

## Notes

- Resist combining the two listeners into one envelope (`{kind: "token"|"status", …}`). The current per-event-name scheme is already wired on the Rust side; flattening here would force a second change in `ws_client.rs` for zero benefit.
- The WS badge is intentionally tiny and never animated. It is a debug affordance, not user-facing chrome. If a future product decision wants to hide it in release builds, gate it on `#[cfg(debug_assertions)]` at that time — not now.
