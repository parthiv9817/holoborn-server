"""No-network contract tests for Meshy API request/response handling.

Run:
    .venv/bin/python tests/scripts/test_meshy_client_contracts.py
"""
from __future__ import annotations

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
from app.services.meshy_client import build_retexture_body, extract_glb_url  # noqa: E402


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


def run() -> int:
    tests = [
        test_retexture_body_includes_quality_flags,
        test_retexture_extracts_top_level_glb_url,
        test_rigging_body_uses_model_url_and_height,
        test_animation_body_uses_rig_task_and_action,
        test_extract_rigging_urls,
        test_extract_animation_glb_url,
    ]
    for test in tests:
        test()
        print(f"  ✓ {test.__name__}")
    print(f"\n  PASS — {len(tests)} Meshy contract cases green")
    return 0


if __name__ == "__main__":
    sys.exit(run())
