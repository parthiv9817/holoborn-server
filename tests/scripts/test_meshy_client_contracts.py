"""No-network contract tests for Meshy API request/response handling.

Run:
    .venv/bin/python tests/scripts/test_meshy_client_contracts.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.services.meshy_animation_client import (  # noqa: E402
    build_animation_body,
    build_rigging_body,
    extract_animation_glb_url,
    extract_basic_animation_url,
    extract_rigged_glb_url,
)
from app.services.meshy_client import (  # noqa: E402
    MeshyJobError,
    MeshyTransientError,
    build_retexture_body,
    extract_glb_url,
    is_transient_error,
    run_with_transient_retry,
)


def test_retexture_body_includes_quality_flags() -> None:
    body = build_retexture_body(
        model_url="https://example.com/model.glb",
        image_style_url="https://example.com/style.png",
        ai_model="meshy-6",
        enable_pbr=True,
        enable_original_uv=False,
        remove_lighting=True,
        hd_texture=True,
        target_formats=["glb"],
    )

    assert body["model_url"] == "https://example.com/model.glb"
    assert body["image_style_url"] == "https://example.com/style.png"
    assert body["enable_original_uv"] is False
    assert body["target_formats"] == ["glb"]


def test_retexture_extracts_top_level_glb_url() -> None:
    task = {"model_urls": {"glb": "https://assets.meshy.ai/model.glb"}}

    assert extract_glb_url(task) == "https://assets.meshy.ai/model.glb"


def test_rigging_body_uses_model_url_and_height() -> None:
    body = build_rigging_body("https://example.com/model.glb", height_meters=1.7)

    assert body == {
        "model_url": "https://example.com/model.glb",
        "height_meters": 1.7,
    }


def test_animation_body_uses_rig_task_and_action() -> None:
    body = build_animation_body("rig-task-id", action_id=0)

    assert body == {"rig_task_id": "rig-task-id", "action_id": 0}


def test_extract_rigging_urls() -> None:
    task = {
        "result": {
            "rigged_character_glb_url": "https://assets.meshy.ai/rigged.glb",
            "basic_animations": {
                "walking_glb_url": "https://assets.meshy.ai/walk.glb",
            },
        }
    }

    assert extract_rigged_glb_url(task) == "https://assets.meshy.ai/rigged.glb"
    assert extract_basic_animation_url(task, "walking") == "https://assets.meshy.ai/walk.glb"


def test_extract_animation_glb_url() -> None:
    task = {"result": {"animation_glb_url": "https://assets.meshy.ai/idle.glb"}}

    assert extract_animation_glb_url(task) == "https://assets.meshy.ai/idle.glb"


def test_is_transient_error_only_for_service_unavailable() -> None:
    # The exact shape Meshy returned on 2026-05-23.
    assert is_transient_error(
        {"type": "service_unavailable",
         "message": "The generation service is temporarily unavailable. Please retry."}
    ) is True
    # Message-only fallback (type missing).
    assert is_transient_error({"message": "Service temporarily unavailable"}) is True
    # String form.
    assert is_transient_error("service_unavailable: retry") is True
    # Hard errors must NOT be classified transient (would loop forever).
    assert is_transient_error({"type": "internal_error", "message": "bad input"}) is False
    assert is_transient_error("invalid model_url 404") is False
    assert is_transient_error(None) is False


def test_retry_recovers_after_transient_blips() -> None:
    calls = {"submit": 0, "poll": 0}
    submitted: list[str] = []

    async def fake_submit() -> str:
        calls["submit"] += 1
        return f"task-{calls['submit']}"

    async def fake_poll(task_id: str) -> dict:
        calls["poll"] += 1
        if calls["poll"] < 3:
            raise MeshyTransientError(f"{task_id} service_unavailable")
        return {"id": task_id, "status": "SUCCEEDED"}

    result = asyncio.run(
        run_with_transient_retry(
            fake_submit, fake_poll,
            label="retexture", max_attempts=3, backoff_s=0,
            on_submit=submitted.append,
        )
    )
    assert result["status"] == "SUCCEEDED"
    assert calls["submit"] == 3            # a fresh submit per retry
    assert submitted == ["task-1", "task-2", "task-3"]


def test_retry_does_not_swallow_hard_errors() -> None:
    calls = {"submit": 0}

    async def fake_submit() -> str:
        calls["submit"] += 1
        return "task"

    async def fake_poll(task_id: str) -> dict:
        raise MeshyJobError("hard failure — bad input")

    raised = False
    try:
        asyncio.run(
            run_with_transient_retry(
                fake_submit, fake_poll, label="retexture", max_attempts=3, backoff_s=0,
            )
        )
    except MeshyJobError as e:
        raised = True
        assert not isinstance(e, MeshyTransientError)
    assert raised
    assert calls["submit"] == 1            # non-transient → no retry


def test_retry_exhausts_then_raises_transient() -> None:
    calls = {"submit": 0}

    async def fake_submit() -> str:
        calls["submit"] += 1
        return "task"

    async def fake_poll(task_id: str) -> dict:
        raise MeshyTransientError("still unavailable")

    raised = False
    try:
        asyncio.run(
            run_with_transient_retry(
                fake_submit, fake_poll, label="rigging", max_attempts=3, backoff_s=0,
            )
        )
    except MeshyTransientError:
        raised = True
    assert raised
    assert calls["submit"] == 3            # tried exactly max_attempts times


def run() -> int:
    tests = [
        test_retexture_body_includes_quality_flags,
        test_retexture_extracts_top_level_glb_url,
        test_rigging_body_uses_model_url_and_height,
        test_animation_body_uses_rig_task_and_action,
        test_extract_rigging_urls,
        test_extract_animation_glb_url,
        test_is_transient_error_only_for_service_unavailable,
        test_retry_recovers_after_transient_blips,
        test_retry_does_not_swallow_hard_errors,
        test_retry_exhausts_then_raises_transient,
    ]
    for test in tests:
        test()
        print(f"  ✓ {test.__name__}")
    print(f"\n  PASS — {len(tests)} Meshy contract cases green")
    return 0


if __name__ == "__main__":
    sys.exit(run())
