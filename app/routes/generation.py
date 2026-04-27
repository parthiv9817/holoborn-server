from datetime import datetime

import cv2
from fastapi import APIRouter, HTTPException, Request

from app.config import AVATARS_DIR, ORIGINALS_DIR
from app.models.generation_schemas import (
    FramingResponse,
    MultiviewResponse,
    TaskStatusResponse,
)
from app.services.frame_decoder import decode_jpeg
from app.services.generation_pipeline import run_pipeline
from app.services.multipart_utils import collect_frames, parse_metadata
from app.services.runpod_client import RunPodClient


router = APIRouter()


def _get_runpod_client(request: Request) -> RunPodClient:
    state = request.app.state
    client = getattr(state, "runpod_client", None)
    if client is None:
        client = RunPodClient()
        state.runpod_client = client
    return client


def _progress_for(runpod_status: str) -> int:
    return {
        "IN_QUEUE": 10,
        "IN_PROGRESS": 50,
        "COMPLETED": 100,
        "FAILED": 0,
        "CANCELLED": 0,
        "TIMED_OUT": 0,
    }.get(runpod_status.upper(), 25)


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
        f"elapsed={result['processing_time_ms']:.1f}ms"
    )

    return FramingResponse(**result)


@router.post("/generate-multiview", response_model=MultiviewResponse)
async def generate_multiview(request: Request) -> MultiviewResponse:
    form = await request.form()
    frames, names = await collect_frames(form)
    if not frames:
        raise HTTPException(status_code=400, detail="no frame_* fields found")

    metadata_raw = form.get("metadata") or ""
    if isinstance(metadata_raw, str) and metadata_raw:
        try:
            parse_metadata(metadata_raw)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"bad metadata: {e}") from e

    runpod = _get_runpod_client(request)
    try:
        task_id, _job_id, task_record = await run_pipeline(
            frames, names, metadata_raw if isinstance(metadata_raw, str) else "", runpod
        )
    except Exception as e:
        print(f"[generate-multiview] pipeline failed: {e}")
        raise HTTPException(status_code=502, detail=f"pipeline failed: {e}") from e

    request.app.state.generation_tasks[task_id] = task_record
    return MultiviewResponse(
        status="processing",
        task_id=task_id,
        frames_received=len(frames),
        message="job submitted to runpod",
    )


@router.get("/generate/{task_id}/status", response_model=TaskStatusResponse)
async def task_status(task_id: str, request: Request) -> TaskStatusResponse:
    tasks = request.app.state.generation_tasks
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="unknown task_id")

    glb_url = f"/avatars/{task_id}.glb"
    glb_path = AVATARS_DIR / f"{task_id}.glb"

    if task.get("status") == "complete" and glb_path.exists():
        return TaskStatusResponse(status="complete", progress=100, glb_url=glb_url)

    if task.get("status") == "failed":
        return TaskStatusResponse(
            status="failed",
            progress=0,
            message=task.get("error", "runpod job failed"),
        )

    runpod = _get_runpod_client(request)
    job_id = task["job_id"]
    try:
        rp_status = await runpod.get_job_status(job_id)
    except Exception as e:
        print(f"[status] runpod poll error task={task_id}: {e}")
        return TaskStatusResponse(
            status="processing",
            progress=_progress_for(task.get("last_runpod_status", "IN_QUEUE")),
            glb_url=glb_url,
            message=f"poll error: {e}",
        )

    state = (rp_status.get("status") or "IN_QUEUE").upper()
    task["last_runpod_status"] = state

    if state == "COMPLETED":
        output = rp_status.get("output") or {}
        try:
            saved = await runpod.download_glb(output, task_id)
        except Exception as e:
            task["status"] = "failed"
            task["error"] = f"glb download failed: {e}"
            print(f"[status] glb download failed task={task_id}: {e}")
            return TaskStatusResponse(status="failed", progress=0, message=task["error"])

        task["status"] = "complete"
        task["glb_path"] = str(saved)
        print(f"[status] task={task_id} complete -> {saved.name} ({saved.stat().st_size} bytes)")
        return TaskStatusResponse(status="complete", progress=100, glb_url=glb_url)

    if state in {"FAILED", "CANCELLED", "TIMED_OUT"}:
        task["status"] = "failed"
        task["error"] = rp_status.get("error") or state.lower()
        return TaskStatusResponse(status="failed", progress=0, message=task["error"])

    return TaskStatusResponse(
        status="processing",
        progress=_progress_for(state),
        glb_url=glb_url,
        message=state.lower(),
    )
