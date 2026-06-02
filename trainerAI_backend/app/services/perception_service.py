from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from app.models.perception_models import PerceptionElement

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).parent.parent / "models_weights" / "autocad_yolov8.pt"
_YOLO_CONFIDENCE = 0.45
# AutoCAD layout (bottom → top): layout-tab strip + status bar (~60px) → command line (~100px) → canvas.
# Skip the tab strip, then scan the command-line band above it.
_STATUS_BAR_PX = 55
_COMMAND_LINE_STRIP_PX = 100
_OCR_CLASSES = frozenset({
    "command_line",
    "command_line_history",
    "dialog_box",
    "properties_panel",
})

_ocr_reader = None
_yolo_model = None
_yolo_loaded = False


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
        import numpy as np
        from PIL import Image
        image_bytes = base64.b64decode(frame_b64, validate=True)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.asarray(image)
    except Exception:
        logger.exception("perception_service: failed to decode frame_b64")
        return None


def _boost_contrast(region) -> "np.ndarray":
    import numpy as np
    from PIL import Image, ImageOps
    img = Image.fromarray(region).convert("L")  # grayscale
    # Invert if the background is dark (AutoCAD dark theme)
    if np.asarray(img).mean() < 128:
        img = ImageOps.invert(img)
    # Upscale 2× — EasyOCR works better on larger text
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    return np.asarray(img)


def _ocr_region(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> str:
    region = frame[y1:y2, x1:x2]
    if region.size == 0:
        return ""
    enhanced = _boost_contrast(region)
    try:
        results = _get_ocr().readtext(enhanced, low_text=0.3, text_threshold=0.5)
    except Exception:
        logger.exception("perception_service: OCR failed for region")
        return ""
    return " ".join(r[1] for r in results).strip()


_DEBUG_CROP_SAVED = False

def _detect_command_line_heuristic(frame: np.ndarray) -> PerceptionElement | None:
    global _DEBUG_CROP_SAVED
    h, w = frame.shape[:2]
    # Read the band above the status bar where the command line lives.
    y_bottom = max(0, h - _STATUS_BAR_PX)
    y_top = max(0, h - _STATUS_BAR_PX - _COMMAND_LINE_STRIP_PX)
    if not _DEBUG_CROP_SAVED:
        _DEBUG_CROP_SAVED = True
        try:
            from PIL import Image
            crop = frame[y_top:y_bottom, 0:w]
            Image.fromarray(crop).save("debug_cmdline_crop.png")
            enhanced = _boost_contrast(crop)
            Image.fromarray(enhanced).save("debug_cmdline_enhanced.png")
            print(f"[ocr_heuristic] saved debug_cmdline_crop.png and debug_cmdline_enhanced.png (y={y_top}..{y_bottom})", flush=True)
        except Exception as e:
            print(f"[ocr_heuristic] crop save failed: {e}", flush=True)
    text = _ocr_region(frame, 0, y_top, w, y_bottom)
    print(f"[ocr_heuristic] raw text from y={y_top}..{y_bottom}: {text!r}", flush=True)
    if not text:
        return None
    return PerceptionElement(
        label="command_line",
        bbox=[0, y_top, w, y_bottom],
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


_DEBUG_FRAME_SAVED = False

def analyse_frame(frame_b64: str) -> list[PerceptionElement]:
    global _DEBUG_FRAME_SAVED
    frame = _decode_frame(frame_b64)
    if frame is None:
        return []

    if not _DEBUG_FRAME_SAVED:
        _DEBUG_FRAME_SAVED = True
        try:
            from PIL import Image
            h, w = frame.shape[:2]
            print(f"[analyse_frame] frame size: {w}x{h}", flush=True)
            Image.fromarray(frame).save("debug_capture.png")
            print("[analyse_frame] saved debug_capture.png in backend working dir", flush=True)
        except Exception as e:
            print(f"[analyse_frame] debug save failed: {e}", flush=True)

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
