import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
import httpx
from botocore.client import Config

from app.config import settings


log = logging.getLogger(__name__)


class RunpodJobError(RuntimeError):
    pass


class GlbDownloadError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_s3_client():
    if not settings.runpod_s3_access_key or not settings.runpod_s3_secret_key:
        raise RuntimeError(
            "RunPod S3 credentials missing — set RUNPOD_S3_ACCESS_KEY / RUNPOD_S3_SECRET_KEY"
        )
    if not settings.runpod_s3_endpoint or not settings.runpod_s3_bucket:
        raise RuntimeError(
            "RUNPOD_S3_ENDPOINT and RUNPOD_S3_BUCKET must be set"
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.runpod_s3_endpoint,
        aws_access_key_id=settings.runpod_s3_access_key,
        aws_secret_access_key=settings.runpod_s3_secret_key,
        region_name=settings.runpod_s3_region or None,
        config=Config(signature_version="s3v4"),
    )


def _runpod_headers() -> dict[str, str]:
    if not settings.runpod_api_key or settings.runpod_api_key in {"", "replace-me"}:
        raise RuntimeError("RUNPOD_API_KEY is not set in .env")
    return {
        "Authorization": f"Bearer {settings.runpod_api_key}",
        "Content-Type": "application/json",
    }


async def submit_job(image_b64: str, **extra: Any) -> str:
    payload = {"input": {"image_b64": image_b64, **extra}}
    async with httpx.AsyncClient(timeout=60.0, headers=_runpod_headers()) as c:
        r = await c.post(settings.runpod_run_url, json=payload)
        r.raise_for_status()
        data = r.json()
    job_id = data.get("id")
    if not job_id:
        raise RunpodJobError(f"runpod submit: no id in response: {data}")
    return job_id


async def _get_job_status(runpod_job_id: str) -> dict[str, Any]:
    url = f"{settings.runpod_status_url_base}/{runpod_job_id}"
    async with httpx.AsyncClient(timeout=30.0, headers=_runpod_headers()) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.json()


async def poll_until_complete(runpod_job_id: str) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + settings.runpod_poll_timeout_s
    while True:
        status = await _get_job_status(runpod_job_id)
        state = (status.get("status") or "").upper()
        if state == "COMPLETED":
            return status.get("output") or {}
        if state in {"FAILED", "CANCELLED", "TIMED_OUT"}:
            err = (
                status.get("error")
                or (status.get("output") or {}).get("error")
                or state.lower()
            )
            raise RunpodJobError(f"runpod job {runpod_job_id} {state.lower()}: {err}")
        if loop.time() > deadline:
            raise TimeoutError(
                f"runpod job {runpod_job_id} did not complete in "
                f"{settings.runpod_poll_timeout_s}s (last state: {state or 'unknown'})"
            )
        await asyncio.sleep(settings.runpod_poll_interval_s)


def _download_sync(bucket: str, key: str, local_path: Path) -> int:
    s3 = get_s3_client()
    s3.download_file(bucket, key, str(local_path))
    return local_path.stat().st_size


async def download_glb(glb_volume_path: str, local_path: Path) -> int:
    bucket = settings.runpod_s3_bucket
    local_path.parent.mkdir(parents=True, exist_ok=True)
    size = await asyncio.to_thread(_download_sync, bucket, glb_volume_path, local_path)
    with local_path.open("rb") as f:
        magic = f.read(4)
    if magic != b"glTF":
        try:
            local_path.unlink()
        except OSError:
            pass
        raise GlbDownloadError(
            f"downloaded GLB has invalid magic bytes: {magic!r} (expected b'glTF')"
        )
    return size


def _delete_sync(bucket: str, key: str) -> None:
    s3 = get_s3_client()
    s3.delete_object(Bucket=bucket, Key=key)


async def delete_remote_glb(glb_volume_path: str) -> None:
    if settings.runpod_s3_keep_after_download:
        log.info(
            "RUNPOD_S3_KEEP_AFTER_DOWNLOAD=true, skipping remote delete: %s",
            glb_volume_path,
        )
        return
    try:
        await asyncio.to_thread(
            _delete_sync, settings.runpod_s3_bucket, glb_volume_path
        )
    except Exception as e:
        log.warning("delete_remote_glb failed for %s: %s", glb_volume_path, e)
