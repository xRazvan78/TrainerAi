# Sub-phase C.5 — Verification & Acceptance

## Overview

End-to-end verification that Phase C is functionally complete. No new code; this is a runbook of checks plus a written acceptance checklist mirrored from `specs/phase-C-qwen-llm-integration.md`.

## Prerequisites

- C.1 through C.4 implemented and unit-tested.
- Docker stack running (`docker compose up -d` from repo root).
- Docker Desktop Model Runner serving `ai/qwen3.5:35B-A3B-Q4_K_M` at `http://localhost:12434/engines/llama.cpp/v1` (verified with the `Invoke-RestMethod` snippet from C.1).
- A populated `embeddings` table (Phase D output).

## Goals

- Full backend test suite is green.
- Live POST → WebSocket flow produces coherent, AutoCAD-relevant guidance within 2–5 seconds.
- Failure modes (Model Runner down, no WS client) degrade gracefully without crashes.
- All acceptance items listed in `specs/phase-C-qwen-llm-integration.md` §Acceptance Criteria are checked.

## Technical Design

N/A — verification phase.

## Implementation Steps

### 1. Test suite

```bash
cd trainerAI_backend
pytest tests/ -v
```

Expected: ~33 tests pass (27 from prior phases plus ~6 added across C.1–C.4). No failures, no skips other than any that were already skipped pre-Phase C.

### 2. OpenAPI / docs check

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs`. Confirm:
- The `/api/guidance/ws/{session_id}` WebSocket endpoint is listed (FastAPI shows WS routes in the schema since 0.115).
- All other existing endpoints still appear (`/api/command`, `/api/perception/state`, `/db/...`, `/health`).

### 3. End-to-end smoke test

Create `trainerAI_backend/scripts/smoke_phase_c.py` (a one-off script, *not* a pytest test):

```python
import asyncio
import httpx
import websockets

SESSION_ID = "smoke-phase-c"
BASE = "http://localhost:8000"
WS = f"ws://localhost:8000/api/guidance/ws/{SESSION_ID}"

async def main():
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE}/db/sessions", json={
            "session_id": SESSION_ID,
            "skill_score": 0.5,
            "verbosity_level": "medium",
        })

    async with websockets.connect(WS) as ws:
        async with httpx.AsyncClient() as client:
            await client.post(f"{BASE}/api/command", json={
                "text": "LINE",
                "timestamp": "2026-05-21T12:00:00Z",
                "session_id": SESSION_ID,
            })

        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=15)
                print(msg, end="", flush=True)
                if '"type":"done"' in msg:
                    break
        except asyncio.TimeoutError:
            print("\n[TIMEOUT] no done marker within 15 s")

asyncio.run(main())
```

Install client dep if needed: `pip install websockets`. Run from `trainerAI_backend/`:

```bash
python scripts/smoke_phase_c.py
```

Expected: a 2–4 sentence guidance string about the AutoCAD `LINE` command streams to stdout, followed by `{"type":"done"}`. Total elapsed time: 2–5 seconds (after a warm Model Runner; first run after container start may take 30–60 s).

### 4. Idle-keepalive check

In a separate terminal, use any WebSocket client (e.g., `wscat -c ws://localhost:8000/api/guidance/ws/idle-test`) and leave it open for 90 seconds. Expected: receive at least two `{"type":"ping"}` frames (one at ~30 s, another at ~60 s) and the connection stays open.

### 5. Failure-mode check

Stop the Model Runner (`docker stop <model-runner-container>` or quit Docker Desktop's Model Runner). Re-run the smoke script:
- Backend stays alive (the `uvicorn` log shows the command being accepted with 202 Accepted).
- WebSocket receives no tokens; the script's 15 s timeout fires and prints `[TIMEOUT]`.
- No tracebacks in the uvicorn log other than (optionally) a single `httpx.ConnectError` swallowed at the wrapper.

Restart Model Runner, re-run, confirm normal flow returns.

## File & Directory Changes

| Path | Change |
|---|---|
| `trainerAI_backend/scripts/smoke_phase_c.py` | NEW — manual smoke runner (not a pytest test). |
| `plans/phase-C-complete.md` | NEW (write at end of phase) — completion report following the pattern of `plans/phase-D-complete.md`. |

## Testing & Validation

This sub-phase *is* the validation. See the checklist below.

## Acceptance Checklist

Mirror of `specs/phase-C-qwen-llm-integration.md` §Acceptance Criteria. All items must be checked before declaring Phase C done.

- [ ] `pytest tests/ -v` green; no new skips beyond pre-Phase-C baseline.
- [ ] `GET http://localhost:8000/docs` shows the `/api/guidance/ws/{session_id}` WebSocket endpoint.
- [ ] POSTing to `/api/command` results in tokens appearing on the connected WebSocket within 2–5 seconds (warm path).
- [ ] The guidance text is coherent and AutoCAD-relevant (use the `LINE`, `FILLET`, `OFFSET` smoke prompts — none of them should produce off-topic or hallucinated command names).
- [ ] WebSocket connection survives idle for 60+ seconds (keepalive ping observed).
- [ ] Backend does not crash or hang when the Model Runner is unreachable (verified by stopping the container).
- [ ] Re-connecting the WebSocket with the same `session_id` cleanly replaces the prior connection (verify with two `wscat` sessions).
- [ ] `plans/phase-C-complete.md` written, summarising what shipped, deviations from the original spec, and any follow-ups for Phase F.

## Edge Cases & Risks

- **Smoke test may pass on a warm cache but fail on first run after `docker compose up`**: document this in `plans/phase-C-complete.md`. Cold-load latency is a known property of the Model Runner, not a defect.
- **`websockets` Python lib is not in `requirements.txt`** — it's a smoke-test client dep only, intentionally not pinned in the project. Install ad-hoc when running the script.
- **AutoCAD-relevance is a judgement call**: if Qwen produces vague output, do **not** start tuning the prompt as part of Phase C — log it as a follow-up for a dedicated prompt-engineering pass.

## Notes

- The completion report (`plans/phase-C-complete.md`) should follow the format used for Phase D (`plans/phase-D-complete.md`): a short narrative of what shipped, deltas vs. the original spec, the test count, and any open issues handed to Phase F.
- Once this checklist is fully ticked, Phase C is closed and Phase F (full pipeline wiring on the Tauri side) becomes unblocked.
