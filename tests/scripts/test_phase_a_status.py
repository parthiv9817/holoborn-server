"""Verification script for Phase A — pipeline-stage status emissions.

Exercises the /generate/{task_id}/status route across all 7 status string values
via FastAPI's TestClient. No uvicorn, no full pipeline run — just the route logic
with an injected fake task_record.

Run:
    QUEST_TEST_MODE=false python3 tests/scripts/test_phase_a_status.py

Expected: all 7 cases green (✓), no AssertionError, exit code 0.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Force quest_test_mode=False so the route exercises real status logic, not the
# early-return branch that always says "failed" in test mode.
os.environ["QUEST_TEST_MODE"] = "false"

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


CASES = [
    # (task_record, expected_status_in_response, expected_progress, label)
    ({"status": "portraitizing"}, "portraitizing", 0, "early portraitizer stage"),
    (
        {"status": "generating", "last_runpod_status": "IN_QUEUE"},
        "generating", 25, "RunPod queued",
    ),
    (
        {"status": "generating", "last_runpod_status": "IN_PROGRESS"},
        "generating", 60, "RunPod running",
    ),
    (
        {"status": "generating", "last_runpod_status": "COMPLETED"},
        "generating", 100, "RunPod done, GLB downloading",
    ),
    ({"status": "retexturing"}, "retexturing", 0, "Meshy retexture (de-light) in flight"),
    ({"status": "rigging"}, "rigging", 0, "Meshy rigging (future)"),
    ({"status": "animating"}, "animating", 0, "Meshy animating (future)"),
    ({"status": "failed", "error": "test failure"}, "failed", 0, "failed task"),
    ({"status": "complete"}, "complete", 100, "complete (no GLB on disk → falls through to processing in route logic)"),
    # legacy fallback
    ({"status": "processing", "last_runpod_status": "PENDING"}, "processing", 10, "legacy processing"),
]


def run() -> int:
    client = TestClient(app)
    # Manually populate state since lifespan startup creates the dict but we need
    # custom records for testing.
    app.state.generation_tasks = {}

    failed = 0
    for i, (record, expect_status, expect_progress, label) in enumerate(CASES):
        task_id = f"phase-a-test-{i:02d}"
        app.state.generation_tasks[task_id] = record

        r = client.get(f"/generate/{task_id}/status")
        if r.status_code != 200:
            print(f"  ✗ {label:<48}  HTTP {r.status_code}: {r.text}")
            failed += 1
            continue

        body = r.json()
        got_status = body.get("status")
        got_progress = body.get("progress")

        # Special case: "complete" without an actual GLB on disk falls through
        # to legacy "processing" branch (because glb_path.exists() is False).
        # Document this expectation.
        if record["status"] == "complete" and expect_status == "complete":
            # We expect the route to NOT return "complete" here because
            # AVATARS_DIR/{task_id}.glb doesn't exist on disk during this test.
            if got_status == "processing":
                print(f"  ✓ {label:<48}  status=processing (correct — no glb on disk)")
                continue

        if got_status == expect_status and got_progress == expect_progress:
            print(f"  ✓ {label:<48}  status={got_status} progress={got_progress}")
        else:
            print(f"  ✗ {label:<48}  expected status={expect_status} progress={expect_progress}, got status={got_status} progress={got_progress}")
            failed += 1

    print()
    if failed == 0:
        print(f"  PASS — {len(CASES)} cases green")
        return 0
    print(f"  FAIL — {failed}/{len(CASES)} cases failed")
    return 1


if __name__ == "__main__":
    sys.exit(run())
