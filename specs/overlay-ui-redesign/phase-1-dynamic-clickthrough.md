# Phase 1: Dynamic Click-Through Interactive Region

## Overview

The overlay window is fully click-through except for a hardcoded rectangle that a Rust thread in
`src-tauri/src/lib.rs` polls the cursor against every 50ms. The redesign changes the panel size
(full sidebar ↔ minimized square), so this rectangle must become **dynamic** and controllable from
the frontend. This phase introduces a shared rectangle plus a Tauri command to update it, and rewires
the polling thread to read it. It comes first because Phase 2's minimize toggle depends on the new
command existing.

## Prerequisites

- Working Tauri build (`cargo tauri dev` runs).
- Familiarity with the existing `set_clickthrough` command in `commands.rs` (the new command mirrors its style).

## Goals

- A process-global rectangle holding the current interactive bounds `(x, y, w, h)`, defaulting to the
  expanded-sidebar rect.
- A new `set_interactive_region(x, y, w, h)` Tauri command that updates it, registered in the invoke handler.
- The cursor-polling thread in `lib.rs` reads this rectangle instead of the hardcoded `0–400 / 0–900` values.

## Technical Design

### Shared state (in `src-tauri/src/commands.rs`)

Add near the existing `static CAPTURE_RUNNING` / `static HTTP_CLIENT` declarations:

```rust
use std::sync::Mutex;

// Current interactive (non-click-through) rectangle: (x, y, w, h) in physical pixels,
// relative to the window's top-left. Defaults to the expanded-sidebar bounds.
static INTERACTIVE_RECT: OnceLock<Mutex<(f64, f64, f64, f64)>> = OnceLock::new();

fn interactive_rect_cell() -> &'static Mutex<(f64, f64, f64, f64)> {
    // Default = expanded sidebar rect (see README geometry table).
    INTERACTIVE_RECT.get_or_init(|| Mutex::new((0.0, 0.0, 412.0, 1040.0)))
}

pub fn interactive_rect() -> (f64, f64, f64, f64) {
    *interactive_rect_cell().lock().unwrap()
}
```

(`OnceLock` is already imported in `commands.rs`.)

### Command

```rust
#[tauri::command]
pub fn set_interactive_region(x: f64, y: f64, w: f64, h: f64) {
    *interactive_rect_cell().lock().unwrap() = (x, y, w, h);
}
```

### Polling thread (in `src-tauri/src/lib.rs`)

Replace the hardcoded hit-test (current lines ~32–38) with a read of `commands::interactive_rect()`:

```rust
let (rx, ry, rw, rh) = commands::interactive_rect();
let in_panel = (rx..rx + rw).contains(&rel_x) && (ry..ry + rh).contains(&rel_y);
let _ = window_clone.set_ignore_cursor_events(!in_panel);
```

Update the surrounding comment to explain the rect is now driven by the frontend via
`set_interactive_region` (no longer a fixed panel size).

## Implementation Steps

1. In `commands.rs`, add `use std::sync::Mutex;` and the `INTERACTIVE_RECT` static + `interactive_rect_cell()` + `interactive_rect()` helpers.
2. Add the `set_interactive_region` `#[tauri::command]`.
3. In `lib.rs`, replace the hardcoded `(0.0..400.0)` / `(0.0..900.0)` hit-test with the dynamic read shown above; update the comment.
4. In `lib.rs`, add `commands::set_interactive_region,` to the `tauri::generate_handler![...]` list.

## File & Directory Changes

- `trainerAI_overlay/src-tauri/src/commands.rs` — add shared rect state, accessor, and `set_interactive_region` command.
- `trainerAI_overlay/src-tauri/src/lib.rs` — read dynamic rect in the polling thread; register the new command; update comment.

## Testing & Validation

- `cargo tauri dev` compiles with no warnings about the unused command.
- Temporary manual check: with the existing UI still in place, invoke from the devtools console
  `window.__TAURI__.core.invoke('set_interactive_region', {x:0,y:0,w:88,h:88})` and confirm only the
  top-left ~88px square remains interactive (clicks elsewhere pass through). Invoke again with the
  expanded rect and confirm the full left strip is interactive again.

## Edge Cases & Risks

- **Physical vs. logical pixels:** the polling thread already works in physical pixels
  (`cursor_position()` / `outer_position()`). On a non-100% display-scale, the CSS px values sent
  from the frontend may differ from physical px. Keep the rects generous (slack already included);
  if hit-testing feels off on a HiDPI display, multiply the frontend-sent values by the window
  scale factor before storing. Note this as a known follow-up rather than over-engineering now.
- **Lock poisoning:** `unwrap()` on the mutex is acceptable here (single writer, trivial critical section).

## Notes

Mirrors the existing `set_clickthrough` pattern intentionally so the two click-through mechanisms
stay recognizable side by side.
