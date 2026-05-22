# Code Review Findings

**Plan folder:** `d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\specs\phase-C`
**Date:** 2026-05-21
**Reviewers used:** 1 (post-fix review)
**Implementation scope:** Small (targeted fixes to 5 files from the prior Phase C review)

---

## Summary

This review covers the fixes applied to resolve the six actionable issues from the original Phase C code review. All critical issues from that review — the service→router layering violation and the dead WebSocket broadcast test — have been correctly resolved. The `_active_connections` dict is properly shared across modules via Python's import reference semantics, and the `client.portal.call` test pattern is confirmed valid under Starlette 1.0.0's shared-portal architecture. Two new warnings were surfaced.

---

## Findings

### Critical Issues

None.

---

### Warnings

**W1 — `_feedback_task` local variable does not fully prevent GC on Python 3.12+ (`command_pipeline_service.py:42`)**

The fix assigns `asyncio.create_task(...)` to `_feedback_task`, but a local variable goes out of scope when `run_week2_command_pipeline` returns. Python 3.12+ asyncio can garbage-collect the `Task` object before it completes if the event loop is under memory pressure. The documented Python 3.12 pattern is a module-level task set:

```python
_background_tasks: set[asyncio.Task] = set()

# inside run_week2_command_pipeline:
task = asyncio.create_task(feedback_logger_service.safe_persist_command_feedback(...))
_background_tasks.add(task)
task.add_done_callback(_background_tasks.discard)
```

This ensures the task is referenced until completion, then discarded automatically.

**W2 — `except (WebSocketDisconnect, RuntimeError)` is too broad in ping loop (`guidance.py:38`)**

Catching bare `RuntimeError` silences any `RuntimeError` raised inside `asyncio.sleep` or `send_text` for any reason — not just "WebSocket is closed." Unrelated asyncio `RuntimeError`s (e.g., "This event loop is already running") would be silently discarded. The Starlette-specific message is `RuntimeError("Unexpected ASGI message 'websocket.send'...")`. A narrower catch or a logging call on unexpected exception types would be safer.

---

### Suggestions

**S1 — `_PING_INTERVAL_SECONDS` in `ws_broadcaster.py` is a layering leak**

This constant controls the WebSocket keep-alive ping interval in `guidance.py`. It has nothing to do with broadcasting tokens. It belongs in `guidance.py` or a shared `constants.py`, not in the broadcaster service module.

**S2 — Bare `except Exception` in `ws_broadcaster.py` broadcast helpers**

Lines 19 and 27 catch all exceptions. Programming errors (e.g., passing a non-string token) are silently swallowed and logged only at DEBUG. Consider catching `(WebSocketDisconnect, RuntimeError, OSError)` specifically and logging unexpected types at WARNING.

**S3 — No `__all__` in `ws_broadcaster.py`**

`_active_connections` (private by convention) is directly imported by `guidance.py`. Making the module's public API explicit via `__all__ = ["broadcast_token", "broadcast_done"]` and providing registration functions (`register_connection`, `unregister_connection`) instead of exposing the raw dict would make the boundary less fragile.

---

## Plan Conformance

All six actionable fixes from the prior review were implemented:

| Fix | Prior finding | Status |
|---|---|---|
| 1 | Service imports from router — extract `ws_broadcaster.py` | ✅ Done |
| 2 | Dead WebSocket broadcast test | ✅ Fixed with `client.portal.call` pattern |
| 3 | `active_tool=None` renders as `"None"` in prompt | ✅ Guarded with `or 'UNKNOWN'` |
| 4 | WebSocket disconnect detection unreliable | ✅ `RuntimeError` added to except tuple |
| 6 | `asyncio.create_task` without held reference | ✅ Assigned to `_feedback_task` (partial — see W1) |
| 7 | Silent broadcast failures | ✅ `logger.debug` added |
| 8 | `Dict`/`List` typing inconsistency | ✅ Replaced with built-in `dict`/`list` |

Fix #5 (LLM failure sends error frame) was correctly deferred to Phase F per the original spec.

**Verification results:**
- No import cycles. Dependency graph is acyclic: `routers/guidance.py` → `services/ws_broadcaster.py` ← `services/command_pipeline_service.py`.
- `_active_connections` dict is correctly shared: `guidance.py` imports the same dict object from `ws_broadcaster.py`; mutations are immediately visible in both modules.
- `client.portal` IS set when using `with TestClient(app) as client:`. Starlette 1.0.0's `_portal_factory` reuses the lifespan portal for WebSocket sessions, so `client.portal.call(broadcast_token, ...)` runs in the same event loop as the WebSocket handler. The test is valid.

---

## Verdict

✅ Ready to ship

No critical issues remain. The two warnings (W1: task GC, W2: broad RuntimeError catch) are low-risk for a local-only development tool and can be addressed in a follow-up hardening pass alongside Phase F work.
