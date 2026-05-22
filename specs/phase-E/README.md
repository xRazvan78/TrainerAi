# Phase E — Screen Capture (Execution Plan)

## Why this exists

`specs/phase-E-screen-capture.md` describes the goal at a high level but
leaves the core capture function as a TODO and warns that a full WGC + COM
implementation in raw `windows` is 150–200 lines of unsafe code. This
execution plan replaces that ambiguity with a concrete, end-to-end
implementation broken into four sub-phases that can be picked up cold by a
developer who was not part of the planning conversation.

## Context

Today `start_capture()` in
`trainerAI_overlay/src-tauri/src/commands.rs` is a 3-line stub that prints
"Starting screen capture..." and returns Ok. The backend's
`/api/perception/state` endpoint (`trainerAI_backend/app/routers/perception.py`)
is fully working and persists every request as JSONB via
`crud.create_perception_state`
(`trainerAI_backend/app/db/crud.py:288`). Phase F (full pipeline
connection) and Phase G (YOLO/OCR on AutoCAD frames) both depend on a real
capture loop.

After Phase E ships:

- The overlay captures the AutoCAD window every 500 ms.
- An 8×8 average-hash (aHash) diff filters idle frames before they hit the
  network (Hamming distance < 10 → drop).
- Changed frames are POSTed as JSON to `/api/perception/state` with
  `frame_hash` and an optional `frame_b64` JPEG payload.
- Rows appear in `perception_states` and can be queried by `session_id`.

## Two deviations from the original spec

1. **High-level `windows-capture` crate, not raw `windows` COM.** The
   spec's outline leaves `capture_window_frame` as a TODO because hand-
   rolled WGC + D3D11 readback is 150–200 lines of unsafe Rust. The
   `windows-capture` crate (a maintained wrapper around the same WGC API)
   gives us real frames in ~20 lines with the unsafe surface audited
   upstream. The acceptance criterion *"AutoCAD window frames appear in
   backend `perception_states` table"* becomes achievable in this phase
   instead of being deferred.

2. **Extend `PerceptionStateRequest` with optional `frame_b64`, no DB
   migration.** The backend already stores the entire request as JSONB,
   so adding the field is one line in
   `trainerAI_backend/app/models/perception_models.py`. Phase G will need
   the image bytes for YOLO/OCR anyway. The spec's sample payload already
   includes `frame_b64`; we just make the backend accept it.

Capture cadence (500 ms), aHash size (8×8), Hamming threshold (< 10),
JPEG quality (75), and 50 % downscale all remain exactly as the spec
defined them.

## Phase dependency graph

```
E.1 (deps + backend model) ──► E.2 (capture module) ──► E.3 (command loop) ──► E.4 (verify)
```

E.2 and E.3 cannot start until E.1 lands the Cargo.toml dependencies; E.3
imports `capture::*` from E.2. E.4 is pure verification with no code
changes.

## Sub-phase index

| File | Phase | Summary |
| ---- | ----- | ------- |
| [01-dependencies-and-backend-model.md](01-dependencies-and-backend-model.md) | E.1 | Cargo.toml deps for the overlay; one-line backend Pydantic field. |
| [02-capture-module.md](02-capture-module.md) | E.2 | New `capture.rs`: HWND lookup, WGC capture, aHash, JPEG encode. |
| [03-command-loop.md](03-command-loop.md) | E.3 | Rewrite `commands.rs` with start/stop loop + HTTP POST; wire `lib.rs`. |
| [04-verification-acceptance.md](04-verification-acceptance.md) | E.4 | End-to-end manual test, DB inspection, regression checks. |

## Definition of done for the whole phase

- `start_capture()` Tauri command returns `"started"` and does not crash
  with AutoCAD running.
- AutoCAD frames appear as rows in `perception_states` (visible via
  `/db/perception_states?session_id=default-session`).
- Idle frames are filtered: a 30-second idle window produces at most one
  POST.
- `frame_hash` changes when AutoCAD's visible state changes (dialog
  opens, command typed, drawing modified).
- `stop_capture()` halts the loop within ~1 second of being called.
- Backend `pytest tests/` still green after adding the optional
  `frame_b64` field.

## Out of scope for Phase E

- YOLOv8 / EasyOCR detection (Phase G fills `elements: []`).
- WebSocket guidance streaming on the overlay side (Phase F).
- Multi-monitor selection or capturing windows other than AutoCAD.
- Configurable capture cadence / quality via UI (env vars are enough for
  now).
- Hardening: retry/backoff on POST failure, payload size caps, frame
  rate metrics — listed in Phase F or later.

## Tech stack additions

- Rust: `windows-capture` 1.4, `windows` 0.58 (Win32_Foundation,
  Win32_UI_WindowsAndMessaging), `image` 0.25 (jpeg), `base64` 0.22,
  `reqwest` 0.12 (json, rustls-tls), `tokio` 1 (rt-multi-thread, macros,
  time, sync), `chrono` 0.4 (serde).
- Python: none. Adding an optional field to `PerceptionStateRequest` uses
  only existing pydantic features.

## Reused existing code

- `crud.create_perception_state` already stores arbitrary JSONB payloads
  — no new CRUD function needed.
- `PerceptionStateRequest.validate_iso8601_timestamp` already accepts the
  exact format `chrono::Utc::now().to_rfc3339()` emits.
- The cursor-polling click-through thread in
  `trainerAI_overlay/src-tauri/src/lib.rs:18` is unrelated and must not
  be touched.
