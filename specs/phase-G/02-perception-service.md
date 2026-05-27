# Phase G.2: Perception Service

## Overview

Add `trainerAI_backend/app/services/perception_service.py`. This is the single new piece of runtime code in Phase G. It takes a base64-encoded JPEG, runs EasyOCR over a fixed command-line region, optionally runs YOLOv8 across the rest of the UI (only if fine-tuned weights are present), and returns a list of `PerceptionElement`s suitable for `crud.create_perception_state(...)`.

The service must:
- Lazy-load models exactly once per process.
- Never raise for bad input — perception failures degrade to an empty list, not a 500.
- Be importable without side effects (no model loads at import time).

## Prerequisites

- G.1 complete: `ultralytics`, `easyocr`, `Pillow` installed; `app/models_weights/` exists.
- `app/models/perception_models.py:11` defines `PerceptionElement` with `label: str`, `bbox: list[int] | None`, `text: str | None`, `confidence: float | None`.

## Goals

- New file `app/services/perception_service.py` exporting a single public function `analyse_frame(frame_b64: str) -> list[PerceptionElement]`.
- Heuristic path always runs: a fixed bottom-strip region of the decoded frame is OCR'd and emitted as a `command_line` element when OCR yields any text.
- YOLO path runs **only if** `app/models_weights/autocad_yolov8.pt` exists; it emits one element per detected box and overrides the heuristic `command_line` when YOLO produces one.
- All inference is synchronous within the function (caller wraps in `asyncio.to_thread`).
- Singleton model instances are cached at module level via a private getter (mirrors `embedder_service.py`'s `_get_model()` pattern).

## Technical Design

### Module layout

```python
# trainerAI_backend/app/services/perception_service.py
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from app.models.perception_models import PerceptionElement

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).parent.parent / "models_weights" / "autocad_yolov8.pt"
_YOLO_CONFIDENCE = 0.45
_COMMAND_LINE_STRIP_PX = 30
_OCR_CLASSES = frozenset({
    "command_line",
    "command_line_history",
    "dialog_box",
    "properties_panel",
})

_ocr_reader = None        # lazy: easyocr.Reader
_yolo_model = None        # lazy: ultralytics.YOLO | None (None means weights missing)
_yolo_loaded = False      # tri-state guard: distinguishes "not yet attempted" from "no weights"


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


def _get_yolo():
    global _yolo_model, _yolo_loaded
    if not _yolo_loaded:
        _yolo_loaded = True
        if _WEIGHTS_PATH.exists():
            from ultralytics import YOLO
            _yolo_model = YOLO(str(_WEIGHTS_PATH))
        else:
            _yolo_model = None
    return _yolo_model


def _decode_frame(frame_b64: str) -> np.ndarray | None:
    try:
        image_bytes = base64.b64decode(frame_b64, validate=False)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.asarray(image)
    except Exception:
        logger.exception("perception_service: failed to decode frame_b64")
        return None


def _ocr_region(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> str:
    region = frame[y1:y2, x1:x2]
    if region.size == 0:
        return ""
    try:
        results = _get_ocr().readtext(region)
    except Exception:
        logger.exception("perception_service: OCR failed for region")
        return ""
    return " ".join(r[1] for r in results).strip()


def _detect_command_line_heuristic(frame: np.ndarray) -> PerceptionElement | None:
    h, w = frame.shape[:2]
    y1 = max(0, h - _COMMAND_LINE_STRIP_PX)
    text = _ocr_region(frame, 0, y1, w, h)
    if not text:
        return None
    return PerceptionElement(
        label="command_line",
        bbox=[0, y1, w, h],
        text=text,
        confidence=1.0,
    )


def _detect_yolo(frame: np.ndarray, model) -> list[PerceptionElement]:
    try:
        results = model(frame, conf=_YOLO_CONFIDENCE, verbose=False)[0]
    except Exception:
        logger.exception("perception_service: YOLO inference failed")
        return []

    elements: list[PerceptionElement] = []
    for box in results.boxes:
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        class_id = int(box.cls[0])
        label = model.names[class_id]
        confidence = float(box.conf[0])
        text = _ocr_region(frame, x1, y1, x2, y2) if label in _OCR_CLASSES else ""
        elements.append(PerceptionElement(
            label=label,
            bbox=[x1, y1, x2, y2],
            text=text or None,
            confidence=confidence,
        ))
    return elements


def analyse_frame(frame_b64: str) -> list[PerceptionElement]:
    frame = _decode_frame(frame_b64)
    if frame is None:
        return []

    elements: list[PerceptionElement] = []

    heuristic = _detect_command_line_heuristic(frame)
    if heuristic is not None:
        elements.append(heuristic)

    yolo_model = _get_yolo()
    if yolo_model is not None:
        yolo_elements = _detect_yolo(frame, yolo_model)
        if any(e.label == "command_line" for e in yolo_elements):
            elements = [e for e in elements if e.label != "command_line"]
        elements.extend(yolo_elements)

    return elements
```

### Design decisions

- **Tri-state YOLO loading (`_yolo_loaded` boolean).** We need to distinguish "haven't tried yet" from "tried and found no weights". Without the flag, the absence of weights would cause a re-stat on every call.
- **`PerceptionElement.text=None` vs `""`.** The Pydantic model treats both as falsy. We default to `None` for YOLO regions with no OCR'd text and the empty `text` from missing OCR results gets normalized to `None` to avoid persisting empty strings that downstream `if el.get("text")` checks would short-circuit on. The heuristic path always emits a non-empty `text`.
- **No async.** EasyOCR and Ultralytics are sync; the caller wraps in `asyncio.to_thread`. Keeping the service function sync keeps tests trivial (no event loop).
- **30-pixel strip.** From `specs/phase-G-autocad-detection.md:343`. Tunable via `_COMMAND_LINE_STRIP_PX`. Do not parameterize through the function signature — that's premature.
- **`gpu=False` for EasyOCR.** Phase G ships CPU-only; users with CUDA can flip the constructor once they verify their env.

### What this service does **not** do

- It does not strip `Command:` prefixes or uppercase the OCR text. That belongs to `_extract_active_tool_from_perception()` in G.3.
- It does not deduplicate across frames. The capture-loop aHash filter (Phase E) already does that upstream.
- It does not log timings. If timing telemetry is later needed, wrap externally — keep this module side-effect-clean.

## Implementation Steps

1. Create `trainerAI_backend/app/services/perception_service.py` with the contents above.
2. Verify it imports without side effects:
   ```powershell
   python -c "from app.services.perception_service import analyse_frame; print('ok')"
   ```
   This must complete in well under a second — no model loads should fire.
3. Smoke-call with a 1×1 black PNG to confirm the empty-output path:
   ```powershell
   python -c "
   import base64
   from app.services.perception_service import analyse_frame
   # 1x1 black PNG
   pixel = base64.b64encode(bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6300000000050001a5d8b6e80000000049454e44ae426082')).decode()
   print(analyse_frame(pixel))
   "
   ```
   First call will trigger EasyOCR weight download (~64 MB) — expected one-time delay. Output should be `[]` (heuristic produces nothing on a 1×1 image; no YOLO weights present).

## File & Directory Changes

| Path | Change | Notes |
|---|---|---|
| `trainerAI_backend/app/services/perception_service.py` | Create | The whole sub-phase. |

## Testing & Validation

Unit tests for this module live in `tests/test_perception_service.py` (written in G.4). G.2 itself only needs to pass the import + smoke-call check above.

## Edge Cases & Risks

- **Truncated / malformed base64.** Handled by the `_decode_frame` try/except → returns `None` → `analyse_frame` returns `[]`. Logged at exception level so the operator sees it but the request still succeeds.
- **Frame smaller than 30 px.** `max(0, h - 30)` clamps `y1`; if `h <= 30`, OCR runs on the whole image. Acceptable — there is no realistic capture below 30 px.
- **EasyOCR loads slowly on first call.** Documented; this is a one-time cost per process, not per request.
- **YOLO model file is corrupted.** `YOLO(str(_WEIGHTS_PATH))` will raise; the `_get_yolo()` getter currently does not catch this. Acceptable for the MVP — a bad `.pt` is operator error and crashing on startup of the model surface is clearer than silently disabling YOLO. If we change our mind later, wrap the `YOLO(...)` call in try/except and log + set `_yolo_model = None`.
- **YOLO class names not in `_OCR_CLASSES`.** Such boxes are emitted with `text=None` and a populated `bbox` — downstream consumers should already treat `text` as optional (the Pydantic field is `Optional[str]`).

## Notes

- The chosen approach hews to the spec's `perception_service.py` skeleton at `specs/phase-G-autocad-detection.md:168–252` but adapts it to the actual `PerceptionElement` shape (`bbox` list, `text` field — not `x1/y1/x2/y2`/`ocr_text` as the spec snippet wrote).
- The YOLO merging rule (YOLO `command_line` wins over heuristic) is the only non-obvious behaviour — it exists because a real bounding box from a trained model is strictly more informative than the fixed-region heuristic.
