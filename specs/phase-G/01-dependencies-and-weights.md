# Phase G.1: Dependencies & Weights Directory

## Overview

Add the three Python packages required for YOLOv8 + EasyOCR inference and provision a place for fine-tuned model weights to live in-tree without committing binaries. This is a pure-setup sub-phase — no runtime code is changed.

## Prerequisites

- Backend virtualenv exists at `trainerAI_backend/.venv/` and is activated.
- `torch` is already installed (pinned in current `requirements.txt`); a CUDA-enabled build is preferable but not required for this phase.

## Goals

- `ultralytics>=8.3.0`, `easyocr>=1.7.0`, `Pillow>=10.0.0` are installed and importable in the backend env.
- `trainerAI_backend/app/models_weights/` exists in-tree with a `.gitkeep` placeholder.
- `*.pt` weight binaries under that directory are gitignored.

## Technical Design

The three new packages slot in alongside the existing ML stack (`sentence-transformers`, `torch`, `openai-whisper`, `opencv-python-headless`) in `trainerAI_backend/requirements.txt`. `ultralytics` will pull a compatible `torch` if it disagrees with the pinned version — let `pip` resolve, do not pre-pin.

The weights directory is `trainerAI_backend/app/models_weights/`. Its location is significant: `perception_service.py` derives the path as `Path(__file__).parent.parent / "models_weights" / "autocad_yolov8.pt"`, so it must sit at `app/models_weights/`, not at the repo root.

`.gitkeep` is an empty file. The `*.pt` ignore rule should be scoped to that directory specifically — there are no other `.pt` files in the repo today, but a narrow rule documents intent.

## Implementation Steps

1. Open `trainerAI_backend/requirements.txt`. Append (preserve any trailing newline):
   ```
   ultralytics>=8.3.0
   easyocr>=1.7.0
   Pillow>=10.0.0
   ```
   Keep alphabetical-ish grouping with the existing ML packages if a clear order is visible; otherwise append at the bottom.

2. Install:
   ```powershell
   cd trainerAI_backend
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   First-time install of `easyocr` will be slow (~200 MB of model weights to follow on first inference call, not during install).

3. Smoke-import (do not commit; this is just to verify the env):
   ```powershell
   python -c "from ultralytics import YOLO; import easyocr; from PIL import Image; print('ok')"
   ```

4. Create the weights directory and its `.gitkeep`:
   ```powershell
   New-Item -ItemType Directory -Force -Path trainerAI_backend\app\models_weights | Out-Null
   New-Item -ItemType File -Force -Path trainerAI_backend\app\models_weights\.gitkeep | Out-Null
   ```

5. Update `.gitignore` at the repo root. If a root `.gitignore` exists, append:
   ```
   trainerAI_backend/app/models_weights/*.pt
   ```
   If no root `.gitignore` exists, create one with that single line. If a `trainerAI_backend/.gitignore` exists in addition, prefer adding the rule there with the relative path `app/models_weights/*.pt`. Do not commit any `.pt` file.

## File & Directory Changes

| Path | Change | Notes |
|---|---|---|
| `trainerAI_backend/requirements.txt` | Modify | Add three packages. |
| `trainerAI_backend/app/models_weights/` | Create | New directory. |
| `trainerAI_backend/app/models_weights/.gitkeep` | Create | Empty placeholder. |
| `.gitignore` (root or backend) | Modify | Ignore `*.pt` under the weights directory. |

## Testing & Validation

- `pip install -r requirements.txt` exits 0.
- `python -c "from ultralytics import YOLO; import easyocr; from PIL import Image"` exits 0.
- `git status` shows `.gitkeep` as untracked (or staged) and does not show any `.pt` file even after future weights are dropped in.
- Existing pytest suite is unchanged and still passes:
  ```powershell
  pytest tests/ -q
  ```

## Edge Cases & Risks

- **`ultralytics` re-installs `torch`.** If pip picks a `torch` version different from the one already pinned, `sentence-transformers` may need to be re-imported in a clean session. Verify with `pip check`; if it complains, re-pin `torch` to a version satisfying both.
- **EasyOCR weight download.** EasyOCR downloads its detector/recognizer weights (~64 MB English) on first `Reader([...])` instantiation, not at install time. This will surface in G.2/G.4, not here.
- **CUDA mismatch.** If the user has a CUDA-only `torch` and `ultralytics` resolves to a CPU build (or vice versa), `torch.cuda.is_available()` may flip. Document but do not block; EasyOCR is constructed with `gpu=False` in G.2 specifically to dodge this.
- **Whitespace at end of requirements.txt.** Some editors strip trailing newlines; `pip` does not care, but keep the file ending with a single newline for diff hygiene.

## Notes

- The `trainerAI_backend/app/models_weights/autocad_yolov8.pt` path is hard-coded in `perception_service.py` (G.2). Changing it later requires a code edit.
- For users who plan to fine-tune YOLOv8 later, the spec's training instructions in `specs/phase-G-autocad-detection.md` (lines 105–162) remain accurate — the only change is that the resulting `best.pt` should be copied to `app/models_weights/autocad_yolov8.pt`.
