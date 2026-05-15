"""Standalone test for portraitize_dual() — hits the real OpenAI API.

Uses yesterday's f60f5313 frame_0 as the body shot and a face-region crop of the
same frame as a stand-in for the face closeup (since we don't have a real face
closeup captured yet — that's the Quest-side work). The point of this test is to
confirm portraitize_dual produces a valid portrait through the real production
code path, not to validate the visual quality of a synthetic face crop.

Costs ~$0.19 per run and takes ~150s. Gated behind RUN_NETWORK_TESTS=1 so it
doesn't fire by accident:
    RUN_NETWORK_TESTS=1 python3 tests/scripts/test_portraitize_dual.py

Without the env var it does a dry-run: validates inputs and signature only.
"""

import os
import sys
import time
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env")

from app.services.portraitizer import (  # noqa: E402
    PORTRAIT_PROMPT_V4,
    portraitize_dual,
)

INPUT_DIR = REPO_ROOT / "results" / "scans" / "20260514_131115_f60f5313"
BODY_PATH = INPUT_DIR / "frame_0.jpg"
OUT_DIR = REPO_ROOT / "tests" / "outputs" / "portraitize_dual"


def _make_face_stand_in(body_jpeg: bytes) -> bytes:
    """Crop a face-region from the body shot to simulate a closeup capture."""
    import numpy as np
    arr = np.frombuffer(body_jpeg, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    h, w = bgr.shape[:2]
    # Heuristic: face sits roughly in horizontal middle, vertical upper third
    cx, cy = w // 2, int(h * 0.22)
    half_w, half_h = int(w * 0.25), int(h * 0.18)
    x0, y0 = max(0, cx - half_w), max(0, cy - half_h)
    x1, y1 = min(w, cx + half_w), min(h, cy + half_h)
    crop = bgr[y0:y1, x0:x1]
    crop_up = cv2.resize(crop, (crop.shape[1] * 2, crop.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", crop_up, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise RuntimeError("failed to encode face crop")
    return buf.tobytes()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not BODY_PATH.exists():
        print(f"missing fixture: {BODY_PATH}")
        return 1

    body_bytes = BODY_PATH.read_bytes()
    face_bytes = _make_face_stand_in(body_bytes)
    print(f"body: {len(body_bytes)} bytes")
    print(f"face stand-in (cropped from body): {len(face_bytes)} bytes")
    print(f"V4 prompt length: {len(PORTRAIT_PROMPT_V4)} chars")

    # save the face stand-in so we can eyeball whether the crop is sane
    (OUT_DIR / "face_stand_in.jpg").write_bytes(face_bytes)
    print(f"saved face stand-in -> {OUT_DIR / 'face_stand_in.jpg'}")

    if os.environ.get("RUN_NETWORK_TESTS") != "1":
        print()
        print("DRY RUN — RUN_NETWORK_TESTS != 1, skipping OpenAI call.")
        print("Re-run with: RUN_NETWORK_TESTS=1 python3 tests/scripts/test_portraitize_dual.py")
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set in env; aborting")
        return 1

    print()
    print(f"calling portraitize_dual (real OpenAI call, ~$0.19, ~150s)...")
    t0 = time.perf_counter()
    portrait = portraitize_dual(body_bytes, face_bytes)
    elapsed = time.perf_counter() - t0
    if not portrait or not portrait.startswith(b"\x89PNG"):
        print(f"FAIL: portrait bytes invalid (head={portrait[:8]!r})")
        return 1

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"portrait_{ts}.png"
    out_path.write_bytes(portrait)
    print(f"OK: wrote {out_path} ({len(portrait)} bytes) in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
