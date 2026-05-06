import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.config import QUEST_TEST_UPLOADS_DIR, settings
from app.models.schemas import DetectionResponse
from app.services.frame_decoder import decode_jpeg


router = APIRouter()
log = logging.getLogger(__name__)


async def _read_image(request: Request) -> bytes:
    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(status_code=400, detail="missing 'file' field")
        return await upload.read()
    return await request.body()


@router.post("/detect", response_model=DetectionResponse)
async def detect(request: Request) -> DetectionResponse:
    data = await _read_image(request)
    if not data:
        raise HTTPException(status_code=400, detail="empty body")

    if settings.quest_test_mode:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        out_path = QUEST_TEST_UPLOADS_DIR / f"detect_{ts}.jpg"
        out_path.write_bytes(data)
        log.info("[quest-test] /detect received %d bytes -> %s", len(data), out_path.name)
        state = request.app.state
        state.frames_processed = getattr(state, "frames_processed", 0) + 1
        return DetectionResponse(detected=False, face_count=0, faces=[], frame_number=state.frames_processed, processing_time_ms=0.0)

    try:
        frame = decode_jpeg(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    detector = request.app.state.face_detector
    faces, elapsed_ms = detector.detect_faces(frame)

    state = request.app.state
    state.frames_processed = getattr(state, "frames_processed", 0) + 1

    return DetectionResponse(
        detected=len(faces) > 0,
        face_count=len(faces),
        faces=faces,
        frame_number=state.frames_processed,
        processing_time_ms=elapsed_ms,
    )
