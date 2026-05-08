"""Manual RunPod end-to-end test — feed any portrait image to GPU pipeline + download GLB.

Bypasses OpenAI portraitizer step. Uses the same runpod_client.py production code path.

Usage:
    source .venv/bin/activate
    python tests/scripts/test_runpod_manual.py path/to/portrait.png
    # with a TRELLIS preset (defined in app/config.TRELLIS_PRESETS):
    python tests/scripts/test_runpod_manual.py path/to/portrait.png demo_premium
    # with the burst-averaged fixture as input:
    python tests/scripts/test_runpod_manual.py tests/outputs/burst_average/averaged.jpg

Default output: tests/outputs/runpod_glbs/manual_test_<preset>_<timestamp>.glb
"""
from __future__ import annotations

import asyncio
import base64
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.config import TRELLIS_PRESETS  # noqa: E402
from app.services.runpod_client import (  # noqa: E402
    GlbDownloadError,
    RunpodJobError,
    download_glb,
    poll_until_complete,
    submit_job,
)


DEFAULT_INPUT = REPO_ROOT / "tests" / "outputs" / "burst_average" / "averaged.jpg"
GLB_OUT_DIR = REPO_ROOT / "tests" / "outputs" / "runpod_glbs"


async def run(input_path: Path, preset_name: str | None) -> None:
    if not input_path.exists():
        sys.exit(f"❌ Input file not found: {input_path}")

    preset_kwargs: dict[str, float | int] = {}
    preset_label = "default"
    if preset_name:
        if preset_name not in TRELLIS_PRESETS:
            sys.exit(
                f"❌ Unknown preset '{preset_name}'. "
                f"Available: {list(TRELLIS_PRESETS.keys())}"
            )
        preset_kwargs = dict(TRELLIS_PRESETS[preset_name])
        preset_label = preset_name

    img_bytes = input_path.read_bytes()
    print(f"📷 Input: {input_path}  ({len(img_bytes):,} bytes)")
    print(f"   First 4 bytes: {img_bytes[:4]!r}")
    print(f"🎛️  Preset: {preset_label}")
    if preset_kwargs:
        for k, v in preset_kwargs.items():
            print(f"     {k} = {v}")

    image_b64 = base64.b64encode(img_bytes).decode("ascii")
    print(f"   Base64 length: {len(image_b64):,} chars")

    print()
    print("⏳ Submitting RunPod job ...")
    t0 = time.perf_counter()
    job_id = await submit_job(image_b64, **preset_kwargs)
    print(f"✅ Job submitted: {job_id}  (took {time.perf_counter()-t0:.2f}s)")

    print()
    print("⏳ Polling for completion (every 5s, 10-min cap) ...")
    poll_start = time.perf_counter()
    try:
        output = await poll_until_complete(job_id)
    except (RunpodJobError, TimeoutError) as e:
        sys.exit(f"❌ Job did not complete: {e}")
    elapsed = time.perf_counter() - poll_start
    print(f"✅ Job COMPLETED in {elapsed:.1f}s")
    print(f"   Output keys: {list(output.keys())}")
    print(f"   Output: {output}")

    glb_volume_path = output.get("glb_volume_path")
    if not glb_volume_path:
        sys.exit(f"❌ No glb_volume_path in output. Full output: {output}")

    GLB_OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    local_glb = GLB_OUT_DIR / f"manual_test_{preset_label}_{ts}.glb"
    print()
    print(f"⏳ Downloading GLB from S3 ({glb_volume_path}) → {local_glb}")
    t1 = time.perf_counter()
    try:
        size = await download_glb(glb_volume_path, local_glb)
    except GlbDownloadError as e:
        sys.exit(f"❌ GLB download/validation failed: {e}")
    print(f"✅ GLB downloaded in {time.perf_counter()-t1:.1f}s")
    print(f"   Size: {size:,} bytes")
    print(f"   Path: {local_glb}")
    print(f"   Magic bytes verified: starts with b'glTF' ✅")

    print()
    print("🎉 END-TO-END RUNPOD TEST PASSED")
    print(f"   Total elapsed: {time.perf_counter()-t0:.1f}s")
    print()
    print(f"View the GLB:")
    print(f"   open {local_glb}")
    print(f"   OR drag-drop into https://gltf-viewer.donmccurdy.com/")


def main() -> None:
    input_arg = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_INPUT)
    preset_arg = sys.argv[2] if len(sys.argv) > 2 else None
    input_path = Path(input_arg).resolve()
    asyncio.run(run(input_path, preset_arg))


if __name__ == "__main__":
    main()
