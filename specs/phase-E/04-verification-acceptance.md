# Phase E.4 — Verification & Acceptance

## Overview

No code changes. This sub-phase is the gate that closes Phase E: a
documented, repeatable manual run that proves every acceptance criterion
from the original spec (`specs/phase-E-screen-capture.md`) is satisfied
and the backend regression suite is still green.

## Prerequisites

- Phase E.1, E.2, E.3 all merged.
- pgvector container running (`docker compose up -d`).
- Backend running (`uvicorn app.main:app --reload` from
  `trainerAI_backend/`).
- AutoCAD installed and launchable.
- A clean database state for `phase-e-verify` session is preferred but
  not required.

## Goals

- Every checkbox in the "Acceptance criteria" list (below) passes
  during a single live demo.
- A short markdown completion report is written to
  `plans/phase-E-complete.md` capturing what shipped, any deviations
  from the spec, deviations beyond E.1/E.2/E.3, the test count, and
  open issues handed to Phase F.

## Technical Design

No code. The verification matrix:

| Criterion | How to verify |
| --------- | ------------- |
| `start_capture()` returns `"started"` without crash | Invoke from dev UI; observe Tauri dev console. |
| Frames appear in `perception_states` | `Invoke-RestMethod "http://localhost:8000/db/perception_states?session_id=phase-e-verify"` returns rows. |
| Idle frames are filtered | Leave AutoCAD untouched for 30 s; expect ≤ 1 POST in backend uvicorn log during that window. |
| `frame_hash` differs across state changes | Trigger the LINE command in AutoCAD; query the latest two `perception_states` rows; their `payload.frame_hash` values must differ. |
| `stop_capture()` halts cleanly | Invoke; uvicorn POST log goes silent within ~1 s. Re-invoking `start_capture()` then resumes the stream. |
| Backend regression: `pytest tests/ -q` still green | Run from `trainerAI_backend/`. |

## Implementation Steps

1. Set the dev env vars:
   ```powershell
   $env:BACKEND_URL = "http://localhost:8000"
   $env:SESSION_ID  = "phase-e-verify"
   ```
2. Insert a row for the session (avoids any FK weirdness in future
   joins, though `perception_states` currently has no FK):
   ```powershell
   Invoke-RestMethod -Method Post `
     -Uri http://localhost:8000/db/sessions `
     -ContentType application/json `
     -Body '{"session_id":"phase-e-verify"}'
   ```
   Skip if the endpoint signature differs — perception ingest does not
   require a pre-existing session.
3. Launch AutoCAD and wait until a drawing is open.
4. `cd trainerAI_overlay; cargo tauri dev`. The overlay appears.
5. Trigger `start_capture` via the dev UI button (or via the Tauri
   inspector if no button exists yet — add one in the Dioxus side only
   if necessary; otherwise document the inspector path).
6. Watch uvicorn's stdout. Within ~500 ms a `POST
   /api/perception/state 201` line should appear. Keep AutoCAD still
   for 30 s — expect zero or one further POST (the first changed frame
   after `start_capture`).
7. Switch to AutoCAD; type `LINE` and draw a stroke. POSTs resume; each
   distinct visual state produces a new row.
8. Pull the last two rows:
   ```powershell
   Invoke-RestMethod "http://localhost:8000/db/perception_states?session_id=phase-e-verify&limit=2"
   ```
   Confirm distinct `payload.frame_hash` values and that `payload.frame_b64`
   is a populated string.
9. Invoke `stop_capture`. POST stream stops within 1 s.
10. Re-invoke `start_capture`. POST stream resumes — confirms the
    atomic resets correctly across cycles.
11. Run `cd trainerAI_backend; pytest tests/ -q`. Must be green.
12. Write `plans/phase-E-complete.md` mirroring the structure of
    `plans/phase-C-complete.md` and `plans/phase-D-complete.md`:
    sections "What Shipped", "Deviations from Original Spec",
    "Test Count", "Open Issues for Phase F".

## File & Directory Changes

| Path | Change |
| ---- | ------ |
| `plans/phase-E-complete.md` | New file — completion report. |

No source code changes.

## Testing & Validation

The verification steps above are themselves the validation. The
sub-phase is complete when:

- Every row in the verification matrix is checked off live.
- `plans/phase-E-complete.md` is written and committed.
- `git status` is clean apart from the new completion report.

## Edge Cases & Risks

- **WGC permission prompt**: First-run WGC on Windows 11 may prompt the
  user to allow capture. The verifier must click "Allow". Document this
  in the completion report so future maintainers know to expect the
  dialog.
- **Frame hash false-positive idle**: If aHash collisions happen on
  visually-different but luminance-similar AutoCAD frames, the diff
  threshold may need tuning (drop to < 6 or move to dHash). Document
  any observed false negatives — do not change the threshold inside
  Phase E unless the acceptance criterion outright fails.
- **Backend FK on session_id**: Some `/db/*` query endpoints may join
  against `sessions`. If the GET returns empty despite POSTs in the
  log, query the table directly with `psql`:
  ```powershell
  docker exec -it trainerai_postgres psql -U trainerai -d trainerai `
    -c "SELECT id, session_id, payload->>'frame_hash' FROM perception_states ORDER BY id DESC LIMIT 5;"
  ```
- **Long JPEG base64 in DB**: Each row may carry ~50–200 KB of base64.
  Confirm `perception_states.payload` is `JSONB` and accept that table
  growth is faster than before. Phase G or a maintenance task will
  prune.

## Notes

- The completion report mirrors the existing
  `plans/phase-C-complete.md` / `plans/phase-D-complete.md` so the
  team can scan the four reports side-by-side.
- If any acceptance criterion fails, do NOT relax the criterion — open
  a follow-up issue against the relevant earlier sub-phase (E.2 or
  E.3) and fix there. E.4 is a gate, not a workaround.
