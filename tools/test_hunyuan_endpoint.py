"""Isolated test: submit 4 turnaround tiles to the Hunyuan endpoint, fetch GLB.

Sends the 4 view tiles (front/left/back/right) from a view_grid_test_* dir
to RunPod endpoint itd7oz9wexb1oo, polls until COMPLETED, downloads the GLB
via the existing S3 path, and prints a quick geometry breakdown.

Uses the same hunyuan_client + runpod_client modules that the real pipeline
uses — so a green run here validates the production wiring too.

Run from repo root:
    .venv/bin/python tools/test_hunyuan_endpoint.py
    .venv/bin/python tools/test_hunyuan_endpoint.py path/to/view_grid_dir
    .venv/bin/python tools/test_hunyuan_endpoint.py --keep-remote  # don't delete S3 GLB

Defaults: most recent view_grid_test_* under results/scans/.

Heads-up: cold start ~5 min (image pull + first inference). Warm ~2 min.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from app.config import AVATARS_DIR, SCANS_DIR  # noqa: E402
from app.services.hunyuan_client import poll_until_complete, submit_job  # noqa: E402
from app.services.runpod_client import delete_remote_glb, download_glb  # noqa: E402


def _default_tiles_dir() -> Path:
    cands = sorted(
        SCANS_DIR.glob("view_grid_test_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cands:
        raise FileNotFoundError(
            f"no view_grid_test_* dirs in {SCANS_DIR} — "
            "run tools/test_view_grid.py first"
        )
    return cands[0]


def _load_views(tiles_dir: Path) -> dict[str, bytes]:
    views: dict[str, bytes] = {}
    for name in ("front", "left", "back", "right"):
        p = tiles_dir / f"tile_{name}.png"
        if not p.exists():
            raise FileNotFoundError(f"missing {p}")
        views[name] = p.read_bytes()
        print(f"  {name}: {len(views[name])} bytes ({p.name})")
    return views


def _inspect_glb(local_path: Path) -> None:
    with open(local_path, "rb") as f:
        data = f.read()
    jl = struct.unpack("<I", data[12:16])[0]
    g = json.loads(data[20 : 20 + jl].decode("utf-8").rstrip("\x00 "))
    print()
    print(
        f"[geometry] meshes={len(g.get('meshes', []))} "
        f"materials={len(g.get('materials', []))} "
        f"images={len(g.get('images', []))}"
    )
    for mi, mesh in enumerate(g.get("meshes", [])):
        for pi, prim in enumerate(mesh["primitives"]):
            attrs = prim.get("attributes", {})
            pos_acc = g["accessors"][attrs.get("POSITION", 0)]
            idx_acc = g["accessors"][prim["indices"]] if "indices" in prim else None
            print(
                f"  mesh[{mi}].prim[{pi}]: verts={pos_acc['count']} "
                f"tris={idx_acc['count'] // 3 if idx_acc else '?'} "
                f"attrs={list(attrs.keys())}"
            )
            if pos_acc.get("min") and pos_acc.get("max"):
                mn, mx = pos_acc["min"], pos_acc["max"]
                print(
                    f"    bbox X[{mn[0]:.3f},{mx[0]:.3f}] "
                    f"Y[{mn[1]:.3f},{mx[1]:.3f}] "
                    f"Z[{mn[2]:.3f},{mx[2]:.3f}] "
                    f"H={mx[1] - mn[1]:.3f}"
                )


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "tiles_dir",
        nargs="?",
        type=Path,
        help="dir with tile_{front,left,back,right}.png (default: latest view_grid_test_*)",
    )
    ap.add_argument(
        "--keep-remote",
        action="store_true",
        help="skip S3 delete after fetch (default: delete to save volume space)",
    )
    args = ap.parse_args()

    tiles_dir = args.tiles_dir or _default_tiles_dir()
    print(f"[test] tiles dir: {tiles_dir}")
    print(f"[test] loading 4 view tiles:")
    views = _load_views(tiles_dir)

    total_bytes = sum(len(v) for v in views.values())
    print(f"[test] total payload (pre-base64): {total_bytes} bytes "
          f"≈ {total_bytes * 4 / 3 / 1024:.1f} KB after b64")
    print()
    print(f"[test] submitting to https://api.runpod.ai/v2/itd7oz9wexb1oo/run")
    print(f"[test] heads-up: cold start ~5min; warm worker ~2min")
    t0 = time.perf_counter()
    job_id = await submit_job(views)
    print(f"[test] job_id={job_id}")

    print(f"[test] polling /status (5s interval, timeout from .env)...")
    output = await poll_until_complete(job_id)
    elapsed = time.perf_counter() - t0
    print(f"[test] job COMPLETED in {elapsed:.1f}s")
    print(f"[test] output: {output}")

    glb_volume_path = output.get("glb_volume_path")
    if not glb_volume_path:
        raise RuntimeError(f"output missing glb_volume_path: {output}")

    local_path = AVATARS_DIR / f"{job_id}_hunyuan_test.glb"
    print(f"[test] downloading GLB via S3 → {local_path.name}")
    t_dl = time.perf_counter()
    size = await download_glb(glb_volume_path, local_path)
    print(f"[test] GLB saved: {size} bytes ({size / 1e6:.2f} MB) in {time.perf_counter() - t_dl:.1f}s")

    if not args.keep_remote:
        await delete_remote_glb(glb_volume_path)
        print(f"[test] deleted remote: {glb_volume_path}")
    else:
        print(f"[test] --keep-remote → S3 GLB preserved at {glb_volume_path}")

    _inspect_glb(local_path)

    print()
    print(f"[ok] local GLB: {local_path}")
    print(f"[ok] inspect in Babylon.js sandbox or copy to results/avatars/test*.glb for Y-test")


if __name__ == "__main__":
    asyncio.run(main())
