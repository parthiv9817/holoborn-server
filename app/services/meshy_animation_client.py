"""Meshy Rigging + Animation API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings
from app.services.meshy_client import MeshyJobError, _headers, is_dummy_mode


log = logging.getLogger(__name__)


def build_rigging_body(
    model_url: str,
    height_meters: float = 1.7,
    texture_image_url: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model_url": model_url,
        "height_meters": height_meters,
    }
    if texture_image_url:
        body["texture_image_url"] = texture_image_url
    return body


def build_animation_body(
    rig_task_id: str,
    action_id: int = 0,
    fps: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "rig_task_id": rig_task_id,
        "action_id": action_id,
    }
    if fps is not None:
        body["post_process"] = {
            "operation_type": "change_fps",
            "fps": fps,
        }
    return body


async def submit_rigging(
    model_url: str,
    height_meters: float = 1.7,
    texture_image_url: str | None = None,
) -> str:
    body = build_rigging_body(model_url, height_meters, texture_image_url)
    return await _post_task("/rigging", body, "rigging")


async def submit_animation(
    rig_task_id: str,
    action_id: int = 0,
    fps: int | None = None,
) -> str:
    body = build_animation_body(rig_task_id, action_id, fps)
    return await _post_task("/animations", body, "animation")


async def poll_rigging_until_complete(task_id: str) -> dict[str, Any]:
    return await _poll_task("/rigging", task_id, "rigging")


async def poll_animation_until_complete(task_id: str) -> dict[str, Any]:
    return await _poll_task("/animations", task_id, "animation")


def extract_rigged_glb_url(task: dict[str, Any]) -> str:
    result = task.get("result") or {}
    url = result.get("rigged_character_glb_url")
    if not url:
        raise MeshyJobError(f"rigging result missing rigged_character_glb_url: {task}")
    return url


def extract_basic_animation_url(task: dict[str, Any], name: str = "walking") -> str:
    result = task.get("result") or {}
    basic = result.get("basic_animations") or {}
    url = basic.get(f"{name}_glb_url")
    if not url:
        raise MeshyJobError(f"rigging result missing basic {name} animation URL: {task}")
    return url


def extract_animation_glb_url(task: dict[str, Any]) -> str:
    result = task.get("result") or {}
    url = result.get("animation_glb_url")
    if not url:
        raise MeshyJobError(f"animation result missing animation_glb_url: {task}")
    return url


async def _post_task(path: str, body: dict[str, Any], label: str) -> str:
    url = f"{settings.meshy_base_url}{path}"
    # 300s timeout — Meshy /rigging endpoint can be slow on the initial POST
    # because Meshy fetches the input model_url upfront before accepting the
    # task. If our ngrok tunnel is rate-limited, this fetch can take 60-120s.
    # 300s leaves headroom.
    async with httpx.AsyncClient(timeout=300.0, headers=_headers()) as c:
        r = await c.post(url, json=body)
    if r.status_code >= 400:
        raise MeshyJobError(f"meshy {label} submit HTTP {r.status_code}: {r.text}")
    data = r.json()
    task_id = data.get("result")
    if not task_id:
        raise MeshyJobError(f"meshy {label} submit: no `result` in response: {data}")
    log.info("meshy %s submitted task_id=%s dummy_mode=%s", label, task_id, is_dummy_mode())
    return task_id


async def _get_task(path: str, task_id: str, label: str) -> dict[str, Any]:
    url = f"{settings.meshy_base_url}{path}/{task_id}"
    async with httpx.AsyncClient(timeout=30.0, headers=_headers()) as c:
        r = await c.get(url)
    if r.status_code >= 400:
        raise MeshyJobError(f"meshy {label} poll HTTP {r.status_code}: {r.text}")
    return r.json()


async def _poll_task(path: str, task_id: str, label: str) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + settings.meshy_poll_timeout_s
    last_status: str | None = None
    last_progress = -1
    while True:
        task = await _get_task(path, task_id, label)
        status = (task.get("status") or "").upper()
        progress = int(task.get("progress") or 0)
        if status != last_status or progress != last_progress:
            log.info("meshy %s %s status=%s progress=%d%%", label, task_id, status, progress)
            last_status, last_progress = status, progress
        if status == "SUCCEEDED":
            return task
        if status in {"FAILED", "CANCELED"}:
            err = task.get("task_error") or status.lower()
            raise MeshyJobError(f"meshy {label} {task_id} {status}: {err}")
        if loop.time() > deadline:
            raise TimeoutError(
                f"meshy {label} {task_id} did not complete in "
                f"{settings.meshy_poll_timeout_s}s (last seen: {last_status} {last_progress}%)"
            )
        await asyncio.sleep(settings.meshy_poll_interval_s)
