"""
Extracts the audio track from an MP4 file using FFmpeg.
Returns the path to the extracted .wav file.
"""
from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path


def extract_audio(video_path: str | Path) -> Path:
    """
    Extract audio from video file to a temporary WAV file.
    Returns the path to the WAV file. Caller is responsible for cleanup.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav_path = Path(tmp.name)
    tmp.close()

    t0 = time.perf_counter()
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",                    # no video
            "-acodec", "pcm_s16le",   # WAV PCM
            "-ar", "16000",           # 16kHz — Whisper requirement
            "-ac", "1",               # mono
            str(wav_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")

    elapsed = time.perf_counter() - t0
    print(f"      Audio extraction took {elapsed:.1f}s")
    return wav_path
