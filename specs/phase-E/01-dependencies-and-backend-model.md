# Phase E.1 — Dependencies & Backend Model

## Overview

Lay the foundation everything else in Phase E needs: add the Rust crates
that drive WGC capture, JPEG encoding, hashing, HTTP POST, and async
runtime to the overlay; and extend the backend's perception request model
with an optional `frame_b64` field so the overlay's payload validates
against the existing `/api/perception/state` endpoint.

This sub-phase ships independently and is verifiable on its own: after it,
the overlay must still compile (with only stub code paths) and the backend
test suite must still pass.

## Prerequisites

- Rust toolchain installed and up to date (`rustup update stable`).
- Target `x86_64-pc-windows-msvc` available (`rustup target add x86_64-pc-windows-msvc`).
- Windows 10 build 19041 or newer (verify with
  `(Get-WmiObject -class Win32_OperatingSystem).BuildNumber`).
- Backend test environment working today (`pytest tests/` green on
  `main`).
- Tauri 2 already wired (it is — see existing `Cargo.toml`).

## Goals

- `trainerAI_overlay/src-tauri/Cargo.toml` lists every crate Phase E.2
  and E.3 need, with pinned versions known to compile against
  `tauri = "2"`.
- `cargo build --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`
  succeeds (no source changes yet → no behaviour change).
- `PerceptionStateRequest` accepts an optional `frame_b64: str | None`
  field that defaults to `None`.
- `pytest tests/` still green.

## Technical Design

### Cargo.toml dependencies to add

Append to the `[dependencies]` section in
`trainerAI_overlay/src-tauri/Cargo.toml` (do not remove the existing
`tauri`, `tauri-plugin-opener`, `serde`, `serde_json` entries):

```toml
windows-capture = "1.4"
windows = { version = "0.58", features = [
    "Win32_Foundation",
    "Win32_UI_WindowsAndMessaging",
] }
image = { version = "0.25", default-features = false, features = ["jpeg"] }
base64 = "0.22"
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls"] }
tokio = { version = "1", features = ["rt-multi-thread", "macros", "time", "sync"] }
chrono = { version = "0.4", default-features = false, features = ["clock", "serde"] }
```

Notes:

- `windows-capture` brings its own `windows` dependency for the
  `Graphics_Capture` / `Direct3D11` features; we only add the bare
  Win32 features needed for `EnumWindows` and `GetWindowTextW` on top.
- `image` is set with `default-features = false` + only `"jpeg"` to keep
  the build slim (we never decode PNG/GIF/etc.).
- `reqwest` is set to `rustls-tls` instead of `native-tls` to avoid
  pulling OpenSSL on Windows.
- `chrono` uses `clock + serde` only — no localisation, no JS
  interop.

### Backend Pydantic change

`trainerAI_backend/app/models/perception_models.py` line 33 currently:

```python
frame_hash: str | None = None
```

Append one line directly after it (still inside `PerceptionStateRequest`):

```python
frame_b64: str | None = None
```

No validator. No size cap (Phase E will produce JPEGs ~50–200 KB which
JSONB handles trivially; a real cap will be added in Phase F or G when
detection metadata also grows). The field is opt-in — every other client
of the endpoint continues to work without changes.

`crud.create_perception_state` already stores the full request via
`model_dump(mode="python")` → JSONB, so no DB schema change and no CRUD
change is required. Confirmed at
`trainerAI_backend/app/routers/perception.py:28` and
`trainerAI_backend/app/db/crud.py:288`.

## Implementation Steps

1. Edit `trainerAI_overlay/src-tauri/Cargo.toml`, add the seven
   dependency blocks above. Keep the existing four entries in place.
2. Run `cargo fetch --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`
   from the repo root to populate the local registry; resolve any
   version conflicts that surface.
3. Run a sanity build (still no source changes):
   `cargo build --manifest-path trainerAI_overlay/src-tauri/Cargo.toml`.
   Expect "0 errors". Warnings about unused crates are expected at this
   sub-phase and must be tolerated; they disappear in E.2/E.3.
4. Edit `trainerAI_backend/app/models/perception_models.py`. Insert the
   `frame_b64: str | None = None` field directly under `frame_hash` so
   related optional fields stay grouped.
5. Run `cd trainerAI_backend; pytest tests/ -q`. All tests must still
   pass. If a test snapshot or serialization assertion fails because the
   new field appears with `None`, update the test to account for the new
   optional field rather than removing it.

## File & Directory Changes

| Path | Change |
| ---- | ------ |
| `trainerAI_overlay/src-tauri/Cargo.toml` | Add 7 dependency entries listed above. |
| `trainerAI_backend/app/models/perception_models.py` | Add `frame_b64: str | None = None` to `PerceptionStateRequest`. |

No new files. No deletions.

## Testing & Validation

- `cargo build` on the overlay manifest succeeds.
- `pytest tests/` green (run from `trainerAI_backend/`).
- Quick manual schema check: start the backend, then
  `Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/perception/state -ContentType application/json -Body (@{ session_id = "smoke"; timestamp = (Get-Date).ToUniversalTime().ToString("o"); elements = @(); frame_b64 = "AAAA" } | ConvertTo-Json)`.
  Expect HTTP 201 and a row in the DB whose `payload.frame_b64` equals
  `"AAAA"`.

## Edge Cases & Risks

- **Version conflicts**: `windows-capture` pins a `windows` minor
  version internally; if cargo refuses to resolve, drop the explicit
  `windows = "0.58"` entry and instead enable the two Win32 features
  through `windows-capture`'s re-exports (the crate re-exports the
  `windows` crate as `windows_capture::windows`). Document whichever
  path was taken in the completion report.
- **Backend serialization**: pydantic v2 includes optional fields with
  `None` by default in `model_dump`; downstream JSONB will then contain
  an explicit `"frame_b64": null`. That is harmless and expected.
- **Test snapshots**: if any existing test compares the persisted JSONB
  payload byte-for-byte, it will now include `"frame_b64": null` and
  must be updated.

## Notes

- The spec's `Cargo.toml` snippet enables a much larger `windows`
  feature set because it implements WGC by hand. With
  `windows-capture` doing that for us, we drop those features entirely.
- Keep the deps additive — do not change the version of `tauri`,
  `serde`, etc. Phase E is not the place to upgrade the framework.
