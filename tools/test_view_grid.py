"""Isolated smoke-test for view_synthesizer.

Loads a cached front portrait, runs the gpt-image-2 turnaround grid generator,
splits into 4 tiles, saves the source + raw grid + 4 tiles to a timestamped
dir under results/scans/ for visual inspection.

Run from repo root:
    .venv/bin/python tools/test_view_grid.py
    .venv/bin/python tools/test_view_grid.py path/to/portrait.png

If no path is given, defaults to the most recent *_portrait.png in
results/avatars/.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from app.config import AVATARS_DIR, SCANS_DIR  # noqa: E402
from app.services.view_synthesizer import (  # noqa: E402
    generate_grid_image,
    split_grid,
)


def _default_portrait() -> Path:
    cands = sorted(
        AVATARS_DIR.glob("*_portrait.png"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cands:
        raise FileNotFoundError(
            f"no *_portrait.png in {AVATARS_DIR} — pass a path explicitly"
        )
    return cands[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Smoke-test the turnaround view synthesizer")
    ap.add_argument(
        "portrait",
        nargs="?",
        type=Path,
        help="path to source front portrait (default: most recent in results/avatars/)",
    )
    args = ap.parse_args()

    src = args.portrait or _default_portrait()
    print(f"[test] source portrait: {src}")
    portrait_bytes = src.read_bytes()
    print(f"[test] source bytes: {len(portrait_bytes)}")

    out_dir = SCANS_DIR / f"view_grid_test_{time.strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[test] output dir: {out_dir}")

    # Save source for reference
    (out_dir / "00_source_portrait.png").write_bytes(portrait_bytes)

    t0 = time.perf_counter()
    grid_png = generate_grid_image(portrait_bytes)
    elapsed_gen = time.perf_counter() - t0

    grid_path = out_dir / "01_grid_raw_1024x1024.png"
    grid_path.write_bytes(grid_png)
    print(f"[test] saved raw grid -> {grid_path.name} ({len(grid_png)} bytes)")

    t1 = time.perf_counter()
    tiles = split_grid(grid_png)
    elapsed_split = time.perf_counter() - t1

    for view in ("front", "left", "back", "right"):
        png = tiles[view]
        (out_dir / f"tile_{view}.png").write_bytes(png)
        print(f"  saved tile_{view}.png ({len(png)} bytes)")

    print()
    print(f"[ok] gen={elapsed_gen:.2f}s  split={elapsed_split:.2f}s")
    print(f"[ok] inspect: {out_dir}")
    print("     00_source_portrait.png    (input)")
    print("     01_grid_raw_1024x1024.png (raw model output before split)")
    print("     tile_front.png  (TL)")
    print("     tile_left.png   (TR)")
    print("     tile_back.png   (BL)")
    print("     tile_right.png  (BR)")


if __name__ == "__main__":
    main()
