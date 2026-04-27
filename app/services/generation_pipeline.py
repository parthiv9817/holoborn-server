import asyncio
import base64
import logging
import time
from pathlib import Path

import cv2

from app.config import AVATARS_DIR
from app.services.portraitizer import portraitize
from app.services.runpod_client import (
    GlbDownloadError,
    RunpodJobError,
    delete_remote_glb,
    download_glb,
    poll_until_complete,
    submit_job,
)


log = logging.getLogger(__name__)


async def _portraitize_async(jpeg_bytes: bytes) -> bytes:
    return await asyncio.to_thread(portraitize, jpeg_bytes)


async def process_task(
    task_id: str,
    averaged_jpeg: bytes,
    scan_dir: Path,
    task_record: dict,
) -> None:
    """Background pipeline: portraitize -> runpod submit -> poll -> download -> delete.

    Mutates task_record in place to communicate progress/status to /status route.
    """
    try:
        t1 = time.perf_counter()
        portrait_bytes = await _portraitize_async(averaged_jpeg)
        log.info(
            "[task %s] portraitize elapsed=%.2fs bytes=%d",
            task_id, time.perf_counter() - t1, len(portrait_bytes),
        )
        (scan_dir / "portrait.png").write_bytes(portrait_bytes)
        task_record["portrait_path"] = str(scan_dir / "portrait.png")

        image_b64 = base64.b64encode(portrait_bytes).decode("ascii")

        t2 = time.perf_counter()
        runpod_job_id = await submit_job(image_b64)
        task_record["job_id"] = runpod_job_id
        task_record["last_runpod_status"] = "IN_QUEUE"
        log.info(
            "[task %s] submitted job=%s elapsed=%.2fs",
            task_id, runpod_job_id, time.perf_counter() - t2,
        )

        t3 = time.perf_counter()
        output = await poll_until_complete(runpod_job_id)
        task_record["last_runpod_status"] = "COMPLETED"
        log.info(
            "[task %s] runpod completed elapsed=%.2fs output_keys=%s",
            task_id, time.perf_counter() - t3, list(output.keys()),
        )

        glb_volume_path = output.get("glb_volume_path")
        if not glb_volume_path:
            raise RunpodJobError(
                f"runpod output missing glb_volume_path: keys={list(output.keys())}"
            )

        local_path = AVATARS_DIR / f"{task_id}.glb"
        t4 = time.perf_counter()
        size = await download_glb(glb_volume_path, local_path)
        log.info(
            "[task %s] glb downloaded -> %s (%d bytes, %.2fs)",
            task_id, local_path.name, size, time.perf_counter() - t4,
        )

        await delete_remote_glb(glb_volume_path)

        task_record["status"] = "complete"
        task_record["glb_path"] = str(local_path)
        task_record["glb_size_bytes"] = size

    except (RunpodJobError, GlbDownloadError, TimeoutError) as e:
        log.exception("[task %s] failed: %s", task_id, e)
        task_record["status"] = "failed"
        task_record["error"] = str(e)
    except Exception as e:
        log.exception("[task %s] unexpected error: %s", task_id, e)
        task_record["status"] = "failed"
        task_record["error"] = f"{type(e).__name__}: {e}"
