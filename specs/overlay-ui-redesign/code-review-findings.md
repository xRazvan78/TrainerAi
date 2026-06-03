# Code Review Findings

**Plan folder:** `specs/overlay-ui-redesign/code-review-findings.md` (fixes pass)
**Date:** 2026-06-03
**Reviewers used:** 1
**Implementation scope:** Small — 4 targeted fixes across 2 files

---

## Summary

Four fixes were applied to resolve issues flagged in the previous review of the overlay UI redesign. The critical dead-zone bug (C1: minimize handler sending wrong region) and the sidebar overshoot warning (W1) were corrected with precise geometry values. Two robustness improvements were also applied: mutex poison recovery (W3) and `__TAURI__` guards on JS eval calls (W4). All fixes are correct and complete.

---

## Findings

### Critical Issues

None.

---

### Warnings

**W2 — Half-open range excludes the last pixel column/row (deferred)**

`(rx..rx+rw).contains(&rel_x)` is exclusive at the end, so the right/bottom boundary pixel is not interactive. At 100% DPI this is a 1-pixel miss; at higher DPI it compounds. No DPI scale factor is applied. Accepted as a known follow-up per the original spec.

**W4 — `__TAURI__` guard does not verify `invoke` is a function**

The guard `if(window.__TAURI__&&window.__TAURI__.core)` does not check `typeof window.__TAURI__.core.invoke==='function'`. In the normal Tauri runtime, `invoke` is always present when `core` is, so this has no practical consequence. Low-priority hardening only.

**W5 — Three buttons in one flex row**

All three action buttons (Capture, Plan, Clear) are in a single `.btn-row`. The original spec pseudocode comment implied Capture separate from Plan+Clear. Functionally correct and visually compact — no change made.

**W6 — Pre-existing: `plan_create` vs `plan_message` dispatch races on `plan_steps`**

Not introduced by this change; not in scope to fix here.

---

### Suggestions

**S2 — Startup `set_interactive_region` is fire-and-forget**

The Rust-side OnceLock default `(0,0,412,1040)` no longer matches the corrected startup value `(0,0,396,1040)`. The polling thread will use `w:412` for the brief window between app start and the first WebView `set_interactive_region` IPC call. This is a tiny startup race (milliseconds) with minimal practical impact, but the invariant is no longer guaranteed by coincidence. A code comment noting this would help future maintainers.

---

## Plan Conformance

All four fixes from the previous findings report were implemented correctly:

- ✅ **C1 fixed**: Minimize handler now sends `{x:16,y:16,w:56,h:56}` — matches the badge's actual 56×56 px painted area at margin:16px
- ✅ **W1 fixed**: Startup hook and badge-restore now send `{x:0,y:0,w:396,h:1040}` — matches the sidebar's right edge at 16+380=396px
- ✅ **W3 fixed**: Both `lock().unwrap()` calls in `commands.rs` now use `.unwrap_or_else(|e| e.into_inner())` — prevents panic on mutex poisoning
- ✅ **W4 fixed**: All three `set_interactive_region` JS eval calls guarded with `if(window.__TAURI__&&window.__TAURI__.core){...}` — silent no-op in dev mode

---

## Verdict

✅ Ready to ship

All must-fix issues are resolved. The remaining warnings are either deferred by design (W2, W5, W6) or trivially low-risk (W4 guard completeness). The one new suggestion (S2 startup race) is cosmetic — the polling thread uses the OnceLock default for at most a few milliseconds before the first IPC call updates it.
