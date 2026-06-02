# Phase H.1 — Backend Perception → Guidance Trigger

## Overview

Wire `POST /api/perception/state` so that when an ingested perception frame yields a new `active_tool`, the existing command pipeline (`safe_run_week2_command_pipeline`) fires as a FastAPI background task on a synthesised `CommandRequest`. This is the single change that closes the loop between the autonomous screen-capture loop and the WebSocket token stream.

This sub-phase ships the whole end-to-end behaviour by itself; H.2 and H.3 are diagnostics layered on top.

## Prerequisites

- Phase G perception inference shipped (`analyse_frame` produces `command_line` elements with OCR text).
- Backend running with Qwen reachable at `http://localhost:12434`.
- `feature/phase-h` branch checked out from `main`.

## Goals

- A perception ingestion that produces an `active_tool` automatically dispatches `safe_run_week2_command_pipeline` exactly once per tool-change, per session.
- Concurrent / rapid-fire frames for the same session do not stack overlapping pipeline runs — additional frames are dropped while one is in flight.
- No change to manual `/api/command` behaviour, to the LLM service, to RAG, or to WebSocket broadcasting.
- New unit tests cover: trigger fires on first tool, trigger skipped on same tool, trigger skipped while another is running.

## Technical Design

### New module: `trainerAI_backend/app/services/guidance_trigger_service.py`

In-memory, per-session state matching the rest of the codebase's "module-level dict + asyncio.Lock" pattern (`session_state_service` is the precedent).

Public API:

```python
def should_trigger(session_id: str, active_tool: str) -> bool:
    """True iff active_tool differs from the last tool we triggered for this session."""

def mark_triggered(session_id: str, active_tool: str) -> None:
    """Record the tool we are about to dispatch guidance for."""

async def try_acquire(session_id: str) -> bool:
    """Non-blocking lock acquire. Returns False if a pipeline run is already in flight for this session."""

def release(session_id: str) -> None:
    """Release the per-session lock. Idempotent."""
```

Internal state:

```python
_last_triggered_tool: dict[str, str] = {}
_inflight: dict[str, asyncio.Lock] = {}
```

`try_acquire` uses `lock.locked()` + `await lock.acquire(...)` with `asyncio.wait_for(lock.acquire(), timeout=0)` semantics, or more simply: `if lock.locked(): return False; await lock.acquire(); return True`. Document that this is **drop-on-busy** (not enqueue).

### Modified module: `trainerAI_backend/app/routers/perception.py`

Inject `BackgroundTasks` into `ingest_perception_state` (same pattern as `command.py`). After successful `crud.create_perception_state(...)` and before the response is built, run the trigger block:

```python
from app.services import guidance_trigger_service
from app.services.session_state_service import _extract_active_tool_from_perception
from app.models.command_models import CommandRequest

active_tool = _extract_active_tool_from_perception(payload.model_dump(mode="python"))
if active_tool and guidance_trigger_service.should_trigger(session_id, active_tool):
    background_tasks.add_task(
        _run_guidance_for_perception,
        pool=pool,
        session_id=session_id,
        active_tool=active_tool,
        observed_at=payload.timestamp,
    )
```

`_run_guidance_for_perception` is a private helper in the same file:

```python
async def _run_guidance_for_perception(
    *, pool: asyncpg.Pool, session_id: str, active_tool: str, observed_at: datetime,
) -> None:
    if not await guidance_trigger_service.try_acquire(session_id):
        return  # another pipeline is already streaming for this session — drop
    try:
        guidance_trigger_service.mark_triggered(session_id, active_tool)
        synthetic_command = CommandRequest(
            text=active_tool,
            timestamp=observed_at,
            session_id=session_id,
        )
        task_id = str(uuid.uuid4())
        await safe_run_week2_command_pipeline(
            pool=pool,
            task_id=task_id,
            command=synthetic_command,
        )
    finally:
        guidance_trigger_service.release(session_id)
```

Why `mark_triggered` runs *after* `try_acquire`: if a frame loses the race for the lock, we don't want to "forget" the tool — the in-flight pipeline is already handling it (or a closely-related one), and the next frame with the same tool should still be skipped.

Why `safe_run_*` and not `run_*`: matches `command.py` exactly; we want the existing error-swallowing + logging behaviour so a Qwen hiccup doesn't take down the perception ingest.

### Imports to add at top of `perception.py`

- `import uuid`
- `from datetime import datetime`
- `from fastapi import BackgroundTasks` (added to the existing `from fastapi import …` line)
- `from app.services import guidance_trigger_service`
- `from app.services.command_pipeline_service import safe_run_week2_command_pipeline`
- `from app.services.session_state_service import _extract_active_tool_from_perception`
- `from app.models.command_models import CommandRequest`

If the underscore-prefixed `_extract_active_tool_from_perception` feels too private to import across modules, promote it by removing the leading underscore in the same commit — but do so only if needed; the existing perception ingest already imports from `session_state_service`'s sibling module conventions.

## Implementation Steps

1. Create `trainerAI_backend/app/services/guidance_trigger_service.py` with the four public functions and module-level state described above. Add a module docstring noting the drop-on-busy semantics.
2. Open `trainerAI_backend/app/routers/perception.py`:
   - Add imports listed above.
   - Add `background_tasks: BackgroundTasks` to the `ingest_perception_state` signature (after `payload`, before `pool=Depends(...)` per FastAPI ordering).
   - Append the trigger block after the existing `if perception_id is None or session_id is None or observed_at is None:` guard but before the `return PerceptionStatePersistedResponse(...)`.
   - Add the `_run_guidance_for_perception` private helper at module bottom.
3. Manual smoke at the REPL:
   ```python
   import asyncio
   from app.services import guidance_trigger_service as g
   assert g.should_trigger("s", "LINE") is True
   g.mark_triggered("s", "LINE")
   assert g.should_trigger("s", "LINE") is False
   assert g.should_trigger("s", "CIRCLE") is True
   ```
4. Write tests (see Testing section). Run `pytest tests/test_perception_router.py -v` and confirm green.
5. Live smoke against a running stack (full procedure in `04-verification-acceptance.md`).

## File & Directory Changes

| File | Change |
|---|---|
| `trainerAI_backend/app/services/guidance_trigger_service.py` | **New.** ~40 LoC; module-level dicts + 4 public functions. |
| `trainerAI_backend/app/routers/perception.py` | Add 6 imports, add `BackgroundTasks` param, add ~10-line trigger block, add ~20-line `_run_guidance_for_perception` helper. |
| `trainerAI_backend/tests/test_perception_router.py` | New cases (extend existing file or create if absent). |

No deletions. No changes to models, schema, or any other service.

## Testing & Validation

### Unit tests (new or extended `tests/test_perception_router.py`)

Use FastAPI `TestClient` with the existing pool fixture. Monkeypatch:

- `app.routers.perception.safe_run_week2_command_pipeline` → an `AsyncMock` recording calls.
- `app.routers.perception.analyse_frame` → returns a fixed `command_line` element with `text="LINE"`.

Cases:

1. **Triggers on new tool.** POST a perception state with a `LINE` command-line element. Assert the mock was called once with `command.text == "LINE"`, `command.session_id` matches the request, and `task_id` is a valid UUID.
2. **Skips on same tool.** Call `guidance_trigger_service.mark_triggered("default-session", "LINE")` directly, then POST the same state. Assert the mock was **not** called.
3. **Skips while in-flight.** Hand the mock an awaitable that blocks on a never-set event; POST two perception states back-to-back; assert exactly one mock call.
4. **No active_tool ⇒ no trigger.** POST a state whose elements contain no `command_line` entry. Assert the mock was not called.
5. **Persistence still happens.** All four cases above must still return 201 and persist the row in the DB stub.

Add `pytest.fixture(autouse=True)` that resets `guidance_trigger_service._last_triggered_tool` and `_inflight` between tests to keep isolation tight.

### Live smoke

Covered in detail in `04-verification-acceptance.md`. Quick check from the command line while the backend is running:

```powershell
$body = @{ session_id = "default-session"; timestamp = (Get-Date).ToString("o"); elements = @(@{ label = "command_line"; text = "Command: LINE" }) } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/perception/state -Body $body -ContentType application/json
# In another terminal:
wscat -c ws://localhost:8000/api/guidance/ws/default-session
# Expected: streaming tokens followed by {"type":"done"}
```

## Edge Cases & Risks

- **`active_tool` extracted from OCR is noisy.** The `_extract_active_tool_from_perception` helper already uppercases and trims; OCR garbage like `LIN3` would trigger guidance once and then be memoised — undesirable but self-limiting (next clean OCR resets to `LINE`). Acceptable for Phase H. Revisit only if it shows up in practice.
- **Long-running Qwen response (10–30 s) while frames keep arriving.** Drop-on-busy keeps the LLM from being saturated. The next perception frame that arrives after the pipeline finishes will re-evaluate `should_trigger`; if the tool is still the same, it's skipped — exactly the desired behaviour.
- **Process restart.** `_last_triggered_tool` is in-memory, so after a backend restart the next frame for the previous tool will re-trigger guidance once. Acceptable; the user explicitly approved single-process semantics.
- **Synthesised CommandRequest.** The pipeline's `_extract_active_tool` will re-derive the tool from `text=active_tool`, which is idempotent — the OCR-derived tool wins inside `session_state_service.update_session_from_command` anyway via its `perception_tool` override. No double-counting.
- **`session_id` from perception payload.** It is already required by `PerceptionStateRequest`; pass through unchanged.
- **`BackgroundTasks` ordering.** FastAPI runs background tasks *after* the response is sent. The 201 returns immediately, the WS push happens shortly after — matches the user's mental model.

## Notes

- The four `guidance_trigger_service` functions are intentionally tiny and synchronous-friendly (except `try_acquire`). Resist the urge to wrap them in a class or extract an interface — there is exactly one caller.
- If a future phase wants throttle-by-time on top of throttle-by-tool, add a `_last_trigger_at: dict[str, float]` field; do not add it speculatively now.
- The `_extract_active_tool_from_perception` import path crosses a private boundary. If a reviewer objects, the smallest acceptable fix is to drop the underscore in `session_state_service.py` in the same commit. Do not duplicate the logic.
