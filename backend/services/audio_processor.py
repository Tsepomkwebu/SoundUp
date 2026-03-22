"""
Audio processing pipeline — FFmpeg-only, single pass.

Uses FFmpeg's built-in filters instead of loading audio into Python memory,
making this safe to run on low-RAM servers (512 MB Render free tier).

  afftdn  — FFT-based noise reduction (no Python memory spike)
  loudnorm — EBU R128 loudness normalization to -14 LUFS
  -c:v copy — video stream copied without re-encoding (fast, lossless)
"""

import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUTPUT_DIR = Path(".tmp/output")


def process_video(input_path: str, job_id: str) -> str:
    """
    Single-pass FFmpeg pipeline:
      1. Apply FFT noise reduction (afftdn)
      2. Normalize loudness to -14 LUFS / -1 dBTP (loudnorm)
      3. Copy video stream as-is, replace audio track

    Returns the path to the processed output video.
    """
    input_path = Path(input_path)
    output_mp4 = OUTPUT_DIR / f"{job_id}_processed.mp4"

    audio_filters = ",".join([
        "afftdn=nf=-25",                          # noise floor -25 dB
        "loudnorm=I=-14:TP=-1:LRA=11",            # -14 LUFS, social media standard
    ])

    cmd = [
        FFMPEG, "-y",
        "-i", str(input_path),
        "-af", audio_filters,
        "-c:v", "copy",       # don't re-encode video
        str(output_mp4),
    ]

    _run(cmd)
    return str(output_mp4)


def _run(cmd: list[str]):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{result.stderr[-3000:]}")
