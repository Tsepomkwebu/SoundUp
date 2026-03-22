import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routers.video import router as video_router

TEMP_DIRS = [".tmp/uploads", ".tmp/audio", ".tmp/output"]
FRONTEND_INDEX = Path(__file__).parent.parent / "frontend" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    for d in TEMP_DIRS:
        os.makedirs(d, exist_ok=True)
    yield


app = FastAPI(
    title="SoundUp API",
    description="Audio enhancement for social media videos",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_INDEX))
