# Code Review Findings

**Plan folder:** `specs/plan-mode-tutor/`
**Date:** 2026-06-03
**Reviewers used:** 3 (2 initial + 1 fix-verification)
**Implementation scope:** Large — 16 new/modified files across Python backend and Rust/Tauri/Dioxus overlay

---

## Summary

Plan Mode (goal-driven tutor) was implemented in full, reviewed, and all critical/warning issues were resolved. The backend Python code is correct, tested (18/18 tests pass), and hardened against transient failures. The Rust overlay has all blocking defects fixed including the click-through region, streaming race conditions, and WS status emission. No outstanding critical or warning issues remain.

---

## Findings

### Critical Issues

None.

---

### Warnings

None.

---

### Suggestions

**[Backend] S1 — `chat()` return type annotation should be `AsyncGenerator[str, None]`**
`chat()` is declared as `async def chat(...) -> AsyncIterator[str]`. An async generator function should be annotated `AsyncGenerator[str, None]` per PEP 525. While CPython accepts `AsyncIterator[str]` at runtime, type-checkers (mypy/pyright) will flag it. Low priority.

**[Backend] S2 — Message history in `chat()` is unbounded**
All previous `plan.messages` (including the initial plan summary) are sent to Mistral on every turn. As conversations grow, this increases prompt token count. For v1 single-session use this is fine; for longer sessions, a sliding-window trim would prevent eventual context overflow.

---

## Changes Applied (Fix Summary)

### Backend Python

| Fix | File | Change |
|-----|------|--------|
| C1 | `app/routers/plan.py` | `_bg_tasks` set + `_schedule()` helper pins task refs; both `plan_create`/`plan_message` use `_schedule`. Test mock updated to return `MagicMock()`. |
| C2 | `app/services/llm_service.py` | `logger.exception(...)` before `return []` in `generate_plan_json`; added `import logging` + `logger`. |
| W2 | `app/services/rag_service.py` | Added `safe_retrieve_for_query` wrapping `retrieve_for_query` with same exception guard as `safe_retrieve_context_documents`. |
| W2 | `app/services/plan_service.py` | Both `retrieve_for_query` calls changed to `safe_retrieve_for_query`. |
| S1 | `app/services/plan_service.py` | Redundant `_plans[session_id] = plan` removed from `chat()` no-plan branch. |
| W4 | `app/services/plan_broadcaster.py` | Dead `_PING_INTERVAL_SECONDS = 20` constant removed. |
| W3 | `app/models/plan_models.py` | `PlanClearRequest = PlanAdvanceRequest` alias added; `plan_clear` endpoint uses it. |
| W5 | `app/models/plan_models.py` | `max_length=2000` added to `goal` and `text` fields. |
| W9 | `tests/test_plan_service.py` | 3 new tests: `test_advance_manual_last_step_boundary`, `test_chat_no_plan_triggers_generate`, `test_chat_existing_plan_streams_tokens`. |
| W9 | `tests/test_plan_api.py` | 3 new tests: `test_plan_message_returns_202`, `test_advance_manual_last_step_becomes_inactive`, `test_perception_with_completed_plan_resumes_reactive_guidance`. `mock_broadcast.assert_called_once()` added to existing perception test. |

### Rust Overlay

| Fix | File | Change |
|-----|------|--------|
| C3 | `src/main.rs` | `plan_streaming.set(false)` added in Close Plan onclick alongside other signal resets. |
| C4 | `src/main.rs` | Token inbox drain new-message and append branches both guarded by `*plan_mode.read()`. |
| C5 | `src-tauri/src/lib.rs` | Click-through region widened from `0..370/0..540` to `0..400/0..900`. |
| C6 | `src-tauri/src/ws_client.rs` | Both early-return guards emit `plan-ws-status: connected: false`. Successful connect emits `connected: true`. Disconnect emits `connected: false`. |
| W6 | `src-tauri/src/commands.rs` | `send_command` and `start_capture` now call `session_id()` helper. |
| W7 | `src-tauri/src/ws_client.rs` | Non-JSON messages and unknown type fields now log via `eprintln!`. |
| W8 | `src/main.rs` | Next button guarded by `steps_len > 0 && current < steps_len`. |
| S4 | `src/main.rs` | Glyph match has explicit `"pending"` arm and named `other` catch-all with `eprintln!`. |

---

## Plan Conformance

All 5 phases from the original plan are implemented and verified. All 6 critical issues from the first review are resolved. All 9 warning items are addressed. 18/18 backend tests pass.

---

## Verdict

✅ **Ready to ship**

All blocking defects are fixed, tests are green, and the two remaining suggestions are minor type-annotation and UX polish items that do not affect correctness.
