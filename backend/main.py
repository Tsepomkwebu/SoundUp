import os
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.video import router as video_router

# Ensure temp directories exist on startup
TEMP_DIRS = [".tmp/uploads", ".tmp/audio", ".tmp/output"]


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
    allow_origins=["*"],  # Tighten in production to your frontend domain
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
