"""Standalone test for collect_frames(form, prefix=...) — the dual-capture
contract sends body_0..body_4 and face_0..face_4 in one multipart submission.
This script fakes a Starlette form and asserts each prefix returns only its own
ordered bursts, plus that the legacy default ("frame_") still works in isolation.

Run from anywhere: `python3 tests/scripts/test_multipart_prefixed.py`
Exits 0 on success, 1 on first failed assertion.
"""

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from starlette.datastructures import UploadFile  # noqa: E402

from app.services.multipart_utils import collect_frames  # noqa: E402


class _FakeUpload:
    """Minimal UploadFile stand-in. isinstance check in collect_frames passes
    because we subclass UploadFile via __class__ trick — simpler to just construct
    a real UploadFile with BytesIO."""

    def __init__(self, payload: bytes):
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


def _make_upload(payload: bytes) -> UploadFile:
    import io
    return UploadFile(file=io.BytesIO(payload), filename="x.jpg")


class _FakeForm:
    def __init__(self, items: list[tuple[str, object]]):
        self._items = items

    def multi_items(self):
        return list(self._items)


async def _run() -> int:
    body_payloads = [f"body-{i}".encode() for i in range(5)]
    face_payloads = [f"face-{i}".encode() for i in range(3)]
    legacy_payloads = [f"legacy-{i}".encode() for i in range(2)]

    items: list[tuple[str, object]] = []
    items.append(("metadata", "should-be-ignored"))  # non-UploadFile, skipped
    for i, b in enumerate(body_payloads):
        items.append((f"body_{i}", _make_upload(b)))
    for i, b in enumerate(face_payloads):
        items.append((f"face_{i}", _make_upload(b)))
    for i, b in enumerate(legacy_payloads):
        items.append((f"frame_{i}", _make_upload(b)))
    items.append(("body_abc", _make_upload(b"junk")))  # bad index, skipped

    form = _FakeForm(items)

    # collect with body_ prefix — should get exactly the 5 body payloads in order
    body_frames, body_names = await collect_frames(form, prefix="body_")
    assert len(body_frames) == 5, f"expected 5 body frames, got {len(body_frames)}"
    assert body_frames == body_payloads, f"body payloads mismatch: {body_frames}"
    assert body_names == [f"body_{i}" for i in range(5)], f"body names: {body_names}"
    print(f"body_ prefix: OK ({len(body_frames)} frames in order)")

    # collect with face_ prefix
    face_frames, face_names = await collect_frames(form, prefix="face_")
    assert len(face_frames) == 3, f"expected 3 face frames, got {len(face_frames)}"
    assert face_frames == face_payloads
    assert face_names == [f"face_{i}" for i in range(3)]
    print(f"face_ prefix: OK ({len(face_frames)} frames in order)")

    # legacy default — should pull the frame_ ones
    legacy_frames, legacy_names = await collect_frames(form)
    assert len(legacy_frames) == 2, f"expected 2 legacy frames, got {len(legacy_frames)}"
    assert legacy_frames == legacy_payloads
    print(f"default (frame_) prefix: OK ({len(legacy_frames)} legacy frames)")

    # explicit empty case
    nope_frames, _ = await collect_frames(form, prefix="missing_")
    assert nope_frames == [], "expected empty list for unknown prefix"
    print(f"unknown prefix: OK (empty)")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
