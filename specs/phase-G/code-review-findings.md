# Code Review Findings

**Plan folder:** `specs/phase-G/code-review-findings.md` (fix pass)
**Date:** 2026-05-27
**Reviewers used:** 1
**Implementation scope:** Small — 6 targeted fixes across 4 files, 1 new test

---

## Summary

This pass applied all 6 fixes identified in the Phase G code review: `frame_b64` exclusion from JSONB persistence, lazy `numpy`/`Pillow` imports, stricter base64 validation, a clarified `removeprefix` pattern, dead test scaffolding removal, and an explicit `numpy` pin. All 66 tests pass. The reviewer found every fix correct and complete with no new issues introduced.

---

## Findings

### Critical Issues

None.

### Warnings

None.

### Suggestions

- The broad `except Exception` in `_decode_frame` is pre-existing style. It works but conflates decode, PIL open, and numpy conversion failures into one log message, which can make diagnosing the exact failure mode harder. Not a defect — noted for future observability improvements.
- `numpy>=1.24.0` is a conservative floor; `>=1.26.0` would be closer to what current wheel distributions target, but there is no compatibility risk at the current setting.

---

## Plan Conformance

All 6 fixes from the prior review's Critical and Warning/Suggestion items were implemented:

| Fix | Status |
|---|---|
| C1: Exclude `frame_b64` from JSONB payload | ✅ Applied — `model_dump(exclude={"frame_b64"})` |
| C2: Lazy `numpy`/`Pillow` imports | ✅ Applied — imports moved inside `_decode_frame` |
| W2: `removeprefix("COMMAND: ")` with trailing space | ✅ Applied |
| W3: `validate=True` in `base64.b64decode` | ✅ Applied |
| W4: Remove dead `fake_yolo` scaffolding in test | ✅ Applied |
| S1: Test asserting `frame_b64` not in persisted payload | ✅ Added — `test_perception_state_does_not_persist_frame_b64` |
| S3: `numpy>=1.24.0` in `requirements.txt` | ✅ Added |

Thread-safety fix (W1 from prior review) was intentionally deferred — it requires a `threading.Lock` around the singleton getters and is low-impact at current concurrency levels.

---

## Verdict

✅ **Ready to ship**

All prior critical and warning issues are resolved; 66 tests pass; no new issues found.
