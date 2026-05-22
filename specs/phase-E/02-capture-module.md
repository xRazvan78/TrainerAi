# Phase E.2 — Capture Module

## Overview

Create a single new file, `trainerAI_overlay/src-tauri/src/capture.rs`,
that owns every concern of pulling a frame from the AutoCAD window and
turning it into something the command loop can ship: a base64 JPEG plus a
64-bit perceptual hash. This is the only file in Phase E that touches the
Windows Graphics Capture API directly. The command loop in E.3 will only
call its public functions; it will not import the `windows_capture` or
`windows` crates itself.

## Prerequisites

- Phase E.1 merged: `windows-capture`, `windows`, `image`, `base64`,
  `tokio` are available in `Cargo.toml`.
- AutoCAD installed locally (any 2022+ version) so the developer can
  manually verify HWND lookup. If AutoCAD is unavailable, Notepad with
  its title manually changed to "Autodesk AutoCAD" is an acceptable
  substitute for development.

## Goals

- `capture.rs` exists and is exported from `lib.rs` (the `pub mod
  capture;` line is added in E.3, not here — for now the file compiles
  standalone via `cargo check`).
- A `CapturedFrame` struct, an `ahash` function, a `hamming` function, a
  `find_autocad_hwnd` function, and an async `capture_window_frame`
  function are all implemented and publicly exposed.
- `cargo clippy` reports no warnings inside `capture.rs`.

## Technical Design

### Public surface

```rust
pub struct CapturedFrame {
    pub jpeg_b64: String,
    pub hash: u64,
    pub width: u32,
    pub height: u32,
}

pub fn ahash(img: &image::DynamicImage) -> u64;
pub fn hamming(a: u64, b: u64) -> u32;
pub fn find_autocad_hwnd() -> Option<windows::Win32::Foundation::HWND>;
pub async fn capture_window_frame(
    hwnd: windows::Win32::Foundation::HWND,
) -> Option<CapturedFrame>;
```

### `ahash` (8×8 average hash)

Resize to 8×8 with `image::imageops::FilterType::Nearest`, convert to
luma8, compute the mean of the 64 pixel values, set bit `i` to 1 when
pixel `i ≥ mean`. Returns a `u64`. Algorithm exactly as in
`specs/phase-E-screen-capture.md`. Pure function — no allocation beyond
the 64-byte resized buffer.

### `hamming`

`(a ^ b).count_ones()`. One line.

### `find_autocad_hwnd`

Use `EnumWindows` with a C callback that:

1. Skips invisible windows (`IsWindowVisible(hwnd) == false`).
2. Skips cloaked windows (the modern Win10/11 hide-from-Alt-Tab state);
   query with `DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ...)` and skip
   when the returned BOOL is non-zero. If wiring DWM proves fiddly, gate
   it behind a TODO and rely on `IsWindowVisible` alone — both AutoCAD's
   main window and Notepad pass the simpler check.
3. Reads the window title via `GetWindowTextW` into a fixed `[u16; 256]`
   buffer, converts to `String`, and checks
   `title.contains("AutoCAD")` (case-sensitive — AutoCAD titles always
   include the literal substring `"AutoCAD"`).
4. On the first match, stores the HWND in a `lParam`-passed
   `*mut Option<HWND>` slot and returns `FALSE` to stop enumeration.

The spec's `FindWindowW(None, w!("Autodesk AutoCAD"))` snippet is
explicitly noted as broken because `FindWindowW` requires exact match.
This sub-phase replaces it.

### `capture_window_frame`

Uses `windows_capture::{capture::WindowsCaptureSession, monitor::Monitor,
window::Window, ...}`. Outline:

1. Build a `windows_capture::window::Window` from the raw HWND.
2. Configure a `WindowsCaptureSession` with:
   - `cursor_capture = CursorCaptureSettings::WithoutCursor` (the
     overlay doesn't need the cursor in the frame),
   - `draw_border = DrawBorderSettings::WithoutBorder`,
   - `color_format = ColorFormat::Rgba8`.
3. Implement the `GraphicsCaptureApiHandler` trait inline (or with a
   small `Handler` struct) so `on_frame_arrived` sends the first frame
   over a `tokio::sync::oneshot::Sender<Vec<u8>>` and then calls
   `capture_control.stop()`.
4. Spawn the session via `WindowsCaptureSession::start_free_threaded`
   (so the function can stay async-friendly), then await the oneshot
   with a 250 ms `tokio::time::timeout`. On timeout return `None`.
5. The received `Vec<u8>` is BGRA8 (note: `windows-capture` returns
   BGRA even when `Rgba8` is requested in some versions — verify by
   capturing a known-coloured window once during development; swap
   channels if needed).
6. Wrap the buffer in `image::RgbaImage::from_raw(w, h, buf)`, convert
   to `DynamicImage`, call `.resize_exact(w / 2, h / 2,
   FilterType::Triangle)` (50 % downscale per the spec's frame strategy
   table).
7. Compute `hash = ahash(&resized)`.
8. Encode the resized image to JPEG at quality 75 using
   `image::codecs::jpeg::JpegEncoder::new_with_quality(&mut bytes, 75)`,
   then `base64::engine::general_purpose::STANDARD.encode(&bytes)`.
9. Return `Some(CapturedFrame { jpeg_b64, hash, width: w/2, height: h/2 })`.

### Threading note

`WindowsCaptureSession::start_free_threaded` runs WGC on its own
dedicated OS thread; from the caller's perspective, `capture_window_frame`
remains `async` and yields naturally on the oneshot await. The command
loop in E.3 will additionally wrap each call in
`tokio::task::spawn_blocking` only if profiling shows oneshot contention
— default to plain `.await`.

## Implementation Steps

1. Create `trainerAI_overlay/src-tauri/src/capture.rs` with the module
   doc-comment and `use` statements.
2. Define `CapturedFrame`.
3. Implement `ahash` and `hamming` first — they are pure and trivially
   unit-testable.
4. Implement `find_autocad_hwnd` using `EnumWindows`. Test by
   compiling and running a one-off binary (or a temporary `#[test]`)
   that prints the matched title.
5. Implement `capture_window_frame`. Iterate against AutoCAD (or
   relabelled Notepad) until you see a non-empty JPEG written to disk
   for debugging:
   ```rust
   std::fs::write("debug-frame.jpg", &raw_jpeg_bytes).unwrap();
   ```
   Open the file to confirm the AutoCAD window content is visible.
   Remove the debug write before finishing.
6. Add module-local unit tests for `ahash` and `hamming`:
   - `ahash` of a solid-colour image is some specific value;
   - `hamming(x, x) == 0`; `hamming(0, !0) == 64`.
7. Run `cargo clippy --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`.
   Fix every lint inside `capture.rs`. Allow `clippy::too_many_lines` if
   the capture function pushes past 100 lines.

## File & Directory Changes

| Path | Change |
| ---- | ------ |
| `trainerAI_overlay/src-tauri/src/capture.rs` | New file. |

No edits to `lib.rs` yet — that wiring is in E.3 so this sub-phase can
land without breaking the existing `commands.rs` stubs.

## Testing & Validation

- `cargo check --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`
  passes with no warnings in `capture.rs`.
- Unit tests for `ahash` / `hamming` pass under
  `cargo test --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`.
- Manual smoke: temporarily expose a `#[tauri::command]` named
  `debug_capture_once` that calls `capture_window_frame` and writes
  `debug-frame.jpg`. Invoke from the dev UI with AutoCAD running.
  Confirm the file shows the AutoCAD window. Delete the command before
  closing the sub-phase.

## Edge Cases & Risks

- **BGRA vs RGBA byte order**: `windows-capture`'s `Rgba8` is sometimes
  documented but BGRA in practice. Verify channel order with a red
  pixel test before committing. Document the result inline.
- **Minimised / cloaked windows**: `capture_window_frame` must return
  `None` rather than panic when AutoCAD is minimised. WGC may either
  return an all-black frame or fail the session start — the 250 ms
  oneshot timeout catches both.
- **Multiple AutoCAD windows**: `find_autocad_hwnd` returns the first
  match. Acceptable for Phase E. If the dev has two AutoCAD instances
  open, document the limitation; Phase G can add foreground-window
  preference.
- **High-DPI scaling**: WGC delivers physical pixels. The 50 % downscale
  is computed against the WGC frame, not the logical DIPs — that is
  intentional and matches the spec's frame strategy.
- **JPEG encoder version mismatch**: `image` 0.25 renamed the JPEG
  encoder API; use
  `image::codecs::jpeg::JpegEncoder::new_with_quality` rather than the
  deprecated `JPEGEncoder` alias.

## Notes

- The original spec links to `robmikh/screenshot-rs` and
  `rustdesk/rustdesk` as references. Both are still useful, but
  `windows-capture` is the direct alternative that lets us skip
  re-implementing their internals.
- Do not optimise prematurely — the per-frame work is bounded by JPEG
  encoding (a few ms at 960×540, q75). Profile only if E.4 shows
  the loop missing its 500 ms tick.
