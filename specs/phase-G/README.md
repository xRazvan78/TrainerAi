# Phase G — AutoCAD-Specific Perception (Execution Plan)

## Why this exists

`specs/phase-G-autocad-detection.md` describes two approaches (label-and-fine-tune YOLOv8 vs. a fixed-region heuristic) and a target end-state where the backend understands which AutoCAD command is on the command line, which dialog is open, etc. After auditing the code on `feature/phase-g`, the actual gap is narrower than the spec suggests: **everything around the inference is already in place** (frame capture, base64 transport, `frame_b64` field, JSONB persistence, perception → session-state hook). The only thing missing is the inference itself.

This execution plan replaces the spec's broad sketch with a concrete, verified scope split into four sub-phases.

## Context

What already works (do **not** rebuild):

- `trainerAI_overlay/src-tauri/src/capture.rs` captures AutoCAD via WGC at ~500 ms cadence, base64-encodes a 50%-downscale JPEG, computes an 8×8 aHash, and POSTs to `/api/perception/state` with `frame_hash` + `frame_b64` (Phase E).
- `trainerAI_backend/app/models/perception_models.py:11` — `PerceptionElement` already exposes `label`, `bbox`, `text`, `confidence` (the exact fields Phase G needs).
- `trainerAI_backend/app/models/perception_models.py:29` — `PerceptionStateRequest` already accepts `frame_b64` (max 280 000 chars, validated).
- `trainerAI_backend/app/routers/perception.py:17` — `POST /api/perception/state` persists the full payload as JSONB via `crud.create_perception_state(...)`.
- `trainerAI_backend/app/services/session_state_service.py:83` — `build_context_packet_foundation()` already fetches the latest perception state via `crud.get_latest_perception_state()` and includes it in the LLM context packet.
- `trainerAI_backend/app/services/embedder_service.py` — lazy-singleton, `lru_cache`-style model loading pattern that the new perception service will mirror.

What is missing (this phase fills it):

1. A `perception_service.py` that decodes `frame_b64`, runs OCR on a fixed command-line region, and (when fine-tuned weights are present) runs YOLOv8 across the rest of the UI.
2. A two-line patch in `routers/perception.py` that calls the service when `frame_b64` is present and the client did not pre-populate `elements`.
3. A perception-aware override in `session_state_service.update_session_from_command()` so the active tool is read from OCR'd command-line text in preference to the user's typed command.

After Phase G ships:

- A capture cycle containing an AutoCAD command-line strip reading `Command: LINE` populates `elements` with a `command_line` entry whose `text` field reads `LINE` (or similar).
- On the next `POST /api/command`, the resulting `SessionSnapshot.active_tool` is `LINE` — sourced from OCR, not from whatever the user typed.
- Dropping a future fine-tuned `autocad_yolov8.pt` into `app/models_weights/` activates the YOLO branch with **no code changes**.

## Two reconciliations with the original spec

1. **Heuristic + YOLO-ready scaffold, not full fine-tuning.** The spec recommends Option B (heuristic) for the command line and Option A (fine-tuned YOLO) for toolbar buttons. Labelling 200–400 screenshots and training a YOLOv8 model is several hours of out-of-VS-Code work that does not block the MVP signal — the command line is what drives `active_tool`, and that comes entirely from the heuristic. We ship the heuristic path now and structure `perception_service.py` so that a `best.pt` dropped into `app/models_weights/autocad_yolov8.pt` is auto-detected and merged with heuristic output. No code change is required when the model arrives.

2. **Inference runs inline via `asyncio.to_thread`, not as a background task.** The spec snippet shows `await asyncio.to_thread(analyse_frame, ...)` before persist; we keep that shape. Persisting twice (once raw, once enriched) would force two JSONB rows per frame at 2 Hz, and `build_context_packet_foundation()` already reads only the latest row. On CPU the round-trip is closer to 800 ms–1.5 s for EasyOCR alone; the capture loop's frame-dedup (Hamming-distance < 10) already keeps the call rate well below the perception cadence, so back-pressure is not a concern in practice. If real-world latency proves prohibitive we can revisit in a follow-up.

Capture cadence, aHash, JPEG quality, and Phase E/F behavior are not touched.

## Phase dependency graph

```
G.1 (deps + weights dir) ──► G.2 (perception_service.py) ──► G.3 (router + session wiring) ──► G.4 (verify)
```

G.2 depends on the new packages from G.1. G.3 imports `analyse_frame` from G.2. G.4 is pure verification.

## Sub-phase index

| File | Phase | Summary |
| ---- | ----- | ------- |
| [01-dependencies-and-weights.md](01-dependencies-and-weights.md) | G.1 | Add `ultralytics`, `easyocr`, `Pillow` to `requirements.txt`; create `app/models_weights/.gitkeep`; ignore `*.pt`. |
| [02-perception-service.md](02-perception-service.md) | G.2 | New `app/services/perception_service.py`: lazy-loaded EasyOCR + optional YOLO, fixed-region command-line heuristic, decode-safe `analyse_frame()`. |
| [03-router-and-session-integration.md](03-router-and-session-integration.md) | G.3 | Two-line patch in `routers/perception.py` to call `analyse_frame` when `frame_b64` is present; new `_extract_active_tool_from_perception()` in `session_state_service.py` and override in `update_session_from_command()`. |
| [04-verification-acceptance.md](04-verification-acceptance.md) | G.4 | Unit tests for `perception_service`, integration test through the router, end-to-end smoke against real AutoCAD. |

## Definition of done for the whole phase

- POSTing a frame containing the AutoCAD command-line strip (or any screenshot with the active command typed at the bottom) results in a persisted perception row whose `elements` contains a `command_line` entry with non-empty `text`.
- On the next `POST /api/command`, `SessionSnapshot.active_tool` is the OCR'd command (e.g. `LINE`, `CIRCLE`), **overriding** whatever was extracted from the typed command text.
- The YOLO branch is dormant when no `autocad_yolov8.pt` is present and remains dormant without raising — the heuristic still runs.
- Dropping any `*.pt` (even `yolov8n.pt`) into `app/models_weights/autocad_yolov8.pt` activates the YOLO branch on the next process start; no source edits required.
- `pytest tests/` passes; the new `test_perception_service.py` and the new integration test in `test_perception_api.py` both pass.
- No edits to `trainerAI_overlay/`. No DB schema changes.

## Out of scope for Phase G

- Labelling AutoCAD screenshots and fine-tuning YOLOv8. Documented in `specs/phase-G-autocad-detection.md` as a follow-up; `app/models_weights/` is provisioned for it.
- A separate perception WebSocket / streaming endpoint. Perception remains a passive frame log (Phase E semantics), read on-demand by `build_context_packet_foundation()`.
- Dialog-box / properties-panel-aware prompt construction. Those classes are wired through `perception_service` when YOLO is active but the prompt builder is not changed in this phase.
- Multi-language OCR (English only).
- GPU EasyOCR (`gpu=False`). The user can flip it once they confirm CUDA works.

## Tech stack additions

- Python (backend only):
  - `ultralytics>=8.3.0` (pulls a compatible `torch` if missing; `torch` is already pinned, so this is just YOLOv8).
  - `easyocr>=1.7.0`.
  - `Pillow>=10.0.0` (image decode).
- Rust / JS: none.

`numpy` arrives transitively. `opencv-python-headless` is already pinned and reused.

## Reused existing code

- `PerceptionElement` (`app/models/perception_models.py:11`) — output type of `analyse_frame`. Do **not** add fields.
- `crud.get_latest_perception_state()` (already called from `session_state_service.build_context_packet_foundation()`) — reused by the new active-tool override.
- Lazy-singleton model loading pattern from `embedder_service.py` — followed verbatim in `perception_service.py`.
- The TestClient + monkeypatch pattern from `tests/test_perception_api.py` — followed verbatim for new tests.
