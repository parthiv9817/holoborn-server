import time
from datetime import datetime

import cv2
from fastapi import APIRouter, HTTPException, Request

from app.config import ORIGINALS_DIR
from app.models.generation_schemas import FramingResponse
from app.services.frame_decoder import decode_jpeg


router = APIRouter()


@router.post("/validate-frame", response_model=FramingResponse)
async def validate_frame(request: Request) -> FramingResponse:
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="empty body")

    try:
        frame = decode_jpeg(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    pose = request.app.state.pose_validator
    result = pose.validate_framing(frame)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    out_path = ORIGINALS_DIR / f"validate_{ts}_{result['framing']}.jpg"
    cv2.imwrite(str(out_path), frame)

    print(
        f"[validate-frame] framing={result['framing']} "
        f"landmarks={result['landmarks_detected']} "
        f"elapsed={result['processing_time_ms']:.1f}ms saved={out_path.name}"
    )

    return FramingResponse(**result)
