import asyncio
import base64
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2

from app.config import SCANS_DIR
from app.services.multipart_utils import clean_unity_str
from app.services.portraitizer import portraitize
from app.services.preprocessing import burst_average
from app.services.runpod_client import RunPodClient


async def run_pipeline(
    frames: list[bytes],
    frame_names: list[str],
    metadata_raw: str,
    runpod: RunPodClient,
) -> tuple[str, str, dict]:
    task_id = str(uuid.uuid4())
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    scan_dir = SCANS_DIR / f"{ts}_{task_id[:8]}"
    scan_dir.mkdir(parents=True, exist_ok=True)

    for name, raw in zip(frame_names, frames):
        (scan_dir / f"{name}.jpg").write_bytes(raw)
    if metadata_raw:
        (scan_dir / "metadata.json").write_text(clean_unity_str(metadata_raw))

    print(f"[pipeline] task={task_id} frames={len(frames)} dir={scan_dir.name}")

    t0 = time.perf_counter()
    averaged = burst_average(frames)
    cv2.imwrite(str(scan_dir / "averaged.jpg"), averaged)
    print(f"[pipeline] burst_avg elapsed={time.perf_counter() - t0:.2f}s shape={averaged.shape}")

    ok, encoded = cv2.imencode(".jpg", averaged, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise RuntimeError("failed to encode averaged frame")
    averaged_jpeg = encoded.tobytes()

    t1 = time.perf_counter()
    portrait_bytes = await asyncio.to_thread(portraitize, averaged_jpeg)
    print(f"[pipeline] portraitize elapsed={time.perf_counter() - t1:.2f}s bytes={len(portrait_bytes)}")
    (scan_dir / "portrait.png").write_bytes(portrait_bytes)

    image_b64 = base64.b64encode(portrait_bytes).decode("ascii")

    t2 = time.perf_counter()
    job_id = await runpod.submit_job(image_b64)
    print(f"[pipeline] runpod submitted job={job_id} elapsed={time.perf_counter() - t2:.2f}s")

    task_record = {
        "job_id": job_id,
        "scan_dir": str(scan_dir),
        "submitted_at": time.time(),
        "status": "processing",
        "glb_path": None,
        "last_runpod_status": "IN_QUEUE",
    }
    return task_id, job_id, task_record
