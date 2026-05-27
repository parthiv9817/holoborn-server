"""Isolated test: rig a Meshy-retex'd GLB + graft PBR materials back onto the rig.

Mirrors the Phase-5 logic in generation_pipeline.py but as a standalone:
  retex'd GLB (PBR, no skel)
    → Meshy rigging (adds skel, strips PBR)
      → graft_pbr_materials (re-bakes PBR onto rigged topology)
        → final GLB (skel + PBR)

Run from repo root:
    .venv/bin/python tools/test_meshy_rigging.py \\
        [path-to-retex.glb]

Default: latest *_retex.glb in results/avatars/.

Pre-reqs: uvicorn + ngrok up, MESHY_PUBLIC_HOST set, real Meshy key.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from app.config import AVATARS_DIR, settings  # noqa: E402
from app.services.meshy_animation_client import (  # noqa: E402
    extract_rigged_glb_url,
    poll_rigging_until_complete,
    submit_rigging,
)
from tools.graft_pbr_materials import graft  # noqa: E402


def _default_retex_glb() -> Path:
    cands = sorted(
        AVATARS_DIR.glob("*_retex.glb"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cands:
        raise FileNotFoundError(
            f"no *_retex.glb in {AVATARS_DIR} — run tools/test_meshy_retex.py first"
        )
    return cands[0]


def _public_url(filename: str) -> str:
    host = settings.meshy_public_host.strip()
    if not host:
        raise RuntimeError("MESHY_PUBLIC_HOST not set in .env")
    if host.startswith(("http://", "https://")):
        base = host.rstrip("/")
    else:
        scheme = "http" if host.startswith(("localhost", "127.")) else "https"
        base = f"{scheme}://{host.rstrip('/')}"
    return f"{base}/avatars/{filename}"


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "retex_glb",
        nargs="?",
        type=Path,
        help="path to retex'd GLB (default: latest *_retex.glb)",
    )
    args = ap.parse_args()

    retex_path = (args.retex_glb or _default_retex_glb()).resolve()
    if retex_path.parent != AVATARS_DIR.resolve():
        raise RuntimeError(f"retex GLB must be inside {AVATARS_DIR}, got {retex_path.parent}")
    if not retex_path.exists():
        raise FileNotFoundError(retex_path)

    model_url = _public_url(retex_path.name)
    print(f"[test] retex GLB:  {retex_path.name} ({retex_path.stat().st_size / 1e6:.2f} MB)")
    print(f"[test] model_url:  {model_url}")
    print()

    t0 = time.perf_counter()
    rig_task_id = await submit_rigging(model_url=model_url, height_meters=1.7)
    print(f"[test] rigging task submitted: id={rig_task_id}")

    print("[test] polling rigging /status (3s interval)...")
    rig_task = await poll_rigging_until_complete(rig_task_id)
    elapsed = time.perf_counter() - t0
    print(f"[test] rigging COMPLETED in {elapsed:.1f}s")

    rigged_remote_url = extract_rigged_glb_url(rig_task)
    short_url = rigged_remote_url[:100] + ("..." if len(rigged_remote_url) > 100 else "")
    print(f"[test] rigged URL: {short_url}")

    rigged_raw_path = AVATARS_DIR / f"{retex_path.stem}_rigged_raw.glb"
    print(f"[test] downloading rigged raw → {rigged_raw_path.name}")
    t_dl = time.perf_counter()
    async with httpx.AsyncClient(timeout=180.0) as c:
        r = await c.get(rigged_remote_url, follow_redirects=True)
    r.raise_for_status()
    if r.content[:4] != b"glTF":
        raise RuntimeError(f"rigged GLB not a glTF — magic={r.content[:4]!r}")
    rigged_raw_path.write_bytes(r.content)
    print(
        f"[test] rigged raw saved: {len(r.content) / 1e6:.2f} MB "
        f"in {time.perf_counter() - t_dl:.1f}s"
    )

    grafted_path = AVATARS_DIR / f"{retex_path.stem}_rigged_grafted.glb"
    print(f"[test] grafting PBR materials → {grafted_path.name}")
    t_gr = time.perf_counter()
    summary = graft(retex_path, rigged_raw_path, grafted_path)
    print(f"[test] graft done in {time.perf_counter() - t_gr:.1f}s")
    print(f"[test] graft summary: {summary}")

    print()
    print(f"[ok] retex'd GLB (PBR, no skel):  {retex_path.name}")
    print(f"[ok] rigged raw (skel, no PBR):   {rigged_raw_path.name}")
    print(f"[ok] FINAL grafted (skel + PBR):  {grafted_path.name} "
          f"({grafted_path.stat().st_size / 1e6:.2f} MB)")
    print(f"[ok] public URL:  {_public_url(grafted_path.name)}")


if __name__ == "__main__":
    asyncio.run(main())
