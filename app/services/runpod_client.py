import base64
from pathlib import Path
from typing import Any

import httpx

from app.config import AVATARS_DIR, settings


class RunPodClient:
    def __init__(self, timeout: float = 60.0) -> None:
        if not settings.runpod_api_key or settings.runpod_api_key == "replace-me":
            raise RuntimeError("RUNPOD_API_KEY is not set in .env")
        self._headers = {
            "Authorization": f"Bearer {settings.runpod_api_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout, headers=self._headers)

    async def submit_job(self, image_b64: str, **extra_input: Any) -> str:
        payload = {"input": {"image_b64": image_b64, **extra_input}}
        r = await self._client.post(settings.runpod_run_url, json=payload)
        r.raise_for_status()
        data = r.json()
        job_id = data.get("id")
        if not job_id:
            raise RuntimeError(f"runpod submit: no id in response: {data}")
        return job_id

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        url = f"{settings.runpod_status_url_base}/{job_id}"
        r = await self._client.get(url)
        r.raise_for_status()
        return r.json()

    async def download_glb(self, output: dict[str, Any], task_id: str) -> Path:
        dest = AVATARS_DIR / f"{task_id}.glb"

        glb_b64 = output.get("glb_b64") or output.get("glb_base64")
        if glb_b64:
            dest.write_bytes(base64.b64decode(glb_b64))
            return dest

        glb_url = output.get("glb_url") or output.get("download_url")
        if glb_url:
            async with self._client.stream("GET", glb_url) as r:
                r.raise_for_status()
                with dest.open("wb") as f:
                    async for chunk in r.aiter_bytes():
                        f.write(chunk)
            return dest

        raise RuntimeError(
            f"runpod output had no glb_b64 / glb_url; keys={list(output.keys())}"
        )

    async def aclose(self) -> None:
        await self._client.aclose()
