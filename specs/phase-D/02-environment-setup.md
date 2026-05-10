# D.2 — Environment setup

**Depends on:** nothing (can run in parallel with D.1)
**Blocks:** D.3, D.4
**Estimated effort:** 30–45 min (plus model download time)

## Goal

Install the system-level tools (FFmpeg, optionally yt-dlp) and Python packages (Whisper, OpenCV) needed by the ingestion pipeline, and lock them in `requirements.txt`. Done once per developer machine.

## System tooling (Windows)

```powershell
# FFmpeg — required by Whisper for audio decoding
winget install Gyan.FFmpeg
# Restart PowerShell so PATH picks up the new entry
ffmpeg -version    # should print 6.x or newer

# yt-dlp — used in D.4 for sourcing tutorial videos with subtitles
winget install yt-dlp.yt-dlp
yt-dlp --version
```

If `winget` is not available, FFmpeg can be installed via `choco install ffmpeg` or by downloading a static build from https://www.gyan.dev/ffmpeg/builds/ and adding `bin/` to PATH.

## Python packages

```powershell
cd D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
.venv\Scripts\Activate.ps1

pip install openai-whisper opencv-python-headless
```

`openai-whisper` pulls in `torch` transitively — but the project already has `torch>=2.3.0` from `sentence-transformers`, so this should be a no-op apart from Whisper itself.

`opencv-python-headless` is preferred over `opencv-python` because the backend is headless (no GUI windows). It is reserved for D.3's optional frame-sampling code path; if that path is skipped, OpenCV can be skipped too.

### Whisper model

The first call to `whisper.load_model("base.en")` downloads ~145 MB to `%USERPROFILE%\.cache\whisper\` and caches it. Pre-warm it once so the first ingest run isn't dominated by a download:

```powershell
python -c "import whisper; whisper.load_model('base.en')"
```

| Model | Size | Speed (CPU) | When to use |
|---|---|---|---|
| `tiny.en` | 39 MB | ~10× realtime | Smoke testing only |
| `base.en` | 145 MB | ~5× realtime | **Default** for Phase D |
| `medium.en` | 1.5 GB | ~1× realtime | Switch to this if AutoCAD command names are mis-transcribed in `base.en` output |

`small.en` exists too but offers little improvement over `base.en` for this domain.

## `requirements.txt` updates

Append to `trainerAI_backend/requirements.txt`:

```
openai-whisper>=20231117
opencv-python-headless>=4.10.0
```

Do **not** pin Whisper's version of `torch`; let `sentence-transformers`'s constraint win.

## Verification

- [ ] `ffmpeg -version` prints a version banner.
- [ ] `python -c "import whisper; print(whisper.__version__)"` prints a version.
- [ ] `python -c "import cv2; print(cv2.__version__)"` prints a version.
- [ ] `pip freeze | findstr /I "whisper opencv"` shows both pinned packages.
- [ ] First-time model load completes; subsequent loads are instant from cache.
