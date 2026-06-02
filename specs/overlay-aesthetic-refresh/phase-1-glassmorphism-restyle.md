# Phase 1: Overlay Glassmorphism Restyle & Test-Button Removal

## Overview
The TrainerAI overlay works functionally but looks plain, and it carries a debug-only
**"Send: LINE"** button that hardcodes a `LINE` command for testing. This phase gives the
overlay a better-looking **glassmorphism** appearance — frosted translucent panel with
backdrop blur, a subtle gradient border/ring, soft glow, and refined typography/buttons —
while keeping all functionality identical, minus the test button. This is the only phase;
the work is self-contained.

## Prerequisites
- A working Tauri/Dioxus overlay that builds and runs (`cargo tauri dev` from
  `trainerAI_overlay/`).
- No backend or schema changes required.

## Goals
- Remove the green **"Send: LINE"** test button entirely.
- Restyle the overlay as a frosted glass card (glassmorphism direction).
- Preserve all existing behavior: status dots, streaming logic, Start/Stop Capture, Clear.
- No regressions; the transparent always-on-top window remains see-through.

## Technical Design

### Key finding — where the live UI lives
The entire live UI is the `App` component in `trainerAI_overlay/src/main.rs`
(approximately lines 106–161), which renders an inline `<style>` block (lines ~107–119)
plus inline element styles. There is **no external stylesheet wired in** —
`trainerAI_overlay/assets/styles.css` and the `src/renderer/` module are leftover
Tauri/Dioxus template files and are **not** referenced by the running overlay. Those dead
files are intentionally left untouched (per user decision).

**All changes are confined to `trainerAI_overlay/src/main.rs`.**

### Glassmorphism style targets
- **`.overlay-container`**: keep the translucent dark base, add
  `backdrop-filter: blur(16px)` (plus `-webkit-backdrop-filter` for compatibility), a soft
  layered `box-shadow` for depth/glow, and a subtle gradient ring border (1px border plus a
  faint inset highlight, or a `background-image` gradient-border technique). Keep the ~320px
  width; bump corner radius to ~16px. Preserve the transparent
  `html, body, #main, #dioxus-root` rules so the window stays see-through.
- **Header row**: keep the two status dots (streaming `dot_style`, ws `ws_dot_style`) and
  the title `h2`. Refine the divider to a faint gradient/low-opacity line; tighten spacing
  and add slight letter-spacing on the title. Keep the existing signal-driven dot colors and
  the `pulse` keyframe (used by the streaming dot).
- **`.guidance-panel`**: lighter translucent inner fill with a subtle inset look (faint inner
  border/shadow), comfortable padding, retained `white-space: pre-wrap` for streamed text,
  improved line-height/font.
- **Buttons (`.btn`)**: unified pill style with smooth `transition`, hover lift, and
  glass-consistent fills. Keep `.btn-blue` (Start/Stop Capture) and `.btn-gray` (Clear).

## Implementation Steps

1. **Remove the test button.** Delete the green **"Send: LINE"** `button { ... }` block
   (currently lines ~144–150), including its `onclick` that invokes `send_command` with
   `text: 'LINE'`. Nothing else references it.

2. **Remove the now-orphaned button style.** The `.btn-green` rule becomes unused once the
   test button is gone — remove that single CSS rule (it is our own orphan from this change).

3. **Rewrite the inline `<style>` block** (lines ~107–119) to implement the glassmorphism
   targets above: update `.overlay-container`, `.guidance-panel`, and `.btn`/`.btn-blue`/
   `.btn-gray`; keep the transparent root rules and the `pulse` keyframe.

4. **Tune inline element styles** in the header row (divider, title `h2`, dot spacing) to
   match the new palette. Optionally adjust the cosmetic color values inside `dot_style` and
   `ws_dot_style` strings to match — but keep their conditional (signal-driven) logic intact.

5. **Leave all behavior untouched**: the signal wiring, JS inbox polling loop, and
   token-streaming logic (lines ~21–102), plus the Start/Stop Capture and Clear `onclick`
   handlers.

## File & Directory Changes
- **Modified:** `trainerAI_overlay/src/main.rs` — remove the Send:LINE button, remove the
  `.btn-green` rule, rewrite the inline style block, tune header inline styles.
- **Untouched (dead template files, by decision):** `trainerAI_overlay/assets/styles.css`,
  `trainerAI_overlay/src/renderer/` (`app.rs`, `mod.rs`).

## Testing & Validation
1. `cd trainerAI_overlay`
2. `cargo tauri dev` — overlay launches as a transparent always-on-top window.
3. **Visual check:** frosted glass card, gradient ring, refined buttons; the **Send: LINE**
   button is gone; only **Start/Stop Capture** and **Clear** remain.
4. **Functional check (behavior unchanged):**
   - Click **Start Capture** → label flips to **Stop Capture** and capture invokes.
   - With the backend streaming guidance, the streaming dot pulses green and the guidance
     panel fills with streamed text.
   - Click **Clear** → panel resets to `"Așteptând activitate AutoCAD..."`.
5. `cargo build` (or the dev build above) succeeds with no warnings about the removed button
   or the orphaned `.btn-green`.

## Edge Cases & Risks
- **`backdrop-filter` support in the webview**: Tauri uses the system WebView2 (Chromium) on
  Windows 10, which supports `backdrop-filter`. If blur does not render, the translucent
  `rgba` background still provides an acceptable fallback — verify during the visual check.
- **Window transparency**: do not alter the `html, body, #main, #dioxus-root` transparent
  rules; removing them would make the whole window opaque.
- **Orphan warnings**: ensure `.btn-green` is fully removed so no dead CSS lingers.

## Notes
- Chosen direction: **Glassmorphism** (confirmed by the user over flat-dark and neon options).
- Decision: leave the unused `renderer/` module and `assets/styles.css` template files in
  place (out of scope for this change).
- Source of the working plan: in-session plan file
  `C:\Users\Vladutsu\.claude\plans\ok-lets-get-a-giggly-cat.md`.
