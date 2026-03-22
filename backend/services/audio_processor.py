"""
Audio processing pipeline — FFmpeg-only, single pass.

Optimised for Render free tier (512 MB RAM, CPU-only). All processing
is done with FFmpeg's built-in filters — no Python audio libs needed.

Filter chain (in order):
  highpass      — cut low-frequency rumble below 80 Hz (AC hum, wind, traffic)
  afftdn        — FFT-based spectral noise reduction
  acompressor   — gentle dynamic compression to even out speech volume
  loudnorm      — EBU R128 loudness target (-14 LUFS, social media standard)
"""

import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUTPUT_DIR = Path(".tmp/output")


def process_video(input_path: str, job_id: str) -> str:
    """
    Single-pass FFmpeg pipeline. Returns path to processed video.
    """
    input_path = Path(input_path)
    output_mp4 = OUTPUT_DIR / f"{job_id}_processed.mp4"

    audio_filters = ",".join([
        # 1. Cut low-frequency rumble (AC hum, wind, traffic below 100 Hz)
        "highpass=f=100",

        # 2. First pass — aggressive FFT spectral subtraction
        #    nf=-15 : noise floor (was -20, more aggressive now)
        #    nr=20  : 20 dB reduction (was 12)
        "afftdn=nf=-15:nr=20:nt=w",

        # 3. Second pass — non-local means denoiser (catches residual noise)
        #    s=7 : denoising strength (noticeable but avoids robotic artifacts)
        "anlmdn=s=7:p=0.002",

        # 4. Gentle compression to even out speech volume
        "acompressor=threshold=0.025:ratio=2.5:attack=5:release=100:makeup=2",

        # 5. EBU R128 loudness normalisation — -14 LUFS social media standard
        "loudnorm=I=-14:TP=-1:LRA=11",
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
