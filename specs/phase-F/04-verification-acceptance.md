# Phase F.4 — Verification & Acceptance

## Overview

Pure verification phase — no code changes. After F.1 → F.3 are merged,
walk through the end-to-end loop with the actual stack running, confirm
the acceptance criteria, and run the small set of regression checks
that prove Phase E (capture + click-through) was not broken.

## Prerequisites

- F.1, F.2, F.3 merged on `feature/phase-f`.
- Docker Desktop running.
- Docker Model Runner serving Qwen at
  `http://localhost:12434/engines/llama.cpp/v1`. Quick smoke:

  ```powershell
  Invoke-RestMethod http://localhost:12434/engines/llama.cpp/v1/models
  ```

  should list `ai/qwen3.5:35B-A3B-Q4_K_M` (or whatever `LLM_MODEL` is
  set to).
- `pgvector` container up (`docker compose up -d`).
- Embeddings table populated by Phase D (or at least by the Phase B
  seed) — otherwise RAG retrieval is empty and Qwen still streams, but
  with weaker prompts. Either way the streaming itself must work.

## Goals

Verify the README's "Definition of done":

- POST or button click → tokens appear in the overlay panel within
  5 s.
- Tokens appear incrementally (not in one blob).
- Backend restart with overlay running → reconnects within ~5 s.
- Phase E capture + click-through unaffected.

## Implementation Steps

No code. Execute the scenarios below in order; record observations.

### Step 1 — Backend-only sanity (proves Phase C/F backend path)

1. `cd trainerAI_backend; uvicorn app.main:app --reload`.
2. In a second PowerShell, install `wscat` if missing
   (`npm install -g wscat`) and run:

   ```powershell
   wscat -c ws://localhost:8000/api/guidance/ws/default-session
   ```

3. In a third PowerShell:

   ```powershell
   $body = @{
     text       = "LINE"
     timestamp  = (Get-Date -Format o)
     session_id = "default-session"
   } | ConvertTo-Json

   Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/command `
       -Body $body -ContentType "application/json"
   ```

4. **Expected**: `wscat` prints a stream of `{"type":"token",...}`
   messages over a few seconds, then `{"type":"done"}`. If this fails,
   the regression is in the backend (out of Phase F scope — Phase C);
   stop and investigate there.

### Step 2 — Overlay-only sanity (proves F.1/F.2 wiring)

1. Keep the backend running. Close `wscat`.
2. In an overlay terminal:

   ```powershell
   $env:SESSION_ID     = "default-session"
   $env:BACKEND_URL    = "http://localhost:8000"
   $env:BACKEND_WS_URL = "ws://localhost:8000"
   cd trainerAI_overlay
   cargo tauri dev
   ```

3. **Expected**: the overlay window appears, the backend log shows a
   new accept on `/api/guidance/ws/default-session`, no
   `[ws_client] connect failed` lines in the overlay terminal.

### Step 3 — End-to-end happy path (proves F.3)

1. With the overlay open, click **Send: LINE**.
2. **Expected**:
   - Backend logs the POST and the pipeline run.
   - Within 2–4 s, tokens stream into the panel — the text grows
     visibly, not in one snap.
   - Status dot turns green and pulses, then grey on `done`.
3. Click **Send: LINE** again. The panel should clear and re-stream a
   fresh response.
4. Click **Clear**. Panel resets to placeholder; status dot stays
   grey.

### Step 4 — Reconnect

1. With the overlay still open and idle, Ctrl-C the backend uvicorn.
2. **Expected**: overlay terminal logs reconnect attempts; UI stays
   responsive.
3. Restart uvicorn.
4. Within ~5 s, overlay terminal stops complaining; backend logs a new
   WS accept.
5. Click **Send: LINE**. The next stream should arrive normally.

### Step 5 — Phase E regression

1. With the overlay open, click **Start Capture**.
2. Confirm POSTs continue hitting `/api/perception/state` at the
   Phase E cadence (~2/sec when the screen is busy, less when idle —
   the aHash filter is unchanged).

   ```powershell
   Invoke-RestMethod "http://localhost:8000/db/perception_states?session_id=default-session&limit=5"
   ```

3. Move the cursor over the panel: clicks land on the overlay
   (buttons clickable). Move the cursor off the panel: clicks pass
   through to AutoCAD or the desktop. Same Phase E behavior.
4. Click **Stop Capture**. POSTs cease within ~1 s.

### Step 6 — Idle keep-alive

1. Leave the overlay open for ~2 minutes with no activity.
2. **Expected**: no reconnect loop noise (the `ping` envelopes from
   `guidance.py` are consumed and dropped by F.1's parser). WS stays
   open. A subsequent **Send: LINE** still works.

## Testing & Validation

- All six steps pass with the observations matching "Expected".
- Backend `pytest tests/` remains green (no backend code was modified
  in Phase F, so this is a smoke check, not a contract).
- `cargo check` and `cargo tauri build` succeed on a clean checkout
  of `feature/phase-f`.

## Edge Cases & Risks

- **Qwen cold-start.** First token may take longer than 4 s the very
  first time after Model Runner boots. Re-run **Send: LINE** once if
  the first attempt times out the 5 s acceptance bar — do not change
  the bar; subsequent runs should hit it.
- **AutoCAD not installed on the test box.** Phase F does not require
  AutoCAD. Manual `Send: LINE` covers all acceptance criteria. Phase
  G is the place that needs the real application.
- **Two overlay instances at once.** They'd share `SESSION_ID` and
  both receive every token (the broadcaster sends to one connection,
  whoever connected last). Don't run two overlays during
  verification.
- **Embeddings table empty.** Streams still work — Qwen falls back to
  zero retrieved docs. If that produces empty output, ensure Phase D
  has ingested at least one corpus entry before judging quality.

## Notes

- A short capture of the overlay during Step 3 (screen recording or a
  few screenshots) is the easiest artifact to attach to the Phase F
  completion report. Save it alongside `plans/phase-F-completion.md`
  (mirrors what other phases have done — e.g. `plans/phase-C/`).
- After verification, run `graphify update .` once so the knowledge
  graph reflects the new `ws_client.rs` and the deleted
  `renderer/app.rs`.
- File a small Phase G ticket: "AutoCAD command-line OCR → POST
  /api/command", because that's the real trigger this manual button
  is standing in for.
