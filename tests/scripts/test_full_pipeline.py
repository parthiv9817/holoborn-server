"""End-to-end backend integration smoke test.

Exercises the FULL real-key pipeline:
  Quest burst frames (5 JPGs) -> POST /generate-multiview
    -> burst averaging
    -> portraitizer (real OpenAI gpt-image-1.5)
    -> RunPod TRELLIS (real serverless endpoint)
    -> Meshy Retexture (real API)
    -> clean GLB delivered via GET /avatars/{task_id}.glb

Times every stage transition for bottleneck identification.

Prereqs:
  1. uvicorn running with real OPENAI_API_KEY + MESHY_API_KEY in .env
     (and TEST_PORTRAIT_OVERRIDE commented out)
  2. RunPod endpoint min_workers >= 1 (warm worker) so first call doesn't
     pay ~9 min cold-start penalty

Run:
    .venv/bin/python tests/scripts/test_full_pipeline.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://localhost:8000"
BURST_DIR = REPO_ROOT / "tests" / "inputs" / "burst_5frames_quest_20260504"
OUT_DIR = REPO_ROOT / "tests" / "outputs" / "full_pipeline"
POLL_INTERVAL_S = 3.0
TIMEOUT_S = 1800.0  # 30 min hard cap — accounts for cold-start (~9 min) on first request
GLB_MAGIC = b"glTF"


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def main() -> None:
    # ── 0. Pre-flight ─────────────────────────────────────────────────
    print(f"[{_ts()}] Pre-flight checks...")
    frames = sorted(BURST_DIR.glob("frame_*.jpg"))
    if len(frames) != 5:
        sys.exit(f"❌ expected 5 frames in {BURST_DIR}, got {len(frames)}")
    print(f"   ✓ Found {len(frames)} burst frames")

    with httpx.Client(timeout=10) as c:
        try:
            r = c.get(f"{BASE_URL}/health")
            print(f"   ✓ /health → {r.status_code} {r.json()}")
        except Exception as e:
            sys.exit(f"❌ /health unreachable: {e}\n   Is uvicorn running on :8000?")

    # ── 1. POST burst ─────────────────────────────────────────────────
    print(f"\n[{_ts()}] POST /generate-multiview (5 burst frames)...")
    files = []
    for i, p in enumerate(frames):
        files.append((f"frame_{i}", (p.name, p.read_bytes(), "image/jpeg")))
    metadata = (
        '[{"index":0,"angle":0.0},{"index":1,"angle":0.0},'
        '{"index":2,"angle":0.0},{"index":3,"angle":0.0},{"index":4,"angle":0.0}]'
    )
    files.append(("metadata", (None, metadata, "application/json")))

    t_submit = time.perf_counter()
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{BASE_URL}/generate-multiview", files=files)
    submit_elapsed = time.perf_counter() - t_submit
    if r.status_code >= 400:
        sys.exit(f"❌ POST /generate-multiview → HTTP {r.status_code}: {r.text}")
    body = r.json()
    task_id = body.get("task_id")
    if not task_id:
        sys.exit(f"❌ no task_id in response: {body}")
    print(f"   ✓ task_id = {task_id}  (submit {submit_elapsed:.2f}s)")

    # ── 2. Poll status with timing ────────────────────────────────────
    print(f"\n[{_ts()}] Polling /generate/{task_id}/status every {POLL_INTERVAL_S}s...\n")
    start = time.perf_counter()
    last_status: str | None = None
    last_progress = -1
    stage_first_seen: dict[str, float] = {}

    while time.perf_counter() - start < TIMEOUT_S:
        elapsed = time.perf_counter() - start
        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(f"{BASE_URL}/generate/{task_id}/status")
        except Exception as e:
            print(f"   [{_ts()}] (+{elapsed:5.1f}s) poll error: {e}")
            time.sleep(POLL_INTERVAL_S)
            continue

        if r.status_code >= 400:
            print(f"   [{_ts()}] (+{elapsed:5.1f}s) status HTTP {r.status_code}: {r.text[:200]}")
            time.sleep(POLL_INTERVAL_S)
            continue

        data = r.json()
        status = data.get("status", "?")
        progress = int(data.get("progress", 0) or 0)
        msg = data.get("message", "")

        if status != last_status:
            stage_first_seen[status] = elapsed
            duration_prev = ""
            if last_status is not None:
                prev_elapsed = stage_first_seen.get(last_status, 0)
                duration_prev = f"  [{last_status} took {elapsed - prev_elapsed:5.1f}s]"
            print(f"   [{_ts()}] (+{elapsed:6.1f}s) status={status:<14} progress={progress:3d}%{duration_prev}")
            if msg:
                print(f"            message: {msg}")
            last_status = status
            last_progress = progress
        elif progress != last_progress and progress > 0:
            print(f"   [{_ts()}] (+{elapsed:6.1f}s)                       progress={progress:3d}%")
            last_progress = progress

        if status == "complete":
            total_elapsed = time.perf_counter() - start
            print(f"\n=========================================================")
            print(f"  ✓ PIPELINE COMPLETE — total {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
            print(f"=========================================================")
            print(f"\n  Stage timings (first-seen → next stage):")
            stages_ordered = sorted(stage_first_seen.items(), key=lambda kv: kv[1])
            for i, (stage, t) in enumerate(stages_ordered):
                next_t = stages_ordered[i + 1][1] if i + 1 < len(stages_ordered) else total_elapsed
                dur = next_t - t
                print(f"    {stage:<14}  +{t:6.1f}s  duration {dur:6.1f}s ({dur/60:.1f} min)")

            # Download GLB
            glb_url = data.get("glb_url")
            if glb_url:
                full_url = f"{BASE_URL}{glb_url}" if glb_url.startswith("/") else glb_url
                print(f"\n[{_ts()}] Downloading GLB from {full_url}")
                t_dl = time.perf_counter()
                with httpx.Client(timeout=120) as c:
                    rg = c.get(full_url)
                dl_elapsed = time.perf_counter() - t_dl
                if rg.status_code != 200:
                    sys.exit(f"❌ GLB download HTTP {rg.status_code}")
                content = rg.content
                if content[:4] != GLB_MAGIC:
                    sys.exit(f"❌ Not a GLB — first 4 bytes = {content[:4]!r}")
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                out_path = OUT_DIR / f"{task_id}.glb"
                out_path.write_bytes(content)
                print(f"   ✓ {len(content):,} bytes, magic={GLB_MAGIC!r} ✓ ({dl_elapsed:.2f}s)")
                print(f"   ✓ Saved → {out_path}")
                print(f"\n   View with: open {out_path}")
                print(f"   OR drag-drop into https://gltf.report")
            return

        if status == "failed":
            print(f"\n=== ❌ PIPELINE FAILED ===")
            print(f"   message: {msg}")
            print(f"   full response: {data}")
            sys.exit(1)

        time.sleep(POLL_INTERVAL_S)

    sys.exit(f"❌ Timed out after {TIMEOUT_S}s (last status: {last_status})")


if __name__ == "__main__":
    main()
