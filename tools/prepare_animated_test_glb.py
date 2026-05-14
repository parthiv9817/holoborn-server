"""Prepare results/avatars/test.glb from Meshy rigging + animation.

This is the asset path the Quest B-button loader already downloads.

Run:
    .venv/bin/python tools/prepare_animated_test_glb.py \
        tests/outputs/full_pipeline/91161109_RETEXTURED.glb --action-id 0
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.config import AVATARS_DIR, settings  # noqa: E402
from app.services.meshy_animation_client import (  # noqa: E402
    extract_animation_glb_url,
    extract_basic_animation_url,
    extract_rigged_glb_url,
    poll_animation_until_complete,
    poll_rigging_until_complete,
    submit_animation,
    submit_rigging,
)
from app.services.meshy_client import download_retexture_glb, is_dummy_mode  # noqa: E402


GLB_MAGIC = b"glTF"
OUT_DIR = REPO_ROOT / "tests" / "outputs" / "meshy_glbs"


def build_public_avatar_url(host: str, filename: str) -> str:
    clean = host.strip().rstrip("/")
    if clean.startswith(("http://", "https://")):
        base = clean
    else:
        scheme = "http" if clean.startswith(("localhost", "127.")) else "https"
        base = f"{scheme}://{clean}"
    return f"{base}/avatars/{filename}"


def resolve_input(path_arg: str | None) -> Path:
    if path_arg:
        path = Path(path_arg).resolve()
    else:
        default = REPO_ROOT / "tests" / "outputs" / "full_pipeline" / "91161109_RETEXTURED.glb"
        if default.exists():
            path = default
        else:
            candidates = sorted(AVATARS_DIR.glob("*.glb"), key=lambda p: p.stat().st_mtime)
            if not candidates:
                raise SystemExit("No input GLB provided and no local GLBs found")
            path = candidates[-1]
    if not path.exists():
        raise SystemExit(f"Input GLB not found: {path}")
    if path.read_bytes()[:4] != GLB_MAGIC:
        raise SystemExit(f"Input is not a GLB: {path}")
    return path


def stage_input(path: Path) -> tuple[Path, str]:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    staged = AVATARS_DIR / f"meshy_rig_input_{ts}.glb"
    shutil.copy2(path, staged)
    host = settings.meshy_public_host.strip()
    if not host:
        raise SystemExit("MESHY_PUBLIC_HOST is required so Meshy can fetch the staged GLB")
    return staged, build_public_avatar_url(host, staged.name)


async def verify_public_url(url: str) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.head(url, follow_redirects=True)
    if response.status_code != 200:
        raise SystemExit(f"Staged model_url is not reachable: HTTP {response.status_code} {url}")


async def prepare(args: argparse.Namespace) -> Path:
    input_path = resolve_input(args.glb_path)
    staged_path, model_url = stage_input(input_path)
    print(f"Input:  {input_path}")
    print(f"Staged: {staged_path}")
    print(f"URL:    {model_url}")
    print(f"Mode:   {'dummy' if is_dummy_mode() else 'real'}")

    await verify_public_url(model_url)
    started = time.perf_counter()

    rig_id = await submit_rigging(model_url, height_meters=args.height)
    print(f"Rig task: {rig_id}")
    rig_task = await poll_rigging_until_complete(rig_id)

    if args.rig_only:
        download_url = extract_rigged_glb_url(rig_task)
        label = "rigged_only"
    elif args.basic_walking:
        download_url = extract_basic_animation_url(rig_task, "walking")
        label = "basic_walking"
    else:
        anim_id = await submit_animation(rig_id, action_id=args.action_id, fps=args.fps)
        print(f"Animation task: {anim_id}")
        anim_task = await poll_animation_until_complete(anim_id)
        download_url = extract_animation_glb_url(anim_task)
        label = f"anim_action{args.action_id}"

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    archived = OUT_DIR / f"{label}_{ts}.glb"
    size = await download_retexture_glb(download_url, archived)

    final_path = AVATARS_DIR / args.out_name
    shutil.copy2(archived, final_path)
    elapsed = time.perf_counter() - started
    print(f"Downloaded: {archived} ({size:,} bytes)")
    print(f"Mirrored:   {final_path}")
    print(f"Elapsed:    {elapsed:.1f}s")
    return final_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the animated GLB served to Quest B button")
    parser.add_argument("glb_path", nargs="?", help="Input GLB. Defaults to full-pipeline retexture output.")
    parser.add_argument("--action-id", type=int, default=0, help="Meshy animation action_id. 0 = Idle.")
    parser.add_argument("--height", type=float, default=1.7, help="Character height in meters for rigging.")
    parser.add_argument("--fps", type=int, choices=[24, 25, 30, 60], help="Optional animation FPS post-process.")
    parser.add_argument("--basic-walking", action="store_true", help="Use rigging's free walking GLB.")
    parser.add_argument("--rig-only", action="store_true", help="Download rigged character without animation.")
    parser.add_argument("--out-name", default="test.glb", help="Avatar filename served under /avatars/.")
    return parser.parse_args()


def main() -> int:
    asyncio.run(prepare(parse_args()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
