# Workflow: Video Audio Enhancement for Social Media

## Objective
Accept a user-uploaded video, improve its audio quality (noise reduction + loudness normalization), and return a download-ready processed video — all CPU-based with no paid services.

---

## Architecture Overview

```
User Browser
    │
    │  POST /upload (multipart/form-data)
    ▼
FastAPI Backend
    │
    ├── 1. Save raw upload to .tmp/uploads/
    ├── 2. Extract audio (FFmpeg) → .tmp/audio/raw_{id}.wav
    ├── 3. Noise reduction (noisereduce) → .tmp/audio/clean_{id}.wav
    ├── 4. Loudness normalization (FFmpeg loudnorm) → .tmp/audio/norm_{id}.wav
    ├── 5. Mux audio back into video (FFmpeg) → .tmp/output/{id}_processed.mp4
    └── 6. Serve file at GET /download/{id}
```

---

## Required Inputs
- Video file (MP4 or MOV, max 500MB)

## Expected Outputs
- Processed MP4 with enhanced audio (noise removed, normalized to -14 LUFS)

---

## Processing Pipeline

### Step 1 — Extract Audio
```bash
ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 44100 -ac 2 raw_audio.wav
```
- `-vn` strips video stream
- `pcm_s16le` gives uncompressed 16-bit WAV for Python processing
- `-ar 44100` standard sample rate
- `-ac 2` stereo

### Step 2 — Noise Reduction (Python)
```python
import soundfile as sf
import noisereduce as nr

data, rate = sf.read("raw_audio.wav")
# Use first 0.5s as noise profile (assumes ambient noise at start)
noise_sample = data[:int(rate * 0.5)]
reduced = nr.reduce_noise(y=data, sr=rate, y_noise=noise_sample, prop_decrease=0.75)
sf.write("clean_audio.wav", reduced, rate)
```

### Step 3 — Loudness Normalization
Target: -14 LUFS (YouTube/TikTok/Reels standard), true peak -1 dBTP
```bash
ffmpeg -i clean_audio.wav \
  -af "loudnorm=I=-14:TP=-1:LRA=11:print_format=summary" \
  -ar 44100 norm_audio.wav
```

### Step 4 — Mux Back Into Video
```bash
ffmpeg -i original_video.mp4 -i norm_audio.wav \
  -c:v copy \
  -map 0:v:0 \
  -map 1:a:0 \
  -shortest \
  output_video.mp4
```
- `-c:v copy` avoids re-encoding the video (fast, no quality loss)
- `-map` explicitly selects video from original, audio from processed file

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Accept video file, queue processing, return job_id |
| GET | `/status/{job_id}` | Poll processing status |
| GET | `/download/{job_id}` | Stream processed video for download |

---

## Edge Cases & Known Constraints

- **No speech at start of video**: Noise profile estimation may be inaccurate. Solution: use stationary noise reduction mode (`stationary=True`) in noisereduce.
- **File too large (>500MB)**: Reject at upload with 413 error before processing.
- **MOV files**: FFmpeg handles them natively — same pipeline applies.
- **Mono audio**: `-ac 2` in extraction normalizes to stereo. If user prefers mono, remove flag.
- **RAM constraint (1-2GB)**: Large WAV files can spike RAM. For >100MB video, process audio in chunks via librosa streaming or reduce sample rate to 22050.
- **Temp file cleanup**: Delete all `.tmp/` files for a job 1 hour after download, or on server restart.

---

## Performance Optimizations

### Immediate (MVP)
- Copy video stream without re-encoding (`-c:v copy`) — biggest single win
- Lower noise reduction aggressiveness for faster processing (`prop_decrease=0.5`)
- Run FFmpeg with `-threads 0` to use all available CPU cores

### Scale-Up Path
1. **Background workers**: Move processing to Celery + Redis. Upload returns job_id immediately, frontend polls `/status/{job_id}`.
2. **Queue**: Redis or RabbitMQ to serialize jobs on low-RAM servers (process one video at a time).
3. **Storage**: Swap `.tmp/` for S3-compatible storage (Cloudflare R2 is free-tier) when multi-instance is needed.
4. **CDN delivery**: Serve downloads via pre-signed S3 URLs instead of streaming from the app server.

---

## Deployment

### Option A: Render (Free Tier)
1. Push repo to GitHub
2. Create a new **Web Service** on Render, point to `/backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add FFmpeg: Add `apt = ["ffmpeg"]` in `render.yaml` (see deployment config)
6. Free tier spins down after inactivity — use paid ($7/mo) for production

### Option B: VPS (DigitalOcean $6/mo, Hetzner €3.79/mo)
```bash
# On the server
sudo apt update && sudo apt install -y ffmpeg python3-pip
git clone <repo> && cd Sound0/backend
pip install -r requirements.txt
# Run with systemd or screen
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```
Use Nginx as a reverse proxy with a 500MB client_max_body_size.

---

## Tools Used
- `tools/` — No custom tools needed for MVP; all logic lives in `backend/services/audio_processor.py`

## Workflow Version
- Created: 2026-03-22
- Status: Active
