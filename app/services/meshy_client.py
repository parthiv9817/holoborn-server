"""Meshy Retexture API client."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import settings


log = logging.getLogger(__name__)


DUMMY_KEY = "msy_dummy_api_key_for_test_mode_12345678"
GLB_MAGIC = b"glTF"


class MeshyJobError(RuntimeError):
    pass


class MeshyDownloadError(RuntimeError):
    pass


def _resolve_key() -> str:
    key = (settings.meshy_api_key or "").strip()
    if not key:
        return DUMMY_KEY
    return key


def is_dummy_mode() -> bool:
    """True when no real MESHY_API_KEY is set — mock responses only."""
    return _resolve_key() == DUMMY_KEY


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_resolve_key()}",
        "Content-Type": "application/json",
    }


async def submit_retexture(
    model_url: str,
    image_style_url: str | None = None,
    text_style_prompt: str | None = None,
    ai_model: str = "meshy-6",
    enable_pbr: bool = True,
    enable_original_uv: bool = True,
    remove_lighting: bool = True,
    hd_texture: bool = False,
    target_formats: list[str] | None = None,
) -> str:
    """Submit a Retexture task. Returns Meshy task_id.

    Either image_style_url or text_style_prompt must be provided (Meshy requirement).
    """
    body = build_retexture_body(
        model_url=model_url,
        image_style_url=image_style_url,
        text_style_prompt=text_style_prompt,
        ai_model=ai_model,
        enable_pbr=enable_pbr,
        enable_original_uv=enable_original_uv,
        remove_lighting=remove_lighting,
        hd_texture=hd_texture,
        target_formats=target_formats,
    )

    url = f"{settings.meshy_base_url}/retexture"
    async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as c:
        r = await c.post(url, json=body)
        if r.status_code >= 400:
            raise MeshyJobError(
                f"meshy retexture submit HTTP {r.status_code}: {r.text}"
            )
        data = r.json()
    task_id = data.get("result")
    if not task_id:
        raise MeshyJobError(f"meshy retexture submit: no `result` in response: {data}")
    log.info(
        "meshy retexture submitted task_id=%s dummy_mode=%s",
        task_id, is_dummy_mode(),
    )
    return task_id


def build_retexture_body(
    model_url: str,
    image_style_url: str | None = None,
    text_style_prompt: str | None = None,
    ai_model: str = "meshy-6",
    enable_pbr: bool = True,
    enable_original_uv: bool = True,
    remove_lighting: bool = True,
    hd_texture: bool = False,
    target_formats: list[str] | None = None,
) -> dict[str, Any]:
    """Build the JSON payload for POST /retexture."""
    if not image_style_url and not text_style_prompt:
        raise ValueError(
            "submit_retexture requires either image_style_url or text_style_prompt"
        )

    body: dict[str, Any] = {
        "model_url": model_url,
        "ai_model": ai_model,
        "enable_pbr": enable_pbr,
        "enable_original_uv": enable_original_uv,
        "remove_lighting": remove_lighting,
        "hd_texture": hd_texture,
    }
    if image_style_url:
        body["image_style_url"] = image_style_url
    if text_style_prompt:
        body["text_style_prompt"] = text_style_prompt
    if target_formats:
        body["target_formats"] = list(target_formats)
    return body


async def _get_task(task_id: str) -> dict[str, Any]:
    url = f"{settings.meshy_base_url}/retexture/{task_id}"
    async with httpx.AsyncClient(timeout=30.0, headers=_headers()) as c:
        r = await c.get(url)
        if r.status_code >= 400:
            raise MeshyJobError(
                f"meshy retexture poll HTTP {r.status_code}: {r.text}"
            )
        return r.json()


async def poll_until_complete(task_id: str) -> dict[str, Any]:
    """Poll Meshy retexture task until SUCCEEDED. Returns task dict.

    Raises MeshyJobError on FAILED/CANCELED. TimeoutError on poll timeout.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + settings.meshy_poll_timeout_s
    last_status: str | None = None
    last_progress = -1
    while True:
        task = await _get_task(task_id)
        status = (task.get("status") or "").upper()
        progress = int(task.get("progress") or 0)
        if status != last_status or progress != last_progress:
            log.info(
                "meshy retexture %s status=%s progress=%d%%",
                task_id, status, progress,
            )
            last_status, last_progress = status, progress
        if status == "SUCCEEDED":
            return task
        if status in {"FAILED", "CANCELED"}:
            err = task.get("task_error") or status.lower()
            raise MeshyJobError(f"meshy retexture {task_id} {status}: {err}")
        if loop.time() > deadline:
            raise TimeoutError(
                f"meshy retexture {task_id} did not complete in "
                f"{settings.meshy_poll_timeout_s}s (last seen: {last_status} {last_progress}%)"
            )
        await asyncio.sleep(settings.meshy_poll_interval_s)


def extract_glb_url(task: dict[str, Any]) -> str:
    """Pull the GLB download URL from a SUCCEEDED retexture task."""
    model_urls = task.get("model_urls") or {}
    glb_url = model_urls.get("glb") or task.get("model_url")
    if not glb_url:
        raise MeshyJobError(
            f"meshy retexture result missing glb url: "
            f"model_urls keys={list(model_urls.keys())}, task keys={list(task.keys())}"
        )
    return glb_url


async def download_retexture_glb(url: str, local_path: Path) -> int:
    """Download retextured GLB. Validates glTF magic bytes. Returns byte size."""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=180.0) as c:
        r = await c.get(url, follow_redirects=True)
    if r.status_code != 200:
        raise MeshyDownloadError(
            f"meshy GLB download HTTP {r.status_code} from {url}: {r.text[:200]}"
        )
    if r.content[:4] != GLB_MAGIC:
        raise MeshyDownloadError(
            f"downloaded file has invalid magic bytes: {r.content[:4]!r} (expected b'glTF')"
        )
    local_path.write_bytes(r.content)
    return len(r.content)
