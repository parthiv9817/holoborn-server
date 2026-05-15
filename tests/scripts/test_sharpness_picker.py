"""Standalone test for pick_sharpest against a known Quest burst.

Loads frame_0..frame_4 from yesterday's successful e2e run (f60f5313). Prints the
per-frame Laplacian variance score and confirms pick_sharpest returns the highest.
Also runs against the frozen burst fixture as a regression anchor.

Run from anywhere: `python3 tests/scripts/test_sharpness_picker.py`
Exits 0 on success, 1 on assertion failure.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.services.preprocessing import pick_sharpest  # noqa: E402


def _score(jpeg: bytes) -> float:
    arr = np.frombuffer(jpeg, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _run_against(burst_dir: Path) -> int:
    frame_paths = sorted(burst_dir.glob("frame_*.jpg"))
    if not frame_paths:
        print(f"no frames found in {burst_dir}")
        return 1
    bursts = [p.read_bytes() for p in frame_paths]
    print(f"\n=== burst: {burst_dir.name} ({len(bursts)} frames) ===")
    full_res_scores = [_score(b) for b in bursts]
    for p, s in zip(frame_paths, full_res_scores):
        print(f"  {p.name}: lap_var (full-res) = {s:.2f}")

    expected_idx = int(np.argmax(full_res_scores))
    picked_bytes, picked_idx, picked_score = pick_sharpest(bursts)
    print(f"pick_sharpest returned idx={picked_idx} score={picked_score:.2f}")
    print(f"expected sharpest (full-res argmax)= idx={expected_idx} score={full_res_scores[expected_idx]:.2f}")

    assert picked_bytes == bursts[picked_idx], "picked bytes != bursts[picked_idx]"

    # picker downscales for speed, so ranking might differ vs full-res by 1 slot
    # if scores are close. Allow either the full-res winner or a tie within 5%.
    if picked_idx != expected_idx:
        ratio = full_res_scores[picked_idx] / full_res_scores[expected_idx]
        assert ratio >= 0.95, (
            f"picked idx {picked_idx} (score {full_res_scores[picked_idx]:.2f}) "
            f"is meaningfully worse than full-res argmax idx {expected_idx} "
            f"(score {full_res_scores[expected_idx]:.2f}); ratio={ratio:.3f}"
        )
        print(f"  (picker chose differently — within 5% of full-res argmax, accepted)")
    else:
        print(f"  (picker matched full-res argmax)")
    return 0


def main() -> int:
    rc = 0
    f60_burst = REPO_ROOT / "results" / "scans" / "20260514_131115_f60f5313"
    if f60_burst.exists():
        rc |= _run_against(f60_burst)

    frozen = REPO_ROOT / "tests" / "inputs" / "burst_5frames_quest_20260504"
    if frozen.exists():
        rc |= _run_against(frozen)

    if rc == 0:
        print("\nall sharpness checks passed.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
