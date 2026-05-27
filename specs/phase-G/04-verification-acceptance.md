# Phase G.4: Verification & Acceptance

## Overview

Write the test coverage for `perception_service`, extend the router integration test, add a session-state override test, then run a manual end-to-end smoke against a real AutoCAD instance. This sub-phase is what proves Phase G ships.

## Prerequisites

- G.1, G.2, G.3 complete.
- Backend env can import `ultralytics`, `easyocr`, `Pillow`.
- For the end-to-end smoke: AutoCAD installed and runnable on the same machine; backend, overlay (`cargo tauri dev`), and Docker Model Runner all running.

## Goals

- New file `tests/test_perception_service.py` with four unit tests covering the heuristic path, the YOLO-wins-over-heuristic path, the decode-failure path, and the no-weights-skips-YOLO path.
- Extended `tests/test_perception_api.py` with one integration test that POSTs `frame_b64` + empty `elements` and asserts the persisted JSONB payload contains the elements that `analyse_frame` returned.
- Extended session-state coverage with one test asserting perception overrides typed command.
- Manual end-to-end smoke documented and executed: AutoCAD command-line OCR → `SessionSnapshot.active_tool` reflects the OCR'd command.
- `pytest tests/ -q` passes.

## Technical Design

### Test patterns to follow

- **Monkeypatch the inference primitives, not the public function.** Tests of `perception_service` mock `easyocr.Reader` and `ultralytics.YOLO` (or the module's `_get_ocr` / `_get_yolo` getters). Tests of the router mock the public `analyse_frame` to keep the router test fast.
- **Synthetic frames.** Use a tiny in-memory image (PIL → BytesIO → base64) sized at least 100×100 px so the 30-px command-line strip is meaningful.
- **TestClient + monkeypatched `crud`.** Same shape as `tests/test_perception_api.py:50` (`_build_client` fixture).

### `tests/test_perception_service.py` (new)

Four tests:

1. **`test_analyse_frame_heuristic_extracts_command_line`**
   - Monkeypatch `perception_service._get_ocr` to return a stub object whose `readtext` returns `[((0,0,0,0), "Command: LINE", 0.95)]`.
   - Monkeypatch `perception_service._get_yolo` to return `None`.
   - Build a 200×200 black PIL image, encode to JPEG base64.
   - Assert `analyse_frame(b64)` returns exactly one element with `label == "command_line"`, `text` containing `"LINE"`, `bbox[1] == 170` (200 − 30), `bbox[3] == 200`.

2. **`test_analyse_frame_yolo_overrides_heuristic_command_line`**
   - Stub OCR to return `[((0,0,0,0), "heuristic-text", 0.95)]`.
   - Stub `_get_yolo` to return a fake model object: `model.names = {0: "command_line"}`, and `model(frame, ...)[0].boxes` yields one box with `xyxy=[[10,10,90,40]]`, `cls=[0]`, `conf=[0.88]`. OCR over that region returns `[((0,0,0,0), "LINE", 0.9)]`.
   - Assert there is **exactly one** `command_line` element in the output, and its `bbox == [10, 10, 90, 40]` (the YOLO one) — the heuristic strip element is dropped.

3. **`test_analyse_frame_decode_failure_returns_empty`**
   - Call `analyse_frame("not-base64!!!@@@")`.
   - Assert returns `[]` and does not raise.
   - Capture logs; assert an exception was logged (use `caplog`).

4. **`test_analyse_frame_no_weights_skips_yolo_silently`**
   - Monkeypatch `perception_service._WEIGHTS_PATH` to a non-existent path.
   - Reset `_yolo_loaded` and `_yolo_model` via `monkeypatch.setattr`.
   - Stub OCR to return some text.
   - Assert output contains the heuristic `command_line` element and no YOLO-derived elements; no exception.

   Note: because the service caches model loads at module level, each test must reset the module-level singletons (`_ocr_reader`, `_yolo_model`, `_yolo_loaded`). Add a `pytest` fixture:

   ```python
   @pytest.fixture(autouse=True)
   def _reset_perception_singletons(monkeypatch):
       import app.services.perception_service as ps
       monkeypatch.setattr(ps, "_ocr_reader", None)
       monkeypatch.setattr(ps, "_yolo_model", None)
       monkeypatch.setattr(ps, "_yolo_loaded", False)
       yield
   ```

### `tests/test_perception_api.py` (extend)

Add one new test:

- **`test_perception_state_enriches_with_analyse_frame_when_frame_b64_present`**
  - Build a valid `PerceptionStateRequest` payload with `frame_b64="<any>"` and `elements=[]`.
  - Monkeypatch `app.routers.perception.analyse_frame` (or wherever the import lands) to return a fixed `[PerceptionElement(label="command_line", bbox=[0,170,200,200], text="LINE", confidence=1.0)]`.
  - Monkeypatch `crud.create_perception_state` to capture the `payload` argument.
  - POST; assert 201; assert the captured payload's `elements` is a list of length 1 with the expected fields.

  Add a sibling test asserting the **skip** path:
- **`test_perception_state_does_not_enrich_when_elements_prepopulated`**
  - Payload with `frame_b64="<any>"` and `elements=[{...}]` (one pre-populated element).
  - Monkeypatch `analyse_frame` to raise if called.
  - POST; assert 201; assert `analyse_frame` was not invoked.

### Session-state test (extend or create)

If `tests/test_session_state_service.py` exists, extend it; otherwise add to `tests/test_command_api.py` since command-level tests already exercise the session flow there.

- **`test_active_tool_prefers_perception_over_typed_command`**
  - Seed `crud.get_latest_perception_state` (via monkeypatch) to return `{"payload": {"elements": [{"label": "command_line", "text": "Command: CIRCLE"}]}}`.
  - Call `update_session_from_command(...)` (or POST `/api/command`) with command text `"LINE"`.
  - Assert the resulting `SessionSnapshot.active_tool == "CIRCLE"`.

- **`test_active_tool_falls_back_to_typed_command_when_no_perception`**
  - Monkeypatch `crud.get_latest_perception_state` to return `None`.
  - Call with command text `"LINE"`.
  - Assert `active_tool == "LINE"`.

## Implementation Steps

1. Write `tests/test_perception_service.py` with the four tests + the autouse fixture above.
2. Append the two new tests to `tests/test_perception_api.py`. Reuse the existing `_build_client` fixture.
3. Add the two session-state tests to wherever active-tool extraction is currently covered. If unsure, search:
   ```powershell
   pytest --collect-only -q tests/ | Select-String -Pattern "active_tool|session_state"
   ```
4. Run the whole suite:
   ```powershell
   cd trainerAI_backend
   pytest tests/ -q
   ```
   All tests pass.

5. **Manual end-to-end smoke (requires AutoCAD).** Documented for the operator; not automated.

   a. Bring up the stack:
   ```powershell
   docker compose up -d
   cd trainerAI_backend
   uvicorn app.main:app --reload
   ```
   In another terminal:
   ```powershell
   cd trainerAI_overlay
   cargo tauri dev
   ```

   b. Open AutoCAD. Make sure the AutoCAD window is the foreground capture target. Type `LINE` in the command line; do not press Enter (so the text stays visible).

   c. Wait ~2 seconds for the next capture cycle. Confirm a new perception row landed:
   ```powershell
   Invoke-RestMethod "http://localhost:8000/db/perception_states?session_id=default-session" | Select-Object -First 1
   ```
   The returned row's `payload.elements` must contain a `command_line` entry whose `text` (case-insensitively) contains `LINE`.

   d. Issue a command through the overlay (the "Send: LINE" button from Phase F, or `Invoke-RestMethod` against `POST /api/command` with a different command text like `"CIRCLE"` to make the override observable). Inspect the resulting session state:
   ```powershell
   Invoke-RestMethod "http://localhost:8000/db/sessions?session_id=default-session"
   ```
   `active_tool` must equal `LINE` — sourced from OCR, not from the `CIRCLE` you POSTed.

   e. Confirm the LLM stream still works end-to-end (Phase F regression). The overlay panel should still receive token-by-token guidance.

## File & Directory Changes

| Path | Change | Notes |
|---|---|---|
| `trainerAI_backend/tests/test_perception_service.py` | Create | Four unit tests + autouse reset fixture. |
| `trainerAI_backend/tests/test_perception_api.py` | Modify | Two new integration tests. |
| `trainerAI_backend/tests/test_session_state_service.py` *or* `tests/test_command_api.py` | Modify | Two new active-tool override tests. |

## Testing & Validation

- `pytest tests/ -q` exits 0.
- The manual smoke (step 5) is executed once and the operator confirms the `active_tool == "LINE"` outcome.
- No new warnings in the pytest output beyond what was present before Phase G (model-deprecation noise from `ultralytics` is acceptable).

## Acceptance Criteria (whole-phase recap)

- [ ] `analyse_frame` decodes a base64 JPEG and returns at least one `command_line` element when the image contains readable text in the bottom 30 px.
- [ ] The router enriches the persisted payload when `frame_b64` is present and `elements` is empty.
- [ ] `SessionSnapshot.active_tool` is sourced from OCR'd command-line text whenever such text is available, otherwise from the typed command (existing behaviour).
- [ ] YOLO branch is dormant without weights; activating it requires only dropping a `.pt` file at `app/models_weights/autocad_yolov8.pt`.
- [ ] `pytest tests/ -q` passes.
- [ ] Manual AutoCAD smoke: typing `LINE` in AutoCAD and issuing any command via the overlay results in `active_tool == "LINE"`.

## Edge Cases & Risks

- **`caplog` not picking up the `_decode_frame` exception log.** EasyOCR / Ultralytics tend to install global log handlers; if `caplog` misses the message, set `caplog.set_level(logging.ERROR, logger="app.services.perception_service")` at the top of test 3.
- **EasyOCR weights download mid-test.** First test run after a fresh install will be slow (~64 MB download). On CI this is fine; document for the developer.
- **Fake YOLO model fixture is verbose.** Acceptable — the test in #2 is the only one that needs it, so the boilerplate is contained.
- **Manual smoke flakiness from frame timing.** If AutoCAD repaints the command line between capture and OCR, the OCR may catch a transient state. Re-type and wait one more cycle.

## Notes

- The manual smoke is the only step that requires AutoCAD. All other validation runs without it; this matters for CI and for developers who do not have AutoCAD locally.
- Once a fine-tuned `autocad_yolov8.pt` is produced (out-of-VS-Code work documented in `specs/phase-G-autocad-detection.md`), no additional Phase G work is needed — the YOLO branch turns on automatically on the next backend start. A follow-up phase may be warranted to teach the prompt builder about non-`command_line` classes (dialog_box, properties_panel) at that point.
