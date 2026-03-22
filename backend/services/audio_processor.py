"""
Audio processing pipeline:
  1. Extract raw WAV audio from the video (FFmpeg)
  2. Apply noise reduction (noisereduce)
  3. Normalize loudness to -14 LUFS / -1 dBTP (FFmpeg loudnorm)
  4. Mux the cleaned audio back into the original video (FFmpeg, no video re-encode)
"""

import os
import subprocess
from pathlib import Path

import soundfile as sf
import noisereduce as nr

AUDIO_DIR = Path(".tmp/audio")
OUTPUT_DIR = Path(".tmp/output")

# Loudness targets aligned with TikTok / Instagram Reels / YouTube Shorts
LUFS_TARGET = -14
TRUE_PEAK_TARGET = -1
LRA_TARGET = 11


def process_video(input_path: str, job_id: str) -> str:
    """
    Full pipeline. Returns the path to the processed output video.
    Raises on any FFmpeg or processing error.
    """
    input_path = Path(input_path)

    raw_wav = AUDIO_DIR / f"raw_{job_id}.wav"
    clean_wav = AUDIO_DIR / f"clean_{job_id}.wav"
    norm_wav = AUDIO_DIR / f"norm_{job_id}.wav"
    output_mp4 = OUTPUT_DIR / f"{job_id}_processed.mp4"

    try:
        _extract_audio(input_path, raw_wav)
        _reduce_noise(raw_wav, clean_wav)
        _normalize_loudness(clean_wav, norm_wav)
        _mux_audio(input_path, norm_wav, output_mp4)
    finally:
        # Always clean up intermediate audio files, keep output
        for f in [raw_wav, clean_wav, norm_wav]:
            if f.exists():
                f.unlink()

    return str(output_mp4)


# ---------------------------------------------------------------------------
# Step 1 — Extract audio
# ---------------------------------------------------------------------------

def _extract_audio(video_path: Path, out_wav: Path):
    """Extract stereo 44.1 kHz 16-bit PCM WAV from the video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                   # drop video stream
        "-acodec", "pcm_s16le",  # uncompressed PCM for Python processing
        "-ar", "44100",
        "-ac", "2",              # stereo
        str(out_wav),
    ]
    _run(cmd, "audio extraction")


# ---------------------------------------------------------------------------
# Step 2 — Noise reduction
# ---------------------------------------------------------------------------

def _reduce_noise(in_wav: Path, out_wav: Path):
    """
    Estimate noise from the first 0.5 s of the file (ambient / room noise),
    then subtract it across the entire signal.

    prop_decrease=0.75 keeps speech natural while reducing background noise.
    stationary=True works better when there's no clear silent section at the start.
    """
    data, rate = sf.read(str(in_wav))

    # Build noise profile from first half-second
    noise_sample_len = int(rate * 0.5)
    noise_sample = data[:noise_sample_len]

    reduced = nr.reduce_noise(
        y=data,
        sr=rate,
        y_noise=noise_sample,
        prop_decrease=0.75,
        stationary=False,   # adaptive; handles varying background noise
        n_jobs=-1,           # use all CPU cores
    )

    sf.write(str(out_wav), reduced, rate, subtype="PCM_16")


# ---------------------------------------------------------------------------
# Step 3 — Loudness normalization (EBU R128)
# ---------------------------------------------------------------------------

def _normalize_loudness(in_wav: Path, out_wav: Path):
    """
    Two-pass loudnorm filter via FFmpeg.
    Targets -14 LUFS integrated, -1 dBTP true peak, 11 LU range.
    These values match YouTube, TikTok, and Instagram Reels standards.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(in_wav),
        "-af", (
            f"loudnorm="
            f"I={LUFS_TARGET}:"
            f"TP={TRUE_PEAK_TARGET}:"
            f"LRA={LRA_TARGET}:"
            f"print_format=summary"
        ),
        "-ar", "44100",
        str(out_wav),
    ]
    _run(cmd, "loudness normalization")


# ---------------------------------------------------------------------------
# Step 4 — Mux audio back into video
# ---------------------------------------------------------------------------

def _mux_audio(video_path: Path, audio_path: Path, output_path: Path):
    """
    Replace the audio track in the original video with the processed audio.
    Video stream is copied as-is (no re-encode) for speed and quality preservation.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),   # original video (video + old audio)
        "-i", str(audio_path),   # processed audio
        "-c:v", "copy",          # copy video stream without re-encoding
        "-map", "0:v:0",         # video from first input
        "-map", "1:a:0",         # audio from second input
        "-shortest",             # trim to shortest stream (handles rounding drift)
        str(output_path),
    ]
    _run(cmd, "audio mux")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(cmd: list[str], step: str):
    """Run a subprocess command; raise RuntimeError with FFmpeg stderr on failure."""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed at step '{step}':\n{result.stderr[-2000:]}"
        )
