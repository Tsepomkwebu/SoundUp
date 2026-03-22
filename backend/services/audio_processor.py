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
        # 1. Cut low-frequency rumble (air con, traffic, wind below 80 Hz)
        "highpass=f=80",

        # 2. FFT noise reduction
        #    nf=-20  : noise floor estimate (dB) — lower = more aggressive
        #    nr=12   : amount of noise reduction (dB) — higher = more reduction
        #    nt=w    : assume broadband/white noise profile (best for room noise)
        "afftdn=nf=-20:nr=12:nt=w",

        # 3. Gentle compression to even out volume differences between
        #    quiet and loud speech, without sounding over-compressed
        #    threshold=-18dB, ratio 2.5:1, fast attack, medium release
        "acompressor=threshold=0.025:ratio=2.5:attack=5:release=100:makeup=2",

        # 4. EBU R128 loudness normalisation to -14 LUFS
        #    Matches YouTube, TikTok, and Instagram Reels targets
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
