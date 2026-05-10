# D.4 — Video corpus sourcing

**Depends on:** D.2 (FFmpeg + yt-dlp installed)
**Blocks:** D.5 (needs ingested data), D.6
**Estimated effort:** 1–3 h, mostly unattended download time

## Goal

Assemble a 5–8 hour starter corpus of clearly-narrated AutoCAD tutorial videos under `TrainerAi/training_videos/`, prefer-downloading auto-captions where available so D.3's transcriber can short-circuit Whisper.

The bigger principle: **chunk-per-tool granularity beats hour-long deep dives.** A 7-minute focused video on FILLET produces tighter, more-retrievable chunks than a 90-minute "complete AutoCAD course".

## Repository hygiene

Add to `.gitignore` at the repo root:

```
training_videos/
*.mp4
*.wav
*.srt
*.vtt
```

The current `.gitignore` only excludes `.env` files — without this, a developer running ingestion can easily commit several gigabytes of video data.

Create the folder:

```powershell
mkdir D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\training_videos
```

## Recommended starter corpus

Aim for **one video per core AutoCAD command**, plus 1–2 longer "intro" videos for general workflow context. Total target: 5–8 h.

### Channels worth scraping

| Channel | Why | Typical length |
|---|---|---|
| **Autodesk official** ([@autodesk](https://www.youtube.com/@autodesk)) | Authoritative; clean narration; auto-captions are accurate | 5–15 min |
| **CAD Intentions** | Per-command focus; clear English; native captions | 10–20 min |
| **The CAD Setter Out** | Workflow-oriented; UK English; reliable captions | 5–15 min |
| **Brooke Godfrey** | Beginner-friendly; transcriptions of UI steps | 10–30 min |

### What to avoid

- Silent screen-recordings with only on-screen text (Whisper has nothing to transcribe).
- Music montages or sped-up time-lapses.
- Non-English audio. The current model is `base.en`; the chunker's tool detection regex matches English command names; the eval set in D.5 is English-only.
- 90+ min "ultimate course" videos — they produce many high-overlap chunks and dilute the eval signal.

### Minimum coverage checklist

The starter set should hit each of these AutoCAD topics with at least one dedicated video:

- LINE / drawing primitives
- CIRCLE / ARC
- RECTANGLE / POLYGON
- TRIM / EXTEND
- OFFSET / MIRROR
- FILLET / CHAMFER
- HATCH
- LAYER management
- BLOCK / INSERT
- DIMENSION
- One general intro to the AutoCAD workspace (ribbon, command line, UCS)

That is 11 topics; with 7–15 min videos each, the corpus lands around 2–3 hours — supplement with one longer general workflow video.

## Download workflow with `yt-dlp`

Single command per video — pulls the video, the best English subtitle track (auto or manual), and converts subs to SRT format that D.3's transcriber can consume directly:

```powershell
cd D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\training_videos

yt-dlp `
  --write-auto-subs `
  --write-subs `
  --sub-lang en `
  --convert-subs srt `
  --output "%(uploader)s - %(title)s [%(id)s].%(ext)s" `
  --restrict-filenames `
  --format "bestvideo[height<=720]+bestaudio/best[height<=720]" `
  "<youtube-url>"
```

The `--restrict-filenames` flag avoids spaces and special characters that break the FFmpeg/Whisper command pipeline downstream.

Quality cap of 720p is intentional — D.3 doesn't need pixel-level detail (no frame OCR until Phase G), and lower-resolution downloads save 60–80% of disk space.

### Batch download

Put a list of URLs in `training_videos/urls.txt` (one URL per line, blank lines and `#` comments allowed) and run:

```powershell
yt-dlp `
  --write-auto-subs --write-subs --sub-lang en --convert-subs srt `
  --output "%(uploader)s - %(title)s [%(id)s].%(ext)s" `
  --restrict-filenames `
  --format "bestvideo[height<=720]+bestaudio/best[height<=720]" `
  --batch-file urls.txt
```

Commit `urls.txt` so the corpus is reproducible across dev machines (the videos themselves are not committed; the URL list is).

## Layout after download

```
TrainerAi/
└── training_videos/
    ├── urls.txt
    ├── Autodesk_AutoCAD_-_LINE_command_basics_[abc123].mp4
    ├── Autodesk_AutoCAD_-_LINE_command_basics_[abc123].en.srt
    ├── CAD_Intentions_-_FILLET_explained_[def456].mp4
    ├── CAD_Intentions_-_FILLET_explained_[def456].en.srt
    └── ...
```

## Ingest the whole corpus

Once D.3 is implemented:

```powershell
cd D:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
.venv\Scripts\Activate.ps1

python -m app.training.ingest --videos-dir ..\training_videos --whisper-model base.en
```

Expected order-of-magnitude timing on a mid-range CPU laptop:

- ~2 min per video for FFmpeg audio extraction + Whisper `base.en` transcription (instant if `.srt` short-circuit fires).
- ~5 s for chunking + batched embedding of one video's chunks.
- ~50–200 inserted rows per video.

Total runtime for an 8-hour corpus: **30–90 min** depending on how many videos provide subtitles.

## Acceptance

- [ ] `training_videos/urls.txt` exists and is committed.
- [ ] `training_videos/` is in the repo `.gitignore` for media files.
- [ ] At least 10 distinct `.mp4` files cover the minimum-coverage topic list above.
- [ ] At least 60% of the videos have a sibling `.en.srt` (verifies the SRT short-circuit will exercise).
- [ ] `yt-dlp --batch-file urls.txt` completes with no errors on a fresh checkout.
