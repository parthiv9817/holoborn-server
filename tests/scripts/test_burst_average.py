"""Standalone test for burst_average against frozen Quest burst fixture.

Loads frame_0..frame_4 from tests/inputs/burst_5frames_quest_20260504, runs them
through app.services.preprocessing.burst_average, and writes:
  - tests/outputs/burst_average/averaged.jpg        (the averaged output)
  - tests/outputs/burst_average/diff_vs_frame0.jpg  (per-pixel abs diff, 4x amplified)
  - tests/outputs/burst_average/frame_0_copy.jpg    (copy of frame 0 for side-by-side)

Prints noise stats so we can quantify the "less noise" claim, not just eyeball it.
Run from anywhere — paths resolve against repo root.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.services.preprocessing import burst_average  # noqa: E402

BURST_DIR = REPO_ROOT / "tests" / "inputs" / "burst_5frames_quest_20260504"
OUT_DIR = REPO_ROOT / "tests" / "outputs" / "burst_average"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    frame_paths = sorted(BURST_DIR.glob("frame_*.jpg"))
    if len(frame_paths) != 5:
        print(f"expected 5 frames, found {len(frame_paths)}")
        return 1

    jpeg_bytes = [p.read_bytes() for p in frame_paths]
    print(f"loaded {len(jpeg_bytes)} frames from {BURST_DIR}")
    for p, b in zip(frame_paths, jpeg_bytes):
        print(f"  {p.name}: {len(b)} bytes")

    averaged = burst_average(jpeg_bytes)  # BGR — frame_decoder uses cv2.imdecode
    print(f"averaged shape={averaged.shape} dtype={averaged.dtype}")

    out_avg = OUT_DIR / "averaged.jpg"
    cv2.imwrite(str(out_avg), averaged, [cv2.IMWRITE_JPEG_QUALITY, 95])

    frame0_bgr = cv2.imdecode(np.frombuffer(jpeg_bytes[0], dtype=np.uint8), cv2.IMREAD_COLOR)
    cv2.imwrite(str(OUT_DIR / "frame_0_copy.jpg"), frame0_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])

    diff = cv2.absdiff(averaged, frame0_bgr)
    diff_amp = np.clip(diff.astype(np.float32) * 4.0, 0, 255).astype(np.uint8)
    cv2.imwrite(str(OUT_DIR / "diff_vs_frame0.jpg"), diff_amp, [cv2.IMWRITE_JPEG_QUALITY, 95])

    print()
    print("--- noise stats ---")
    decoded = [
        cv2.imdecode(np.frombuffer(b, dtype=np.uint8), cv2.IMREAD_COLOR).astype(np.float32)
        for b in jpeg_bytes
    ]

    stack = np.stack(decoded, axis=0)
    per_pixel_std = stack.std(axis=0).mean()
    avg_to_frame0_mae = np.abs(averaged.astype(np.float32) - decoded[0]).mean()

    print(f"per-pixel stddev across 5 frames (mean): {per_pixel_std:.3f}")
    print(f"  -> higher = more frame-to-frame jitter / sensor noise being averaged out")
    print(f"avg(burst) vs frame_0 MAE: {avg_to_frame0_mae:.3f}")
    print(f"  -> small but nonzero means averaging is actually doing work")

    print()
    print(f"wrote: {out_avg}")
    print(f"wrote: {OUT_DIR / 'frame_0_copy.jpg'}")
    print(f"wrote: {OUT_DIR / 'diff_vs_frame0.jpg'}  (4x amplified)")
    print()
    print("eyeball test: open frame_0_copy.jpg and averaged.jpg side by side.")
    print("  averaged should look slightly smoother on flat regions (walls, skin).")
    print("  motion edges (controller, hand) may show ghosting if Quest moved during burst.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
