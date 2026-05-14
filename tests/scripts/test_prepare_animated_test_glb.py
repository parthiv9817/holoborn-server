"""No-network tests for the animated test-GLB preparation script.

Run:
    .venv/bin/python tests/scripts/test_prepare_animated_test_glb.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_animated_test_glb import build_public_avatar_url  # noqa: E402


def test_public_avatar_url_adds_https_for_ngrok_host() -> None:
    url = build_public_avatar_url("grinning-flyable-golf.ngrok-free.dev", "input.glb")

    assert url == "https://grinning-flyable-golf.ngrok-free.dev/avatars/input.glb"


def test_public_avatar_url_keeps_localhost_http() -> None:
    url = build_public_avatar_url("localhost:8000", "input.glb")

    assert url == "http://localhost:8000/avatars/input.glb"


def test_public_avatar_url_preserves_explicit_scheme() -> None:
    url = build_public_avatar_url("https://example.com/base/", "input.glb")

    assert url == "https://example.com/base/avatars/input.glb"


def run() -> int:
    tests = [
        test_public_avatar_url_adds_https_for_ngrok_host,
        test_public_avatar_url_keeps_localhost_http,
        test_public_avatar_url_preserves_explicit_scheme,
    ]
    for test in tests:
        test()
        print(f"  ✓ {test.__name__}")
    print(f"\n  PASS — {len(tests)} prepare-script cases green")
    return 0


if __name__ == "__main__":
    sys.exit(run())
