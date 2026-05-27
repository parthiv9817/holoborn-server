"""Isolated test: feed a Hunyuan-output GLB to Meshy v6 Retexture.

Stages the input GLB + reference portrait at the local ngrok URL so Meshy can
fetch them, submits a retexture job (same params as production pipeline),
polls until complete, downloads the clean PBR-textured GLB to
results/avatars/{basename}_retex.glb.

Both files MUST live in results/avatars/ (the dir uvicorn serves under /avatars/).

Run from repo root:
    .venv/bin/python tools/test_meshy_retex.py \\
        results/avatars/<hunyuan>.glb --portrait results/avatars/<portrait>.png

Defaults: most recent *_hunyuan_test.glb + most recent *_portrait.png.

Prereqs: uvicorn + ngrok running, MESHY_PUBLIC_HOST set in .env, real
MESHY_API_KEY in .env (not dummy).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from app.config import AVATARS_DIR, settings  # noqa: E402
from app.services.meshy_client import (  # noqa: E402
    download_retexture_glb,
    extract_glb_url,
    is_dummy_mode,
    poll_until_complete,
    submit_retexture,
)


def _default_glb() -> Path:
    cands = sorted(
        AVATARS_DIR.glob("*_hunyuan_test.glb"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cands:
        raise FileNotFoundError(
            f"no *_hunyuan_test.glb in {AVATARS_DIR} — "
            "run tools/test_hunyuan_endpoint.py first"
        )
    return cands[0]


def _default_portrait() -> Path:
    cands = sorted(
        AVATARS_DIR.glob("*_portrait.png"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cands:
        raise FileNotFoundError(f"no *_portrait.png in {AVATARS_DIR}")
    return cands[0]


def _public_url(filename: str) -> str:
    host = settings.meshy_public_host.strip()
    if not host:
        raise RuntimeError(
            "MESHY_PUBLIC_HOST not set in .env — ngrok URL needed for Meshy to fetch"
        )
    if host.startswith(("http://", "https://")):
        base = host.rstrip("/")
    else:
        scheme = "http" if host.startswith(("localhost", "127.")) else "https"
        base = f"{scheme}://{host.rstrip('/')}"
    return f"{base}/avatars/{filename}"


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("glb", nargs="?", type=Path, help="input GLB (default: latest *_hunyuan_test.glb)")
    ap.add_argument("--portrait", type=Path, help="reference portrait PNG (default: latest *_portrait.png)")
    args = ap.parse_args()

    if is_dummy_mode():
        raise RuntimeError("MESHY_API_KEY missing/dummy — set real key in .env")

    glb_path = (args.glb or _default_glb()).resolve()
    portrait_path = (args.portrait or _default_portrait()).resolve()

    if not glb_path.exists():
        raise FileNotFoundError(glb_path)
    if not portrait_path.exists():
        raise FileNotFoundError(portrait_path)

    # Both files MUST be inside AVATARS_DIR — that's what uvicorn serves under /avatars/.
    if glb_path.parent != AVATARS_DIR.resolve():
        raise RuntimeError(f"GLB must be inside {AVATARS_DIR}, got {glb_path.parent}")
    if portrait_path.parent != AVATARS_DIR.resolve():
        raise RuntimeError(f"portrait must be inside {AVATARS_DIR}, got {portrait_path.parent}")

    model_url = _public_url(glb_path.name)
    portrait_url = _public_url(portrait_path.name)
    print(f"[test] input GLB:          {glb_path.name} ({glb_path.stat().st_size / 1e6:.2f} MB)")
    print(f"[test] reference portrait: {portrait_path.name}")
    print(f"[test] model_url:          {model_url}")
    print(f"[test] image_style_url:    {portrait_url}")
    print(
        f"[test] meshy params: ai_model=meshy-6, enable_pbr=True, "
        f"enable_original_uv=False, remove_lighting=True, hd_texture=True"
    )
    print()

    t0 = time.perf_counter()
    task_id = await submit_retexture(
        model_url=model_url,
        image_style_url=portrait_url,
        ai_model="meshy-6",
        enable_pbr=True,
        enable_original_uv=False,
        remove_lighting=True,
        hd_texture=True,
        target_formats=["glb"],
    )
    print(f"[test] meshy task submitted: id={task_id}")

    print("[test] polling /retexture status (3s interval)...")
    task = await poll_until_complete(task_id)
    elapsed = time.perf_counter() - t0
    print(f"[test] meshy COMPLETED in {elapsed:.1f}s")

    clean_url = extract_glb_url(task)
    print(f"[test] clean GLB URL: {clean_url[:120]}{'...' if len(clean_url) > 120 else ''}")

    out_path = AVATARS_DIR / f"{glb_path.stem}_retex.glb"
    print(f"[test] downloading → {out_path.name}")
    size = await download_retexture_glb(clean_url, out_path)
    print(f"[test] retex GLB saved: {size} bytes ({size / 1e6:.2f} MB)")

    print()
    print(f"[ok] local:                    {out_path}")
    print(f"[ok] public (Babylon-droppable): {_public_url(out_path.name)}")
    print(f"[ok] Babylon sandbox:           https://sandbox.babylonjs.com/")


if __name__ == "__main__":
    asyncio.run(main())
