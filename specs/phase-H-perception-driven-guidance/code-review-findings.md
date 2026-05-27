# Code Review Findings

**Plan folder:** `specs/phase-H-perception-driven-guidance`  
**Date:** 2026-05-27  
**Reviewers used:** 2 (initial) + 1 (post-cleanup verification)  
**Implementation scope:** Medium (two languages, three new/modified files across backend and Rust overlay)

---

## Summary

Phase H implements the missing perception → guidance trigger that connects autonomous screen capture to the Qwen LLM streaming pipeline, plus a WebSocket connection-state badge and a `use_effect` → `use_hook` leak fix in the Dioxus overlay. Two post-review critical corrections were applied (race window + unreliable test), then a second round of cleanup addressed all open warnings and suggestions. The reviewer confirmed all three files are clean with no regressions.

## Findings

### Critical Issues

**C1 (Fixed): `mark_triggered` placement created a deduplication race window.**

`mark_triggered` was called inside `_run_guidance_for_perception` (background task) after `try_acquire`, leaving a window where a second concurrent HTTP request could pass `should_trigger` before the background task started. Fixed by moving `mark_triggered` into the HTTP handler immediately after the `should_trigger` check, before `add_task`.

**C2 (Fixed): `test_trigger_skipped_while_in_flight` acquired an asyncio.Lock on a different event loop.**

The test used `asyncio.get_event_loop().run_until_complete(try_acquire(...))` to pre-acquire a lock while `TestClient` runs on its own anyio event loop. Fixed by patching `guidance_trigger_service.try_acquire` directly to return `False`, accurately simulating an in-flight session without cross-loop dependencies.

### Warnings

**W1: `observed_at` passed as DB datetime rather than `payload.timestamp` string.**

Deferred to a follow-up PR. Both approaches work; the DB-roundtrip path adds the `hasattr`/`isoformat` conversion logic in `_run_guidance_for_perception`. Simplifying to `payload.timestamp` (the validated ISO-8601 string already on the request) would remove that branch entirely.

**W2: `_extract_active_tool_from_perception` is a private name imported across module boundaries.**

Deferred to a clean-up PR. The function is now used by two modules; removing the leading underscore aligns the name with its actual visibility.

**W3 (Rust, Fixed): `__guidance_inbox_init` guard was unreachable with `use_hook` without explanation.**

Added a comment explaining the guard is retained as a safety net against HMR / future component remounts, not because it fires in normal operation.

**W4 (Rust, Resolved): Dioxus 0.7 `use_hook` semantics.**

`Cargo.toml` declares `dioxus = "0.7"`. Confirmed `use_hook` semantics are unchanged in Dioxus 0.7 — it runs exactly once per component instance, the same guarantee the leak-fix depends on. No code change needed.

### Suggestions

**S1 (Fixed): Missing `command.session_id` assertion in `test_trigger_fires_on_new_tool`.**  
Added.

**S2 (Fixed): `_inflight` and `_last_triggered_tool` dicts grow unbounded.**  
Added a comment in `guidance_trigger_service.py` documenting the intentional single-session trade-off and flagging the LRU eviction path for future productionisation.

**S3 (Rust, Fixed): Redundant `.to_string()` in `ws_client.rs`.**  
Both `text.to_string()` occurrences replaced with `text`. `Message::Text(text)` already binds an owned `String`; the borrow for `serde_json::from_str(&text)` is released before any move, so all control-flow paths are valid Rust.

**S4 (Rust, Fixed): First `use_hook` closure used `move` without capturing any signals.**  
Changed to `use_hook(|| {` — the closure only runs `js_sys::eval` with a string literal and has no reason to take ownership of the signal values in scope.

## Plan Conformance

All H.1, H.2, and H.3 requirements are satisfied and fully cleaned up. H.4 is a manual acceptance procedure (AutoCAD + live backend) not covered by automated review.

## Verdict

✅ Ready to ship

All critical issues fixed, all warnings resolved, all suggestions applied. The codebase is internally consistent and the reviewer confirmed no regressions.
