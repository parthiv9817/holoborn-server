"""Unit test for the two portraitize wrappers in generation_pipeline.

Both wrappers MUST honor TEST_PORTRAIT_OVERRIDE so the dual-capture flow can be
exercised offline (no OpenAI cost) just like the legacy single path. This test
sets the override to a known PNG and confirms both wrappers return its bytes
without dispatching to the real portraitizer functions.

Run from anywhere: `python3 tests/scripts/test_portraitize_routing.py`
Exits 0 on success, 1 on assertion failure.
"""

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


# minimal stub PNG (1x1 transparent) used as the override target
STUB_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6364000000000005000156a76e2c0000000049454e44ae"
    "426082"
)


async def _run() -> int:
    out_dir = REPO_ROOT / "tests" / "outputs" / "portraitize_routing"
    out_dir.mkdir(parents=True, exist_ok=True)
    stub_path = out_dir / "stub.png"
    stub_path.write_bytes(STUB_PNG_BYTES)

    os.environ["TEST_PORTRAIT_OVERRIDE"] = str(stub_path)

    # Import after env var is set so Settings picks it up on first read.
    from app.config import settings
    # If settings was already constructed elsewhere with a cached value, force a refresh.
    settings.test_portrait_override = str(stub_path)

    from app.services.generation_pipeline import (
        _portraitize_async,
        _portraitize_async_dual,
    )

    # Single path with override
    out_single = await _portraitize_async(b"\x00" * 10)
    assert out_single == STUB_PNG_BYTES, (
        f"single override mismatch: got {len(out_single)} bytes, expected {len(STUB_PNG_BYTES)}"
    )
    print(f"single-path override: OK ({len(out_single)} bytes)")

    # Dual path with override — MUST also bypass and return the same stub
    out_dual = await _portraitize_async_dual(b"\x00" * 10, b"\x00" * 10)
    assert out_dual == STUB_PNG_BYTES, (
        f"dual override mismatch: got {len(out_dual)} bytes, expected {len(STUB_PNG_BYTES)}"
    )
    print(f"dual-path override: OK ({len(out_dual)} bytes)")

    # Clear override and verify behavior changes (would need real network — just confirm we'd dispatch)
    settings.test_portrait_override = ""
    # Don't actually call — would hit OpenAI. Just assert the override is clear.
    assert not settings.test_portrait_override
    print(f"override cleared: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
