"""Manual Meshy end-to-end test — replicates yesterday's web-UI rigging+animation flow via API.

Flow:  TRELLIS GLB → /rigging → poll → /animations → poll → download GLB.
Stages input into results/avatars/ so the existing uvicorn+ngrok serves it to Meshy.

Env:  MESHY_API_KEY (real key or falls back to dummy with warning),
      MESHY_PUBLIC_HOST (e.g. grinning-flyable-golf.ngrok-free.dev — unless --model-url given).

    python tests/scripts/test_meshy_manual.py                     # latest GLB, Idle
    python tests/scripts/test_meshy_manual.py path.glb --action-id 16
    python tests/scripts/test_meshy_manual.py --no-animation      # rigging only, no anim credits
    python tests/scripts/test_meshy_manual.py --model-url https://...  # bypass staging
    python tests/scripts/test_meshy_manual.py --retexture --image-style path/to/portrait.png
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.config import AVATARS_DIR  # noqa: E402

DUMMY_KEY = "msy_dummy_api_key_for_test_mode_12345678"
BASE_URL = "https://api.meshy.ai/openapi/v1"
GLB_OUT_DIR = REPO_ROOT / "tests" / "outputs" / "meshy_glbs"
DEFAULT_HEIGHT_M = 1.7
GLB_MAGIC = b"glTF"
POLL_INTERVAL_S = 3.0
POLL_TIMEOUT_S = 600.0


def _digest(key: str) -> str:
    return f"{key[:8]}…{key[-4:]}" if key else "<empty>"


def _hdrs(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def _verify_url(url: str) -> int:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.head(url, follow_redirects=True)
    if r.status_code != 200:
        sys.exit(f"❌ model_url not reachable: HTTP {r.status_code} from {url}")
    return int(r.headers.get("content-length", 0))


async def _post(c: httpx.AsyncClient, key: str, path: str, body: dict) -> str:
    r = await c.post(f"{BASE_URL}{path}", headers=_hdrs(key), json=body)
    if r.status_code >= 400:
        sys.exit(f"❌ POST {path} → HTTP {r.status_code}: {r.text}")
    task_id = r.json().get("result")
    if not task_id:
        sys.exit(f"❌ POST {path} returned no `result`: {r.text}")
    return task_id


async def _poll(c: httpx.AsyncClient, key: str, path: str, label: str) -> dict:
    start = time.perf_counter()
    last_status: str | None = None
    last_progress = -1
    while time.perf_counter() - start < POLL_TIMEOUT_S:
        r = await c.get(f"{BASE_URL}{path}", headers=_hdrs(key))
        if r.status_code >= 400:
            sys.exit(f"❌ poll {label} HTTP {r.status_code}: {r.text}")
        task = r.json()
        status = task.get("status")
        progress = int(task.get("progress", 0) or 0)
        if status != last_status or progress != last_progress:
            queue = task.get("preceding_tasks", 0)
            elapsed = time.perf_counter() - start
            print(f"   [{label}] t+{elapsed:5.1f}s  status={status:<11}  progress={progress:3d}%  queued_ahead={queue}")
            last_status, last_progress = status, progress
        if status == "SUCCEEDED":
            return task
        if status in ("FAILED", "CANCELED"):
            err = task.get("task_error") or {}
            sys.exit(f"❌ {label} {status}: {err}")
        await asyncio.sleep(POLL_INTERVAL_S)
    sys.exit(f"❌ {label} timed out after {POLL_TIMEOUT_S:.0f}s (last seen: {last_status} {last_progress}%)")


async def _download(url: str, out_path: Path) -> int:
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.get(url, follow_redirects=True)
    if r.status_code != 200:
        raise RuntimeError(f"download HTTP {r.status_code}: {r.text[:200]}")
    if r.content[:4] != GLB_MAGIC:
        raise RuntimeError(f"not a GLB — first 4 bytes = {r.content[:4]!r}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(r.content)
    return len(r.content)


async def run(input_glb: Path, model_url: str, key: str, action_id: int | None, height: float) -> None:
    is_dummy = key == DUMMY_KEY
    print(f"🎯 Input GLB:  {input_glb}  ({input_glb.stat().st_size:,} bytes)")
    print(f"🌐 model_url:  {model_url}")
    print(f"🔑 API key:    {_digest(key)}{'  ⚠️  DUMMY MODE — no real GLB will be produced' if is_dummy else ''}")
    print(f"📐 Height:     {height}m")
    print(f"🎬 action_id:  {'(none — rigging only)' if action_id is None else action_id}")
    print()

    print("🔍 Verifying model_url is publicly reachable …")
    fetched = await _verify_url(model_url)
    print(f"✅ HEAD OK — Meshy will fetch {fetched:,} bytes")
    print()

    t_total = time.perf_counter()

    async with httpx.AsyncClient(timeout=60) as c:
        # ── 1. Rigging ────────────────────────────────────────────────
        print("⏳ POST /rigging …")
        t = time.perf_counter()
        rig_id = await _post(c, key, "/rigging", {"model_url": model_url, "height_meters": height})
        print(f"✅ rig_task_id = {rig_id}  ({time.perf_counter()-t:.1f}s)\n")

        print(f"⏳ Polling /rigging/{rig_id} …")
        rig_task = await _poll(c, key, f"/rigging/{rig_id}", "rig")
        rig_result = rig_task.get("result") or {}
        print(f"✅ rigging SUCCEEDED  (consumed {rig_task.get('consumed_credits', 0)} credits)")
        print(f"   rigged_character_glb_url: {rig_result.get('rigged_character_glb_url')}")
        basic = rig_result.get("basic_animations") or {}
        if basic:
            print(f"   basic_animations.walking_glb_url: {basic.get('walking_glb_url')}")
            print(f"   basic_animations.running_glb_url: {basic.get('running_glb_url')}")
        print()

        # ── 2. Animation (optional) ───────────────────────────────────
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if action_id is None:
            url_to_download = rig_result.get("rigged_character_glb_url")
            label = f"rigged_only_{ts}"
            anim_credits = 0
        else:
            print(f"⏳ POST /animations  (rig_task_id={rig_id}, action_id={action_id}) …")
            t = time.perf_counter()
            anim_id = await _post(c, key, "/animations", {"rig_task_id": rig_id, "action_id": action_id})
            print(f"✅ anim_task_id = {anim_id}  ({time.perf_counter()-t:.1f}s)\n")

            print(f"⏳ Polling /animations/{anim_id} …")
            anim_task = await _poll(c, key, f"/animations/{anim_id}", "anim")
            anim_result = anim_task.get("result") or {}
            anim_credits = anim_task.get("consumed_credits", 0)
            print(f"✅ animation SUCCEEDED  (consumed {anim_credits} credits)")
            print(f"   animation_glb_url: {anim_result.get('animation_glb_url')}\n")
            url_to_download = anim_result.get("animation_glb_url")
            label = f"anim_action{action_id}_{ts}"

        # ── 3. Download + mirror ──────────────────────────────────────
        if not url_to_download:
            sys.exit("❌ No download URL in task result")

        out_path = GLB_OUT_DIR / f"{label}.glb"
        print(f"⏳ Downloading → {out_path}")
        try:
            n = await _download(url_to_download, out_path)
        except RuntimeError as e:
            if is_dummy:
                print(f"⚠️  Download failed in DUMMY MODE: {e}")
                print(f"⚠️  This is EXPECTED — dummy key returns mock URLs. Plumbing verified through polling.")
                print(f"⚠️  Real key will produce a real downloadable GLB at this same step.")
                return
            sys.exit(f"❌ {e}")
        print(f"✅ Downloaded {n:,} bytes  (magic = {GLB_MAGIC!r} ✓)")
        print()

        rig_credits = rig_task.get("consumed_credits", 0) or 0
        print("🎉 END-TO-END MESHY TEST PASSED")
        print(f"   Total elapsed:  {time.perf_counter()-t_total:.1f}s")
        print(f"   Output GLB:     {out_path}")
        print(f"   Credits charged: rig={rig_credits} + anim={anim_credits} = {rig_credits + anim_credits}")
        print()
        print("View it:")
        print(f"   open {out_path}")
        print(f"   OR drag-drop into https://gltf.report or https://playcanvas.com/viewer")


async def run_retexture(
    input_glb: Path,
    model_url: str,
    image_style_url: str,
    key: str,
) -> None:
    """Test /retexture endpoint end-to-end. Mirrors run() shape."""
    is_dummy = key == DUMMY_KEY
    print(f"🎯 Input GLB:       {input_glb}  ({input_glb.stat().st_size:,} bytes)")
    print(f"🌐 model_url:       {model_url}")
    print(f"🖼️  image_style_url: {image_style_url}")
    print(f"🔑 API key:         {_digest(key)}{'  ⚠️  DUMMY MODE — no real GLB will be produced' if is_dummy else ''}")
    print(f"🤖 ai_model:        meshy-6")
    print(f"⚙️  flags:           enable_pbr=true, enable_original_uv=false, remove_lighting=true, hd_texture=true")
    print()

    print("🔍 Verifying URLs reachable …")
    glb_size = await _verify_url(model_url)
    print(f"✅ model_url HEAD OK — Meshy will fetch {glb_size:,} bytes")
    # Only verify image URL if it's our staged one (skip for arbitrary external URLs)
    if "ngrok" in image_style_url or "localhost" in image_style_url:
        img_size = await _verify_url(image_style_url)
        print(f"✅ image_style_url HEAD OK — {img_size:,} bytes")
    print()

    t_total = time.perf_counter()

    async with httpx.AsyncClient(timeout=60) as c:
        # ── 1. Retexture ──────────────────────────────────────────────
        print("⏳ POST /retexture …")
        t = time.perf_counter()
        body = {
            "model_url": model_url,
            "image_style_url": image_style_url,
            "ai_model": "meshy-6",
            "enable_pbr": True,
            "enable_original_uv": False,   # False = Meshy regenerates proper UV unwrap (web UI default)
            "remove_lighting": True,
            "hd_texture": True,            # 4K base color — Pro plan
            "target_formats": ["glb"],     # Only generate GLB, skip fbx/obj/usdz/stl (faster)
        }
        retex_id = await _post(c, key, "/retexture", body)
        print(f"✅ retex_task_id = {retex_id}  ({time.perf_counter()-t:.1f}s)\n")

        print(f"⏳ Polling /retexture/{retex_id} …")
        retex_task = await _poll(c, key, f"/retexture/{retex_id}", "retex")
        # model_urls is at TOP LEVEL of task (not under 'result') per Meshy docs
        model_urls = retex_task.get("model_urls") or {}
        print(f"✅ retexture SUCCEEDED  (consumed {retex_task.get('consumed_credits', 0)} credits)")
        print(f"   model_urls keys: {list(model_urls.keys())}")
        glb_url = model_urls.get("glb") or retex_task.get("model_url")
        print(f"   glb url: {glb_url}")
        print()

        # ── 2. Download ───────────────────────────────────────────────
        if not glb_url:
            if is_dummy:
                print("⚠️  No glb URL returned (expected in DUMMY MODE — model_urls empty)")
                print("🎉 END-TO-END RETEXTURE PLUMBING TEST PASSED (dummy mode)")
                print(f"   ✓ POST /retexture accepted  (request shape validated)")
                print(f"   ✓ Polled task to SUCCEEDED  (auth + polling logic confirmed)")
                print(f"   Total elapsed: {time.perf_counter()-t_total:.1f}s")
                return
            sys.exit("❌ No glb URL in retexture task result")

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = GLB_OUT_DIR / f"retex_{ts}.glb"
        print(f"⏳ Downloading → {out_path}")
        try:
            n = await _download(glb_url, out_path)
        except RuntimeError as e:
            if is_dummy:
                print(f"⚠️  Download failed in DUMMY MODE: {e}")
                print(f"⚠️  This is EXPECTED — dummy key returns mock URLs. Plumbing verified through polling.")
                print(f"🎉 END-TO-END RETEXTURE PLUMBING TEST PASSED (dummy mode)")
                print(f"   Total elapsed:  {time.perf_counter()-t_total:.1f}s")
                return
            sys.exit(f"❌ {e}")
        print(f"✅ Downloaded {n:,} bytes  (magic = {GLB_MAGIC!r} ✓)")
        print()

        credits = retex_task.get("consumed_credits", 0) or 0
        print("🎉 END-TO-END RETEXTURE TEST PASSED")
        print(f"   Total elapsed: {time.perf_counter()-t_total:.1f}s")
        print(f"   Output GLB:    {out_path}")
        print(f"   Credits:       {credits}")
        print()
        print("View it:")
        print(f"   open {out_path}")
        print(f"   OR drag-drop into https://gltf.report")


def _resolve_image_style_url(image_path: str | None, override_url: str | None) -> str:
    """Stage a portrait image to AVATARS_DIR and return its public ngrok URL.

    If override_url given, return it directly (no staging).
    """
    if override_url:
        return override_url
    if not image_path:
        sys.exit(
            "❌ --retexture requires --image-style <path> or --image-style-url <URL>\n"
            "   Try: --image-style tests/inputs/v3_apose_test_portrait_b.png"
        )
    p = Path(image_path).resolve()
    if not p.exists():
        sys.exit(f"❌ image not found: {p}")
    host = os.getenv("MESHY_PUBLIC_HOST", "").strip()
    if not host:
        sys.exit(
            "❌ Need MESHY_PUBLIC_HOST set (e.g. grinning-flyable-golf.ngrok-free.dev)\n"
            "   OR pass --image-style-url <direct URL> to skip staging."
        )
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    staged = AVATARS_DIR / f"meshy_style_{ts}{p.suffix}"
    shutil.copy2(p, staged)
    print(f"🖼️  Staged image → {staged}")
    scheme = "http" if host.startswith(("localhost", "127.")) else "https"
    return f"{scheme}://{host}/avatars/{staged.name}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Meshy rigging + animation manual test")
    p.add_argument("glb_path", nargs="?", help="Path to input TRELLIS GLB (default: latest manual_test_*.glb)")
    p.add_argument("--action-id", type=int, default=0, help="Animation library ID (default 0 = Idle)")
    p.add_argument("--no-animation", action="store_true", help="Skip /animations call; download rigged-only GLB")
    p.add_argument("--model-url", help="Override staged URL with an externally-hosted model URL")
    p.add_argument("--height", type=float, default=DEFAULT_HEIGHT_M)
    p.add_argument("--retexture", action="store_true",
                   help="Test /retexture endpoint instead of /rigging+/animations")
    p.add_argument("--image-style", help="Path to portrait image to use as image_style_url (--retexture only)")
    p.add_argument("--image-style-url", help="Direct URL for image_style_url (skips staging)")
    return p.parse_args()


def _resolve_input(arg: str | None) -> Path:
    if arg:
        p = Path(arg).resolve()
    else:
        glbs = sorted(
            (REPO_ROOT / "tests" / "outputs" / "runpod_glbs").glob("manual_test_*.glb"),
            key=lambda x: x.stat().st_mtime,
        )
        if not glbs:
            sys.exit("❌ No glb_path given and no manual_test_*.glb in tests/outputs/runpod_glbs/")
        p = glbs[-1]
        print(f"ℹ️  No glb_path given — using latest: {p.name}")
    if not p.exists():
        sys.exit(f"❌ Input GLB not found: {p}")
    if p.read_bytes()[:4] != GLB_MAGIC:
        sys.exit(f"❌ Not a GLB (magic mismatch): {p}")
    return p


def _resolve_model_url(input_glb: Path, override: str | None) -> str:
    if override:
        return override
    host = os.getenv("MESHY_PUBLIC_HOST", "").strip()
    if not host:
        sys.exit(
            "❌ Need a public URL for Meshy to fetch the GLB.\n"
            "   Set MESHY_PUBLIC_HOST in .env (e.g. grinning-flyable-golf.ngrok-free.dev)\n"
            "   OR pass --model-url <URL> directly."
        )
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    staged = AVATARS_DIR / f"meshy_input_{ts}.glb"
    shutil.copy2(input_glb, staged)
    print(f"📦 Staged input → {staged}")
    scheme = "http" if host.startswith(("localhost", "127.")) else "https"
    return f"{scheme}://{host}/avatars/{staged.name}"


def main() -> None:
    args = parse_args()
    key = os.getenv("MESHY_API_KEY", "").strip()
    if not key:
        print("⚠️  MESHY_API_KEY not set — using dummy key. Plumbing-only test.")
        key = DUMMY_KEY
    input_glb = _resolve_input(args.glb_path)
    model_url = _resolve_model_url(input_glb, args.model_url)
    if args.retexture:
        image_style_url = _resolve_image_style_url(args.image_style, args.image_style_url)
        asyncio.run(run_retexture(input_glb, model_url, image_style_url, key))
        return
    action_id = None if args.no_animation else args.action_id
    asyncio.run(run(input_glb, model_url, key, action_id, args.height))


if __name__ == "__main__":
    main()
