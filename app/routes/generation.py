import asyncio
import base64
import time
import uuid
from datetime import datetime

import cv2
from fastapi import APIRouter, HTTPException, Request

from app.config import ORIGINALS_DIR, SCANS_DIR
from app.models.generation_schemas import FramingResponse, MultiviewResponse
from app.services.frame_decoder import decode_jpeg
from app.services.multipart_utils import (
    clean_unity_str,
    collect_frames,
    parse_metadata,
)
from app.services.portraitizer import portraitize
from app.services.preprocessing import burst_average
from app.services.runpod_client import RunPodClient


router = APIRouter()


def _get_runpod_client(request: Request) -> RunPodClient:
    state = request.app.state
    client = getattr(state, "runpod_client", None)
    if client is None:
        client = RunPodClient()
        state.runpod_client = client
    return client


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


@router.post("/generate-multiview", response_model=MultiviewResponse)
async def generate_multiview(request: Request) -> MultiviewResponse:
    form = await request.form()
    frames, names = await collect_frames(form)
    if not frames:
        raise HTTPException(status_code=400, detail="no frame_* fields found")

    metadata_raw = form.get("metadata")
    metadata: list[dict] = []
    if isinstance(metadata_raw, str) and metadata_raw:
        try:
            metadata = parse_metadata(metadata_raw)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"bad metadata: {e}") from e

    task_id = str(uuid.uuid4())
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    scan_dir = SCANS_DIR / f"{ts}_{task_id[:8]}"
    scan_dir.mkdir(parents=True, exist_ok=True)

    for name, raw in zip(names, frames):
        (scan_dir / f"{name}.jpg").write_bytes(raw)
    if metadata:
        (scan_dir / "metadata.json").write_text(clean_unity_str(metadata_raw or ""))

    print(f"[generate-multiview] task={task_id} frames={len(frames)} dir={scan_dir.name}")

    t0 = time.perf_counter()
    averaged = burst_average(frames)
    avg_path = scan_dir / "averaged.jpg"
    cv2.imwrite(str(avg_path), averaged)
    t_avg = time.perf_counter() - t0
    print(f"[generate-multiview] burst_avg elapsed={t_avg:.2f}s shape={averaged.shape}")

    ok, encoded = cv2.imencode(".jpg", averaged, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode averaged frame")
    averaged_jpeg = encoded.tobytes()

    t1 = time.perf_counter()
    try:
        portrait_bytes = await asyncio.to_thread(portraitize, averaged_jpeg)
    except Exception as e:
        print(f"[generate-multiview] portraitize failed: {e}")
        raise HTTPException(status_code=502, detail=f"portraitize failed: {e}") from e
    t_portrait = time.perf_counter() - t1
    print(f"[generate-multiview] portraitize elapsed={t_portrait:.2f}s bytes={len(portrait_bytes)}")

    portrait_path = scan_dir / "portrait.png"
    portrait_path.write_bytes(portrait_bytes)

    image_b64 = base64.b64encode(portrait_bytes).decode("ascii")

    runpod = _get_runpod_client(request)
    t2 = time.perf_counter()
    try:
        job_id = await runpod.submit_job(image_b64)
    except Exception as e:
        print(f"[generate-multiview] runpod submit failed: {e}")
        raise HTTPException(status_code=502, detail=f"runpod submit failed: {e}") from e
    t_submit = time.perf_counter() - t2
    print(f"[generate-multiview] runpod submitted job={job_id} elapsed={t_submit:.2f}s")

    request.app.state.generation_tasks[task_id] = {
        "job_id": job_id,
        "scan_dir": str(scan_dir),
        "submitted_at": time.time(),
        "status": "processing",
        "glb_path": None,
        "last_runpod_status": "IN_QUEUE",
    }

    return MultiviewResponse(
        status="processing",
        task_id=task_id,
        frames_received=len(frames),
        message="job submitted to runpod",
    )
