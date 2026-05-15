import json
from typing import Any

from starlette.datastructures import UploadFile


def clean_unity_str(s: str) -> str:
    if not s:
        return s
    return s.lstrip("﻿").replace("\x00", "").strip()


def parse_metadata(raw: str) -> list[dict[str, Any]]:
    cleaned = clean_unity_str(raw)
    if not cleaned:
        return []
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("metadata must be a JSON array")
    return parsed


async def collect_frames(form, prefix: str = "frame_") -> tuple[list[bytes], list[str]]:
    """Collect uploaded files whose field name matches `{prefix}{int}`, ordered by index.

    Default prefix "frame_" preserves the legacy single-burst contract. The dual-capture
    flow calls this twice with prefix="body_" and prefix="face_" to pull two ordered bursts
    out of one multipart submission.
    """
    indices: list[tuple[int, str, UploadFile]] = []
    for key, value in form.multi_items():
        if not isinstance(value, UploadFile):
            continue
        if not key.startswith(prefix):
            continue
        try:
            idx = int(key[len(prefix):])
        except ValueError:
            continue
        indices.append((idx, key, value))

    indices.sort(key=lambda t: t[0])
    frames: list[bytes] = []
    names: list[str] = []
    for _, key, upload in indices:
        frames.append(await upload.read())
        names.append(key)
    return frames, names
