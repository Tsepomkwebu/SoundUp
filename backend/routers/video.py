import uuid
import shutil
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from services.audio_processor import process_video

router = APIRouter()

# In-memory job store. Replace with Redis for multi-worker deployments.
jobs: dict[str, dict] = {}

ALLOWED_EXTENSIONS = {".mp4", ".mov"}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

UPLOAD_DIR = Path(".tmp/uploads")
OUTPUT_DIR = Path(".tmp/output")


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Upload MP4 or MOV.",
        )

    # Stream directly to disk — never load the full file into RAM
    job_id = str(uuid.uuid4())
    input_path = UPLOAD_DIR / f"{job_id}{ext}"
    bytes_written = 0
    with open(input_path, "wb") as out:
        for chunk in file.file:
            bytes_written += len(chunk)
            if bytes_written > MAX_FILE_SIZE_BYTES:
                input_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File exceeds 500 MB limit.")
            out.write(chunk)

    # Register job
    jobs[job_id] = {"status": "queued", "error": None}

    # Kick off background processing
    background_tasks.add_task(_run_processing, job_id, str(input_path))

    return {"job_id": job_id, "status": "queued"}


async def _run_processing(job_id: str, input_path: str):
    """Runs the CPU-bound processing in a thread pool to avoid blocking the event loop."""
    jobs[job_id]["status"] = "processing"
    loop = asyncio.get_event_loop()
    try:
        output_path = await loop.run_in_executor(
            None,
            process_video,
            input_path,
            job_id,
        )
        jobs[job_id]["status"] = "done"
        jobs[job_id]["output_path"] = output_path
    except Exception as exc:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(exc)


@router.get("/status/{job_id}")
def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job_id": job_id, "status": job["status"], "error": job.get("error")}


@router.get("/download/{job_id}")
def download_video(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Video not ready yet. Current status: {job['status']}",
        )

    output_path = job.get("output_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=500, detail="Output file missing.")

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=f"enhanced_{job_id}.mp4",
    )
