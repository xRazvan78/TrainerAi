# Phase 2: Frontend Redesign — Tall Scrollable Sidebar + Minimize-to-Square

## Overview

Rebuild the overlay UI in `trainerAI_overlay/src/main.rs` from scratch: a polished, refined
**dark-glass tall sidebar** (~380px × ~90vh) whose guidance and plan areas scroll internally, plus a
**minimize-to-square** feature (top-left ~56px badge, click to restore). Only the `<style>` block and
the `rsx!` markup tree change — all Rust logic (structs, signals, hooks, polling loop, event handlers)
is preserved. Wires the minimize toggle to the Phase 1 `set_interactive_region` command.

## Prerequisites

- **Phase 1 complete** — `set_interactive_region` command exists and is registered.

## Goals

- Sidebar: ~380px wide, ~90vh tall, top-left margin, flex column so inner regions can scroll.
- `.guidance-panel` becomes the flexible scroll region (`flex: 1 1 auto; overflow-y: auto; min-height: 0`),
  so long guidance text scrolls instead of running off-screen.
- Plan chat transcript keeps an internal scroll with a sensible `max-height`.
- Minimize button collapses to a `.mini-badge` square; clicking the badge restores the full sidebar.
- Each state toggle (and startup) invokes `set_interactive_region` with the matching rect (see README geometry table).
- All existing behavior preserved: Capture toggle, Plan create/message/advance(Next)/clear(Close Plan),
  guidance streaming text accumulation, streaming + WS status dots, Clear.

## Technical Design

### Preserve verbatim (do NOT change)

- All `#[derive(Deserialize)]` structs (`GuidanceToken`, `WsStatus`, `ChatMsg`, `StepView`, `PlanPayload`,
  `StepPayload`, `PlanData`, `TokenPayload`).
- Both `use_hook` blocks: the JS inbox initializer and the 50ms `spawn_local` polling loop.
- Every existing signal and every `onclick`/`oninput` handler body, including the exact
  `js_sys::eval("window.__TAURI__.core.invoke(...)")` invoke strings for `start_capture`,
  `stop_capture`, `plan_create`, `plan_message`, `plan_advance`, `plan_clear`.

### New state

```rust
let mut minimized = use_signal(|| false);
```

### Startup region hook

Add a `use_hook` (or reuse an existing one) that invokes the expanded rect once on mount:

```rust
let _ = js_sys::eval("window.__TAURI__.core.invoke('set_interactive_region', {x:0,y:0,w:412,h:1040})");
```

### Helper to toggle region from handlers

Each minimize/restore `onclick` sets `minimized` and invokes the matching rect:

- Minimize (button in header): `minimized.set(true)` then invoke `{x:0,y:0,w:88,h:88}`.
- Restore (click on badge): `minimized.set(false)` then invoke `{x:0,y:0,w:412,h:1040}`.

### `<style>` block (refined dark glass)

Keep the `html, body, #main, #dioxus-root` transparent reset and `@keyframes pulse`. Rewrite the rest:

- `.overlay-container`: `width: 380px; height: 90vh; margin: 16px; padding: 18px; display: flex;
  flex-direction: column; gap: 12px; box-sizing: border-box;` plus refined glass
  (`background: rgba(15,23,42,0.72); backdrop-filter: blur(18px); border-radius: 18px;
  border: 1px solid rgba(255,255,255,0.16); box-shadow: …`).
- `.ov-header`: `display:flex; align-items:center; gap:8px;` with the title and a minimize button
  pushed right via `margin-left:auto`.
- `.icon-btn`: small (~28px) round/rounded glass button for minimize; hover lift.
- `.guidance-panel`: `flex: 1 1 auto; min-height: 0; overflow-y: auto; white-space: pre-wrap;`
  refined typography (`font-size: 0.95rem; line-height: 1.6;`). **Remove** the off-screen overflow
  by giving it the flex + scroll treatment (no `max-height` needed; it fills remaining space).
- `.btn` row: keep the existing `.btn-blue / .btn-green / .btn-gray` gradients, refine radius/spacing.
  Consider a horizontal button row for Plan + Clear to save vertical space.
- `.plan-panel`: glass sub-card; `.chat-transcript { max-height: 200px; overflow-y: auto; }` kept.
- Custom scrollbars for `.guidance-panel` and `.chat-transcript`:
  `::-webkit-scrollbar { width:8px } ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.18); border-radius:4px }`
  `::-webkit-scrollbar-track { background: transparent }`.
- `.mini-badge`: `width:56px; height:56px; margin:16px; border-radius:16px; display:flex;
  align-items:center; justify-content:center; gap:4px; cursor:pointer;` glass bg + hover lift;
  contains the streaming status dot + a small "AI" label.

### `rsx!` markup structure

```
if *minimized.read() {
    div { class: "mini-badge", onclick: /* restore + region */,
        span { style: "{dot_style}" }   // reuse existing streaming dot
        span { "AI" }
    }
} else {
    div { class: "overlay-container",
        div { class: "ov-header",
            span { style: "{dot_style}" }       // streaming dot (existing)
            span { style: "{ws_dot_style}" }    // ws dot (existing)
            h2 { "AutoCAD Trainer AI" }
            button { class: "icon-btn", onclick: /* minimize + region */, "—" }
        }
        div { class: "guidance-panel", "{guidance_text}" }
        // button row: Capture (blue), then Plan (green) + Clear (gray)
        // existing capture/plan/clear buttons with their UNCHANGED onclick bodies
        if *plan_mode.read() { /* existing plan-panel block, classes refined, logic unchanged */ }
    }
}
```

Reuse the existing `dot_style`, `ws_dot_style`, `capture_label`, `plan_btn_label` locals as-is.

## Implementation Steps

1. Add `let mut minimized = use_signal(|| false);` alongside the other signals.
2. Add a startup `use_hook` invoking `set_interactive_region` with the expanded rect.
3. Replace the `<style>` block contents with the refined dark-glass styles above (keep the transparent
   reset + `@keyframes pulse`).
4. Replace the `rsx!` body tree with the `if minimized { mini-badge } else { container }` structure,
   moving the existing header/guidance/buttons/plan-panel into the `else` branch **with their handler
   bodies unchanged**.
5. Add a minimize `icon-btn` in the header (`minimized.set(true)` + invoke small rect) and the
   `mini-badge` restore `onclick` (`minimized.set(false)` + invoke expanded rect).
6. Verify no signal/struct/handler was dropped in the rewrite.

## File & Directory Changes

- `trainerAI_overlay/src/main.rs` — rewrite `<style>` block and `rsx!` markup; add `minimized` signal,
  startup region hook, minimize/restore handlers. No other files.

## Testing & Validation

1. `cd trainerAI_overlay; cargo tauri dev` — overlay launches as a tall left dark-glass sidebar.
2. With backend running, trigger guidance / send a long plan message → confirm long text **scrolls
   inside** the guidance and chat panels and never leaves the screen.
3. Click minimize (—) → panel collapses to the top-left ~56px badge; clicks on AutoCAD pass through
   everywhere except the badge.
4. Click the badge → full sidebar restores; buttons are clickable again; rest of screen stays click-through.
5. Regression: Start/Stop Capture, Plan create → message → Next → Close Plan, Clear; streaming + WS
   status dots still update.

## Edge Cases & Risks

- **Region/CSS drift:** the rects sent to `set_interactive_region` must match the rendered geometry.
  If buttons near the panel's right/bottom edge feel unclickable, widen the expanded rect slightly.
- **Display scaling:** see the HiDPI note in Phase 1 — if hit-testing is offset on a scaled display,
  scale the frontend-sent rect by the window scale factor.
- **Minimized while streaming:** the badge reuses `dot_style`, so the pulse still indicates active
  streaming when collapsed — desirable; confirm it animates.
- **Flexbox scroll:** `min-height: 0` on `.guidance-panel` is required for `overflow-y: auto` to work
  inside a flex column — do not omit it.

## Notes

Functionality parity is the hard requirement; the visual rebuild is free to change classes and layout
as long as every existing handler and the polling pipeline remain wired exactly as before.
