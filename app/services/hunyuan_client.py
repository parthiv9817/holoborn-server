"""Hunyuan3D-2mv RunPod serverless client.

Mirrors runpod_client (TRELLIS) but for the Hunyuan endpoint itd7oz9wexb1oo
deployed 2026-05-23. Uses the SAME RUNPOD_API_KEY and the SAME S3 bucket/volume
as TRELLIS — only the /run and /status URLs differ. The S3 download/delete
logic is reused directly from runpod_client (no duplication).

Endpoint input contract (handler.py in parthiv9817/holoborn-hunyuan-gpu):
    {"input": {
        "front_b64": "<base64 PNG>",   # required
        "left_b64":  "<...>",          # optional
        "back_b64":  "<...>",          # optional
        "right_b64": "<...>",          # optional
        # optional tuning params (Hunyuan defaults are the validated optimum):
        "octree_resolution": 512,      # ceiling — higher = polygon bloat, not detail
        "num_inference_steps": 50,     # 60 = marginal bump on 24GB
        "guidance_scale": 5.0,         # mv flow-matching default; do NOT raise
        "num_chunks": 20000,           # memory knob, quality-neutral
        "seed": 12345,
        "skip_enhance": False,
        "skip_preprocess": False
    }}

Output (same shape as TRELLIS, fetchable via the same S3 client):
    {"glb_volume_path": "outputs/<job_id>.glb",
     "glb_size_bytes": int,
     "elapsed_seconds": float}
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx

from app.config import settings
from app.services.runpod_client import RunpodJobError, _runpod_headers


log = logging.getLogger(__name__)


VIEW_KEYS = ("front", "left", "back", "right")


def _build_payload(views: dict[str, bytes], extra: dict[str, Any]) -> dict[str, Any]:
    if "front" not in views or not views["front"]:
        raise ValueError("hunyuan_client: views must include a non-empty 'front' tile")
    payload_input: dict[str, Any] = {}
    for view in VIEW_KEYS:
        if view in views and views[view]:
            payload_input[f"{view}_b64"] = base64.b64encode(views[view]).decode("ascii")
    payload_input.update(extra)
    return {"input": payload_input}


async def submit_job(views: dict[str, bytes], **extra: Any) -> str:
    """Submit a multi-view job to the Hunyuan endpoint → returns RunPod job_id."""
    payload = _build_payload(views, extra)
    async with httpx.AsyncClient(timeout=60.0, headers=_runpod_headers()) as c:
        r = await c.post(settings.hunyuan_run_url, json=payload)
        r.raise_for_status()
        data = r.json()
    job_id = data.get("id")
    if not job_id:
        raise RunpodJobError(f"hunyuan submit: no id in response: {data}")
    log.info("[hunyuan] submitted job=%s views=%s", job_id, list(views.keys()))
    return job_id


async def _get_job_status(runpod_job_id: str) -> dict[str, Any]:
    url = f"{settings.hunyuan_status_url_base}/{runpod_job_id}"
    async with httpx.AsyncClient(timeout=30.0, headers=_runpod_headers()) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.json()


async def poll_until_complete(runpod_job_id: str) -> dict[str, Any]:
    """Poll Hunyuan job until COMPLETED (or FAILED / TIMED_OUT). Returns output dict."""
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
            raise RunpodJobError(f"hunyuan job {runpod_job_id} {state.lower()}: {err}")
        if loop.time() > deadline:
            raise TimeoutError(
                f"hunyuan job {runpod_job_id} did not complete in "
                f"{settings.runpod_poll_timeout_s}s (last state: {state or 'unknown'})"
            )
        await asyncio.sleep(settings.runpod_poll_interval_s)
