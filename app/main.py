import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import AVATARS_DIR
from app.routes import detection, health
from app.services.face_detector import FaceDetector
from app.services.pose_validator import PoseValidator


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = time.time()
    app.state.frames_processed = 0
    app.state.face_detector = FaceDetector()
    app.state.pose_validator = PoseValidator()
    app.state.generation_tasks = {}
    print("[startup] face_detector + pose_validator loaded")
    try:
        yield
    finally:
        app.state.face_detector.close()
        app.state.pose_validator.close()
        runpod = getattr(app.state, "runpod_client", None)
        if runpod is not None:
            await runpod.aclose()
        print("[shutdown] resources released")


app = FastAPI(title="HoloBorn Mac Backend", lifespan=lifespan)

app.include_router(health.router)
app.include_router(detection.router)

app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR)), name="avatars")
