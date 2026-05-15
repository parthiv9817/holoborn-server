import asyncio
import logging
import time
import uuid
from datetime import datetime

import cv2
from fastapi import APIRouter, HTTPException, Request

from app.config import AVATARS_DIR, ORIGINALS_DIR, QUEST_TEST_UPLOADS_DIR, SCANS_DIR, settings
from app.models.generation_schemas import (
    FramingResponse,
    MultiviewResponse,
    TaskStatusResponse,
)
from app.services.frame_decoder import decode_jpeg
from app.services.generation_pipeline import process_task
from app.services.multipart_utils import (
    clean_unity_str,
    collect_frames,
    parse_metadata,
)
from app.services.preprocessing import burst_average, pick_sharpest


router = APIRouter()
log = logging.getLogger(__name__)


_PROGRESS_BY_RUNPOD_STATE = {
    "IN_QUEUE": 25,
    "IN_PROGRESS": 60,
    "COMPLETED": 100,
}


@router.post("/validate-frame", response_model=FramingResponse)
async def validate_frame(request: Request) -> FramingResponse:
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="empty body")

    if settings.quest_test_mode:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        out_path = QUEST_TEST_UPLOADS_DIR / f"validate_{ts}.jpg"
        out_path.write_bytes(data)
        log.info("[quest-test] /validate-frame received %d bytes -> %s", len(data), out_path.name)
        return FramingResponse(framing="good", message="quest-test mode: bytes saved", landmarks_detected=33)

    try:
        frame = decode_jpeg(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    pose = request.app.state.pose_validator
    result = pose.validate_framing(frame)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    out_path = ORIGINALS_DIR / f"validate_{ts}_{result['framing']}.jpg"
    cv2.imwrite(str(out_path), frame)

    log.info(
        "validate-frame framing=%s landmarks=%d elapsed=%.1fms",
        result["framing"], result["landmarks_detected"], result["processing_time_ms"],
    )
    return FramingResponse(**result)


@router.post("/generate-multiview", response_model=MultiviewResponse)
async def generate_multiview(request: Request) -> MultiviewResponse:
    form = await request.form()

    body_frames, body_names = await collect_frames(form, prefix="body_")
    face_frames, face_names = await collect_frames(form, prefix="face_")
    legacy_frames, legacy_names = await collect_frames(form)

    # Dual mode requires BOTH bursts. If only one prefix is present (or only
    # legacy frames), we fall back to the single-input path.
    dual_mode = bool(body_frames and face_frames)

    if not dual_mode and not legacy_frames:
        raise HTTPException(
            status_code=400,
            detail="no frame_* / body_* / face_* fields found",
        )

    metadata_raw = form.get("metadata") or ""

    # NOTE: QUEST_TEST_MODE no longer short-circuits this endpoint. It now only
    # affects /validate-frame (skip BlazePose). Real RunPod pipeline runs in
    # both modes. OpenAI bypass is controlled separately via TEST_PORTRAIT_OVERRIDE.

    if isinstance(metadata_raw, str) and metadata_raw:
        try:
            parse_metadata(metadata_raw)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"bad metadata: {e}") from e

    task_id = str(uuid.uuid4())
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    scan_dir = SCANS_DIR / f"{ts}_{task_id[:8]}"
    scan_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(metadata_raw, str) and metadata_raw:
        (scan_dir / "metadata.json").write_text(clean_unity_str(metadata_raw))

    body_jpeg: bytes
    face_jpeg: bytes | None = None
    frames_received: int

    if dual_mode:
        for name, raw in zip(body_names + face_names, body_frames + face_frames):
            (scan_dir / f"{name}.jpg").write_bytes(raw)

        t0 = time.perf_counter()
        body_jpeg, body_idx, body_score = pick_sharpest(body_frames)
        face_jpeg, face_idx, face_score = pick_sharpest(face_frames)
        (scan_dir / "body_sharpest.jpg").write_bytes(body_jpeg)
        (scan_dir / "face_sharpest.jpg").write_bytes(face_jpeg)
        log.info(
            "[task %s] dual-pick elapsed=%.2fs body=idx%d/score%.1f face=idx%d/score%.1f",
            task_id, time.perf_counter() - t0,
            body_idx, body_score, face_idx, face_score,
        )
        frames_received = len(body_frames) + len(face_frames)
    else:
        for name, raw in zip(legacy_names, legacy_frames):
            (scan_dir / f"{name}.jpg").write_bytes(raw)

        t0 = time.perf_counter()
        averaged = burst_average(legacy_frames)
        cv2.imwrite(str(scan_dir / "averaged.jpg"), averaged)
        log.info(
            "[task %s] burst_avg elapsed=%.2fs shape=%s frames=%d",
            task_id, time.perf_counter() - t0, averaged.shape, len(legacy_frames),
        )

        ok, encoded = cv2.imencode(".jpg", averaged, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise HTTPException(status_code=500, detail="failed to encode averaged frame")
        body_jpeg = encoded.tobytes()
        frames_received = len(legacy_frames)

    task_record = {
        "status": "processing",
        "submitted_at": time.time(),
        "scan_dir": str(scan_dir),
        "job_id": None,
        "last_runpod_status": "PENDING",
        "glb_path": None,
        "error": None,
        "mode": "dual" if dual_mode else "single",
    }
    request.app.state.generation_tasks[task_id] = task_record

    asyncio.create_task(
        process_task(task_id, body_jpeg, scan_dir, task_record, face_jpeg=face_jpeg)
    )

    return MultiviewResponse(
        status="processing",
        task_id=task_id,
        frames_received=frames_received,
        message="job accepted",
    )


@router.get("/generate/{task_id}/status", response_model=TaskStatusResponse)
async def task_status(task_id: str, request: Request) -> TaskStatusResponse:
    tasks = request.app.state.generation_tasks
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="unknown task_id")

    # NOTE: QUEST_TEST_MODE used to short-circuit here. Now it only affects
    # /validate-frame; status reflects the real pipeline state regardless.

    glb_url = f"/avatars/{task_id}.glb"
    glb_path = AVATARS_DIR / f"{task_id}.glb"

    status = task.get("status", "processing")

    if status == "complete" and glb_path.exists():
        return TaskStatusResponse(status="complete", progress=100, glb_url=glb_url)

    if status == "failed":
        return TaskStatusResponse(
            status="failed",
            progress=0,
            message=task.get("error") or "task failed",
        )

    if status in ("portraitizing", "retexturing", "rigging", "animating"):
        return TaskStatusResponse(status=status, progress=0, glb_url=glb_url)

    if status == "generating":
        rp_state = (task.get("last_runpod_status") or "PENDING").upper()
        progress = _PROGRESS_BY_RUNPOD_STATE.get(rp_state, 10)
        return TaskStatusResponse(
            status="generating",
            progress=progress,
            glb_url=glb_url,
            message=rp_state.lower(),
        )

    rp_state = (task.get("last_runpod_status") or "PENDING").upper()
    progress = _PROGRESS_BY_RUNPOD_STATE.get(rp_state, 10)
    return TaskStatusResponse(
        status="processing",
        progress=progress,
        glb_url=glb_url,
        message=rp_state.lower(),
    )
