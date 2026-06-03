# Overlay UI Redesign

## Summary

Redesign the TrainerAI overlay frontend from scratch (functionality preserved) into a polished
**tall scrollable left sidebar** with a **refined dark-glass** aesthetic, and add the ability to
**minimize the panel to a small corner square** (top-left) that restores on click.

## Why

The overlay still looks like the default Tauri/Dioxus template. Three concrete problems:

1. **Look & layout** — the UI is a small fixed 320px card; it should be a fuller, polished sidebar.
2. **Overflow** — `.guidance-panel` has `min-height` but no `max-height`/scroll, so long guidance
   text runs off the bottom of the screen instead of scrolling internally.
3. **No minimize** — the panel can't be collapsed when it takes too much space.

## Goals / Success Criteria

- Sidebar panel ~380px wide, ~90vh tall, anchored top-left with margin; refined dark-glass styling.
- Guidance area and plan chat/checklist scroll **internally** — long content never leaves the screen.
- A minimize button collapses the panel to a ~56px rounded square badge (top-left); clicking it restores.
- Click-through interactive region tracks the current state (full sidebar vs. small square) so clicks
  land correctly in both states and pass through everywhere else.
- All existing functionality preserved: capture toggle, plan mode (create/message/advance/clear),
  guidance streaming, WS/streaming status dots, Clear.

## Key Architectural Constraint (read before implementing)

The overlay window is a fullscreen (1920×1080) **transparent, always-on-top, click-through** layer.
JS hover events do **not** fire under OS-level click-through, so the interactive (non-click-through)
zone is determined by a Rust thread in `src-tauri/src/lib.rs` that polls the cursor position every
50ms against a **hardcoded rectangle** (`0–400` X, `0–900` Y).

Because the panel will now change size (full sidebar ↔ small square), this rectangle must become
**dynamic**, driven from the frontend via a new Tauri command. The CSS pixel geometry and the Rust
rectangle bounds must stay in agreement.

All UI lives in `trainerAI_overlay/src/main.rs` as inline `rsx!` markup plus a single `<style>` block.
No external CSS is wired in. The event/polling pipeline (guidance + plan inboxes via `js_sys::eval`)
must remain untouched.

## Shared Geometry Constants (both phases must agree)

| State | x | y | w | h | Notes |
|---|---|---|---|---|---|
| Expanded sidebar | 0 | 0 | ~412 | ~1040 (≈full screen height) | 16 margin + 380 width + scrollbar/padding slack |
| Minimized square | 0 | 0 | ~88 | ~88 | 16 margin + 56 badge + slack |

The frontend invokes `set_interactive_region` with these exact numbers on each state toggle and once
on startup; the default in `commands.rs` must match the expanded rect.

## Phase Overview

| Phase | File | Purpose |
|---|---|---|
| 1 | `phase-1-dynamic-clickthrough.md` | Make the click-through interactive region dynamic via a new Tauri command (`commands.rs`, `lib.rs`). |
| 2 | `phase-2-frontend-redesign.md` | Rebuild the UI (`main.rs`): tall scrollable dark-glass sidebar + minimize-to-square, wired to the Phase 1 command. |

## Out of Scope

- Backend, WS protocol, capture, and plan HTTP endpoints — unchanged.
- Dragging/resizing the panel (user chose a fixed sidebar + fixed corner badge).
- Deleting unused `src/renderer/` and `assets/styles.css` (note only; do not delete).
