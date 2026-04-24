# Phase G — AutoCAD-Specific Detection

**Prerequisite for**: Production-quality guidance  
**Depends on**: Phase F (end-to-end pipeline working)  
**Estimated effort**: 8–14 hours  
**Outside VS Code work**: Yes — installing YOLOv8 dependencies, creating/labelling training data

---

## Goal

Move from generic screen capture to AutoCAD-aware perception. Instead of sending raw frames and hoping the LLM figures out context, this phase makes the backend understand exactly what the user is looking at: which toolbar buttons are visible, what command is typed in the command line, which dialog is open, and what is selected on the canvas.

This enables far more targeted and useful guidance.

---

## What Gets Added

```
Raw JPEG frame  (from Phase E WGC capture)
        │
        ▼
[YOLOv8 inference]              → detects AutoCAD UI elements
        │                          (command_line, toolbar_button, dialog, canvas)
        ▼
[EasyOCR on detected regions]   → reads text from command_line, dialog text fields
        │
        ▼
Structured perception payload:
{
  "elements": [
    {"label": "command_line", "x1":0,"y1":1035,"x2":800,"y2":1060, "text":"LINE "},
    {"label": "toolbar_button", "x1":55,"y1":85,"x2":90,"y2":110, "text":"", "confidence":0.91},
    ...
  ]
}
        │
        ▼
POST /api/perception/state   (already implemented — just fill elements array)
        │
        ▼
session_state_service reads active command from elements[label=command_line].text
```

---

## Outside VS Code — Installing YOLOv8

YOLOv8 runs in the Python backend environment.

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
.venv\Scripts\Activate.ps1

pip install ultralytics>=8.3.0
pip install easyocr>=1.7.0
pip install Pillow>=10.0.0
```

`ultralytics` pulls PyTorch automatically. For GPU inference, ensure you have CUDA-compatible PyTorch:

```powershell
# Check if GPU is available
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

If this prints `False`, install the CUDA build of PyTorch from https://pytorch.org/get-started/locally/ before running ultralytics.

---

## AutoCAD UI Elements to Detect

| YOLOv8 Class           | Description                                  | Why It Matters                                |
| ---------------------- | -------------------------------------------- | --------------------------------------------- |
| `command_line`         | The bottom command line input area           | The primary signal for what the user is doing |
| `command_line_history` | The command history above the input          | Provides recent action context                |
| `toolbar_button`       | Buttons in the ribbon/toolbar                | Detect which tool group is active             |
| `dialog_box`           | Modal dialogs (Save, Export, Options, etc.)  | User is in a blocking interaction             |
| `canvas_selection`     | Blue selection bounding boxes on the canvas  | User has selected objects                     |
| `properties_panel`     | Right-side Properties/Quick Properties panel | User inspecting element properties            |
| `layer_dropdown`       | Layer selector in ribbon                     | Layer context                                 |

---

## Approach: Fine-Tuned YOLOv8 on AutoCAD Screenshots

### Option A — Label Your Own Data (Best quality, more work)

1. Collect 200–400 screenshots of AutoCAD in various states
2. Label them using [Label Studio](https://labelstud.io/) or [Roboflow](https://roboflow.com/)
3. Export in YOLOv8 format
4. Fine-tune `yolov8n.pt` (nano, fastest) on your labelled data

### Option B — Zero-Shot with YOLOv8 + Manual Region Heuristics (Faster to get started)

AutoCAD's UI is consistent across versions. Use fixed-region heuristics for the command line (always at the very bottom of the AutoCAD window) and detect dialogs by window title. Use YOLOv8 only for the ribbon area where toolbar buttons change.

**Recommended starting approach**: Option B for the command line (high reliability, no training needed), Option A for toolbar detection when you have time.

---

## Outside VS Code — Creating Training Data (Option A)

### 1. Set up Label Studio

```powershell
pip install label-studio
label-studio start
# Opens at http://localhost:8080
```

### 2. Create a project

- Select "Object Detection with Bounding Boxes"
- Upload AutoCAD screenshots (PNG/JPEG)
- Add labels: `command_line`, `toolbar_button`, `dialog_box`, `canvas_selection`, `properties_panel`, `layer_dropdown`

### 3. Label images

Annotate 50+ images per class minimum. The command line is easy to label (always bottom strip). Toolbar buttons are smaller and need more examples.

### 4. Export and convert

Export in YOLO format from Label Studio. This produces:

```
labels/
    train/
        image001.txt  ← bounding box annotations
    val/
        image050.txt
images/
    train/
        image001.png
    val/
        image050.png
data.yaml             ← class definitions
```

### 5. Fine-tune YOLOv8

```powershell
python -c "
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.train(
    data='path/to/autocad_data.yaml',
    epochs=50,
    imgsz=1280,
    batch=8,
    name='autocad_ui_detector',
    device=0   # GPU; use 'cpu' if no GPU
)
"
```

The trained weights will be at `runs/detect/autocad_ui_detector/weights/best.pt`. Copy this to:

```
trainerAI_backend/app/models_weights/autocad_yolov8.pt
```

---

## In VS Code — New Backend Service: `perception_service.py`

```python
"""
Runs YOLOv8 + EasyOCR on a base64-encoded frame to detect AutoCAD UI elements.
Called from the perception router when a frame_b64 field is present in the payload.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import List

from PIL import Image

from app.models.perception_models import PerceptionElement

# Lazy-loaded model instances (loaded on first call, cached in process)
_yolo_model = None
_ocr_reader = None
_WEIGHTS_PATH = Path(__file__).parent.parent / "models_weights" / "autocad_yolov8.pt"
_YOLO_CONFIDENCE = 0.45
_OCR_CLASSES = {"command_line", "command_line_history", "dialog_box", "properties_panel"}


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        if _WEIGHTS_PATH.exists():
            _yolo_model = YOLO(str(_WEIGHTS_PATH))
        else:
            # Fallback to base model if no fine-tuned weights yet
            _yolo_model = YOLO("yolov8n.pt")
    return _yolo_model


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


def analyse_frame(frame_b64: str) -> List[PerceptionElement]:
    """
    Run YOLOv8 + EasyOCR on a base64 JPEG frame.
    Returns a list of detected PerceptionElement objects.
    """
    # Decode base64 to PIL image
    image_bytes = base64.b64decode(frame_b64)
    image = Image.open(io.BytesIO(image_bytes))
    import numpy as np
    frame_array = np.array(image)

    # YOLOv8 inference
    model = _get_yolo()
    results = model(frame_array, conf=_YOLO_CONFIDENCE, verbose=False)[0]

    elements: List[PerceptionElement] = []
    ocr = _get_ocr()

    for box in results.boxes:
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        class_id = int(box.cls[0])
        label = model.names[class_id]
        confidence = float(box.conf[0])

        # Run OCR on text-bearing regions
        ocr_text = ""
        if label in _OCR_CLASSES:
            region = frame_array[y1:y2, x1:x2]
            if region.size > 0:
                ocr_results = ocr.readtext(region)
                ocr_text = " ".join(r[1] for r in ocr_results).strip()

        elements.append(PerceptionElement(
            x1=x1, y1=y1, x2=x2, y2=y2,
            label=label,
            ocr_text=ocr_text,
            confidence=confidence,
        ))

    return elements
```

---

## In VS Code — Update Perception Router

In `trainerAI_backend/app/routers/perception.py`, check for `frame_b64` in the payload and run inference:

```python
# In the POST /api/perception/state handler, before persisting:
from app.services.perception_service import analyse_frame

if request.frame_b64:
    # Run vision inference — this replaces/augments any elements sent by client
    detected_elements = await asyncio.to_thread(analyse_frame, request.frame_b64)
    # Merge with any elements already in the request (client-side detections take priority)
    if not request.elements:
        request.elements = detected_elements
```

---

## In VS Code — Update Session State Service

In `session_state_service.py`, extract the active command from detected `command_line` elements:

```python
def _extract_active_tool_from_perception(perception_state: dict | None) -> str | None:
    """
    Read the command_line OCR text from the latest perception state.
    Returns the detected AutoCAD command or None if not found.
    """
    if not perception_state:
        return None
    elements = perception_state.get("elements", [])
    for el in elements:
        if el.get("label") == "command_line" and el.get("ocr_text"):
            # Command line shows: "Command: LINE" or just "LINE "
            text = el["ocr_text"].strip().upper()
            # Strip "Command:" prefix if present
            text = text.removeprefix("COMMAND:").strip()
            # Return first word (the command)
            parts = text.split()
            return parts[0] if parts else None
    return None
```

Use this in `update_session_from_command()` to override the active_tool extraction when perception data is available.

---

## Outside VS Code — Test the Perception Pipeline

```powershell
# Take a screenshot of AutoCAD
# Save it as test_frame.png
# Encode to base64 and POST to the perception endpoint

$bytes = [System.IO.File]::ReadAllBytes("C:\path\to\autocad_screenshot.png")
$b64 = [System.Convert]::ToBase64String($bytes)

$body = @{
    session_id = "test-session"
    timestamp = (Get-Date -Format o)
    elements = @()
    source = "test"
    frame_b64 = $b64
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/perception/state -Body $body -ContentType "application/json"

# Then query the saved perception state
Invoke-RestMethod -Uri "http://localhost:8000/db/perception_states?session_id=test-session"
```

The returned `elements` array should contain detected bounding boxes with class labels and OCR text.

---

## Outside VS Code — AutoCAD Command Line Region Heuristic (No Training Needed)

If you want a quick win before training a YOLOv8 model, hardcode the AutoCAD command line region using a fixed pixel offset from the bottom of the captured window:

```python
# autocad_heuristics.py
def get_command_line_region(frame_height: int, frame_width: int):
    """
    AutoCAD's command line is typically at the bottom ~25px of the window,
    spanning full width. This is consistent across AutoCAD 2020–2025 with
    the default dark theme.
    Returns (x1, y1, x2, y2).
    """
    return (0, frame_height - 30, frame_width, frame_height)
```

Use EasyOCR on this fixed region to detect the active command without any YOLOv8 model at all.

---

## Acceptance Criteria

- [ ] Backend correctly detects the `command_line` element from AutoCAD screenshots
- [ ] OCR correctly reads the typed command from the command line region
- [ ] `session_snapshot.active_tool` is populated from OCR text (not just first word of command text)
- [ ] YOLOv8 correctly identifies toolbar buttons and dialogs (if model is trained)
- [ ] Perception round-trip (capture → detect → OCR → session update) completes in < 300ms

---

## Training Data Tips

- Capture screenshots during actual AutoCAD use sessions — 10 minutes of use gives many diverse states
- Capture different AutoCAD versions (2022, 2023, 2024, 2025) for robustness
- Include both light and dark themes
- Include different screen resolutions (1920×1080, 2560×1440, 4K)
- Focus on the command line label — this is the most important class for the MVP
