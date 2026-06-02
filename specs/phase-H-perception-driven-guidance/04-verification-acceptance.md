# Phase H.4 — Verification & Acceptance

## Overview

End-to-end acceptance procedure for Phase H. Runs against a fully assembled stack (Docker pgvector + uvicorn backend + Qwen Model Runner + Tauri overlay + AutoCAD). The goal is to prove the autonomous capture → guidance → overlay loop works, not just that each unit test passes.

## Prerequisites

- H.1, H.2, H.3 merged on `feature/phase-h`.
- Qwen reachable at `http://localhost:12434` (the user has confirmed this is the case in their setup).
- AutoCAD installed and runnable.
- `wscat` available on PATH for the WebSocket diagnostic step (`npm install -g wscat` if missing).

## Goals

- Confirm tokens reach `div.guidance-panel` within ~1 s of an AutoCAD command-line change.
- Confirm the "same tool" memoisation works.
- Confirm the WS badge accurately reflects backend availability.
- Confirm the full pytest suite remains green.

## Implementation Steps

### Step 1 — Bring up infrastructure

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi
docker compose up -d
Invoke-RestMethod http://localhost:12434/engines/llama.cpp/v1/models  # Qwen reachable?
```

### Step 2 — Start the backend

```powershell
cd trainerAI_backend
uvicorn app.main:app --reload
```

In a second terminal, confirm health and that the new perception trigger path is in place:

```powershell
Invoke-RestMethod http://localhost:8000/health
# Optional: open the OpenAPI docs and verify POST /api/perception/state still returns 201.
```

### Step 3 — Run the backend test suite

```powershell
cd trainerAI_backend
pytest tests/ -q
```

Expected: all tests pass, including the new `test_perception_router.py` cases for trigger fires / skipped / locked from H.1.

### Step 4 — Sanity-check the WS path with wscat

In a third terminal:

```powershell
wscat -c ws://localhost:8000/api/guidance/ws/default-session
```

Send a synthetic perception state from a fourth terminal:

```powershell
$body = @{
  session_id = "default-session"
  timestamp  = (Get-Date).ToUniversalTime().ToString("o")
  elements   = @(@{ label = "command_line"; text = "Command: LINE" })
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/perception/state `
  -Body $body -ContentType application/json
```

Expected in the `wscat` terminal: a stream of Qwen tokens followed by `{"type":"done"}`. If this works and the overlay step below doesn't, the bug is in the overlay event plumbing (H.2/H.3), not in H.1.

### Step 5 — Repeat with the same tool

Re-run the `Invoke-RestMethod` from step 4 unchanged. Expected: **no new tokens** appear in `wscat`. The trigger memoised `LINE` for this session.

### Step 6 — Change tools

Re-run with `text = "Command: CIRCLE"`. Expected: a fresh stream of Qwen tokens for `CIRCLE`.

### Step 7 — Run the overlay against AutoCAD

```powershell
cd trainerAI_overlay
cargo tauri dev
```

In the overlay UI:
- WS badge should turn green within ~1 s of launch (backend is up).
- The streaming-state dot should still be grey/green per existing Phase F behaviour.

Open AutoCAD with a blank drawing. Click "Start Capture" in the overlay. Type `LINE` at the AutoCAD command prompt and press Enter. Expected within ~1 s of the next captured frame:
- `div.guidance-panel` replaces "Așteptând activitate AutoCAD..." with Qwen-streamed guidance for the LINE tool.
- The streaming dot pulses green during the stream.

Type `CIRCLE`. Expected: a new stream replaces the LINE guidance.

### Step 8 — Backend kill/restart

While the overlay is running, stop the uvicorn process. Expected within ≤ 1 s plus backoff: WS badge turns red. Restart uvicorn. Expected: WS badge turns green; a subsequent AutoCAD command produces fresh guidance.

## File & Directory Changes

None. This sub-phase is verification only.

## Testing & Validation

### Acceptance checklist

- [ ] `docker compose up -d` brings up pgvector cleanly.
- [ ] `Invoke-RestMethod http://localhost:12434/engines/llama.cpp/v1/models` returns model metadata.
- [ ] `pytest tests/ -q` is green, including new H.1 cases.
- [ ] Step 4: `wscat` shows streaming tokens followed by `{"type":"done"}`.
- [ ] Step 5: repeating the same `LINE` POST produces **no** new WS traffic.
- [ ] Step 6: switching to `CIRCLE` produces fresh streaming tokens.
- [ ] Step 7: overlay panel updates without any manual button click.
- [ ] Step 7: switching tools in AutoCAD regenerates the panel.
- [ ] Step 8: WS badge flips red on backend kill and green on restart.

### If step 4 succeeds but step 7 fails

The bug is in the overlay event plumbing introduced in H.2/H.3 (or pre-existing in `ws_client.rs` / `main.rs`). Reproduce in isolation:

1. In the overlay's dev tools console (right-click → Inspect if `withGlobalTauri` exposes it), run:
   ```js
   window.__TAURI__.event.listen('guidance-token', e => console.log('TOKEN', e.payload));
   ```
   Then re-run step 4. If `TOKEN` lines appear in the console, the Tauri-side wiring is fine and the bug is in the Dioxus polling drain (`main.rs`). If they don't appear, the bug is in `ws_client.rs`'s emit path.
2. Cross-check `eprintln!("[ws_client] connected to ...")` in the cargo terminal — its absence indicates the WS never connected (env-var mismatch on `BACKEND_WS_URL` / `SESSION_ID`).

### If step 5 fails (re-trigger fires)

`guidance_trigger_service._last_triggered_tool` is not being populated. Most likely cause: `mark_triggered` is being called inside `try_acquire`'s failure branch, or the `_inflight` lock is released too early. Re-read H.1 § "Why `mark_triggered` runs *after* `try_acquire`".

## Edge Cases & Risks

- **Step 7 timing.** The capture loop in `commands.rs::start_capture` only POSTs when the aHash differs by ≥ 10 bits from the previous frame. If AutoCAD is fully static between command entries, the OCR'd command-line region change must dominate the hash diff. The 8×8 aHash captures the whole window, so even a small text change usually crosses the threshold — but if step 7 hangs at "Așteptând…", confirm a real frame change by checking backend logs for incoming `/api/perception/state` calls.
- **Qwen warm-up.** First inference call after Qwen boot can take 5–10 s. Don't conclude H.1 is broken until you've waited ≥ 15 s for the first stream.
- **Default `SESSION_ID`.** Both `lib.rs` (WS client) and `commands.rs` (capture loop) default to `"default-session"` when `SESSION_ID` is unset. If a developer has set `SESSION_ID` for one process and not the other, the WS will subscribe to a different session than the capture loop writes to, and Phase H will look broken. The wscat step (4) decouples this — if step 4 works but step 7 doesn't, environment mismatch is a prime suspect.

## Notes

- Capture a short screen recording of the working end-to-end flow on first successful pass and drop it into `plans/phase-H-completion-report.md` (or similar) when filing the completion artefact, following the convention of prior phases.
- Once acceptance is green, run `graphify update .` to refresh `graphify-out/` as per the project's `CLAUDE.md` policy.
