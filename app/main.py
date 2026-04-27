import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import AVATARS_DIR, settings
from app.routes import detection, generation, health
from app.services.face_detector import FaceDetector
from app.services.pose_validator import PoseValidator
from app.services.runpod_client import get_s3_client


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("holoborn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = time.time()
    app.state.frames_processed = 0
    app.state.face_detector = FaceDetector()
    app.state.pose_validator = PoseValidator()
    app.state.generation_tasks = {}
    log.info("face_detector + pose_validator loaded")

    s3 = get_s3_client()
    s3.head_bucket(Bucket=settings.runpod_s3_bucket)
    log.info(
        "RunPod S3 ready: bucket=%s endpoint=%s",
        settings.runpod_s3_bucket, settings.runpod_s3_endpoint,
    )

    try:
        yield
    finally:
        app.state.face_detector.close()
        app.state.pose_validator.close()
        log.info("shutdown: resources released")


app = FastAPI(title="HoloBorn Mac Backend", lifespan=lifespan)

app.include_router(health.router)
app.include_router(detection.router)
app.include_router(generation.router)

app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR)), name="avatars")
