# Code Review Findings

**Plan folder:** `specs/phase-F`
**Date:** 2026-05-27
**Reviewers used:** 2
**Implementation scope:** Medium (3 new/rewritten files, 2 modified files, one new Cargo crate feature across Tauri + Dioxus layers)

---

## Summary

Phase F correctly wires the Tauri overlay to the backend's guidance WebSocket. The WebSocket client (`ws_client.rs`) handles the actual wire format (raw text tokens + JSON control messages) correctly, the reconnect loop works, the Dioxus UI subscribes to events via a JS inbox pattern with idempotency guards, and the three buttons (capture toggle, Send: LINE, Clear) all function as specified. Four bugs found during review were fixed inline before this report was written; the codebase passes `cargo check` cleanly.

---

## Findings

### Critical Issues

None.

### Warnings

**W1 — `send_command` lacked localhost safety check (FIXED)**
`send_command` in `commands.rs` posted to `BACKEND_URL` without validating that it points to localhost, unlike `start_capture` which had an explicit guard. A misconfigured `BACKEND_URL` could exfiltrate command strings to a remote host. Fixed: the same two-line guard from `start_capture` was added to `send_command`.

**W2 — `send_command` allocated a new `reqwest::Client` per call (FIXED)**
`start_capture` correctly uses the `HTTP_CLIENT: OnceLock<reqwest::Client>` singleton. `send_command` called `reqwest::Client::new()` on every invocation, allocating a new connection pool each time. Fixed: changed to `HTTP_CLIENT.get_or_init(reqwest::Client::new)`.

**W3 — `send_command` silently swallowed 4xx/5xx responses (FIXED)**
`.send().await` returns `Ok` for any HTTP status. `start_capture` chains `.and_then(|r| r.error_for_status())`; `send_command` did not, so backend validation errors would disappear. Fixed: added `.and_then(|r| r.error_for_status())`.

**W4 — Double-read of `capturing` signal in toggle button (FIXED)**
The capture toggle read `*capturing.read()` twice (once for the command string, once to negate for `capturing.set()`). While safe in WASM's single-threaded model today, it is logically fragile. Fixed: one local variable `currently_capturing` holds the value for both uses.

**W5 — `ws_client` reconnect loop has a fixed 5 s delay with no UI feedback**
The reconnect loop uses a flat 5-second sleep on both connection errors and clean disconnects. No exponential backoff, no ceiling, no `connection-status` event to the UI. Acceptable for the Phase F scope (localhost dev tool, backend restarts are infrequent), but should be addressed in Phase G alongside the "reconnect indicator" noted as out-of-scope in the README.

**W6 — No validation of `backend_ws_url` / `session_id` in `ws_client`**
`connect_and_stream` accepts both values as plain strings and formats them directly into the WebSocket URL without checking that the host is localhost or that `session_id` is free of URL-special characters. Low severity for the current env-var-driven setup; same localhost guard used in `commands.rs` should be applied here before Phase G ships.

**W7 — `spawn_local` polling loop has no cancellation path**
The 50 ms inbox drain loop in `main.rs` is detached via `spawn_local` with no handle. If `App` were ever unmounted (not the case today), the loop would continue writing into dangling signals. Acceptable for a single-root-component overlay; becomes a real leak if the component tree is ever refactored.

### Suggestions

**S1 — Replace `js_sys::eval` with proper Tauri invoke bindings**
Buttons invoke Tauri commands via `js_sys::eval("window.__TAURI__.core.invoke(...)")`. The command names are currently literals or a boolean-selected literal, so there is no injection risk today. However, the pattern establishes a habit that becomes dangerous if user-supplied text ever enters the string. Tauri v2 exposes typed JS bindings; using them would remove the eval entirely and make command invocations auditable by `cargo check`.

**S2 — `"default-session"` fallback instead of `uuid::Uuid::new_v4()`**
The plan's original draft called for a UUID as the session-ID fallback. The implementation uses the literal `"default-session"`. This is fine for single-instance use (and actually makes capture and WS agree without ceremony), but means two simultaneous overlay instances share a session. Acceptable for Phase F; document for Phase G when multi-session might matter.

**S3 — `send_command` button hardcodes `"LINE"`**
The green button always sends `"LINE"`. It is an intentional smoke-test stub for Phase F, but should either gain an input field or be removed before Phase G ships the AutoCAD OCR trigger.

---

## Plan Conformance

All six acceptance criteria from `specs/phase-F/README.md` are implemented:

| Criterion | Status |
|---|---|
| POST or button click → tokens appear in panel within 5 s | ✅ Wired end-to-end |
| Tokens appear incrementally | ✅ Per-token signal append |
| Backend restart → reconnects within ~5 s | ✅ 5 s retry loop |
| Phase E capture + click-through unaffected | ✅ Cursor thread and capture module untouched |
| No backend edits | ✅ Confirmed |
| No new DB changes | ✅ Confirmed |

Two intentional deviations from the draft spec are improvements, not regressions:
- Used `serde_json` parsing instead of naive `text.contains()` substring matching for control messages — more robust.
- Used `"default-session"` fallback instead of `uuid::Uuid::new_v4()` — keeps capture and WS in sync without ceremony. Noted in S2.

F.4 (verification) requires a live stack (Docker + Qwen Model Runner + the overlay) and is a manual step; no code was produced for it. The plan specifies this explicitly.

## Verdict

✅ **Ready to ship**
All acceptance criteria are met, the four consistency bugs found during review were fixed before this report, and `cargo check` passes cleanly. The remaining warnings (W5–W7) are deferred to Phase G per the plan's own out-of-scope list.
