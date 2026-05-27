"""Multi-view turnaround generator for Hunyuan3D-2mv input.

Takes a single clean front portrait (output of portraitize / portraitize_dual)
and generates a 2x2 turnaround grid via gpt-image-2 in ONE API call, then
splits the grid into 4 separate view images (front / left / back / right).

The Hunyuan endpoint downscales every input view to 512x512 internally (per
hy3dgen's MVImageProcessorV2), so we output a 1024x1024 grid → splits to four
512x512 tiles → sits exactly at the model's input resolution. No wasted detail.

Per the OpenAI cookbook prompting guide
(https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide):
  - gpt-image-2 does NOT use input_fidelity (high by default — passing it errors)
  - Use Change / Preserve / Constraints structure
  - Label each panel explicitly
  - Restate preserve list every call to reduce drift

Layout (locked — split coordinates depend on this exact arrangement):
    ┌───────────────┬───────────────┐
    │  FRONT  (TL)  │   LEFT  (TR)  │
    ├───────────────┼───────────────┤
    │  BACK   (BL)  │  RIGHT  (BR)  │
    └───────────────┴───────────────┘
"""
from __future__ import annotations

import base64
import io
import time

from PIL import Image
from openai import OpenAI

from app.config import settings


TURNAROUND_GRID_PROMPT = (
    "LAYOUT: a 1024x1024 image composed of exactly 4 equal-size square panels "
    "in a 2x2 grid, with a clean 8-pixel white gutter between panels. Each "
    "panel is a separate photograph of the same person from the reference "
    "image, from a different camera angle.\n\n"
    "Panel TOP-LEFT (front view): same person, body and head facing camera "
    "directly, full body, A-pose.\n"
    "Panel TOP-RIGHT (left profile, camera at 90 degrees to subject's left): "
    "full body, A-pose, side silhouette of body and head visible.\n"
    "Panel BOTTOM-LEFT (back view, camera 180 degrees behind subject): full "
    "body, A-pose, back of head and back of body visible; do not show the face.\n"
    "Panel BOTTOM-RIGHT (right profile, camera at 90 degrees to subject's "
    "right): full body, A-pose, opposite-side silhouette visible.\n\n"
    "CHANGE per panel: only the camera angle. Nothing else changes.\n\n"
    "KEEP IDENTICAL across all 4 panels:\n"
    "  identity, face, skin tone, facial hair, hairstyle and hair density, "
    "age, every clothing item visible in the reference (shirt, pants, "
    "footwear, accessories), fabric pattern and color, A-pose limb position "
    "(arms 30-40 degrees from torso reaching toward the panel edges, feet "
    "shoulder-width apart), body proportions, lighting (soft diffuse front "
    "key + gentle side fill), background (plain seamless light-grey RGB "
    "240,240,240).\n\n"
    "CONSTRAINTS:\n"
    "  No text, no labels, no panel numbers, no watermarks, no decorative "
    "borders. Gutter between panels must be uniform white space, not a colored "
    "stripe. Do not invent or remove any clothing or accessory. Photorealistic "
    "documentary photography, no stylization, no painting, no cartoon."
)


VIEW_LAYOUT = ("front", "left", "back", "right")  # TL, TR, BL, BR


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key or settings.openai_api_key == "replace-me":
            raise RuntimeError("OPENAI_API_KEY is not set in .env")
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def generate_grid_image(front_portrait_bytes: bytes) -> bytes:
    """Single gpt-image-2 call → returns raw 2x2 grid PNG bytes (1024x1024)."""
    if not front_portrait_bytes:
        raise ValueError("empty portrait bytes")

    client = _get_client()
    start = time.perf_counter()

    buf = io.BytesIO(front_portrait_bytes)
    buf.name = "front_portrait.png"

    # gpt-image-2: no input_fidelity (high by default — passing it errors).
    response = client.images.edit(
        model="gpt-image-2",
        image=buf,
        prompt=TURNAROUND_GRID_PROMPT,
        size="1024x1024",
        quality="high",
    )

    if not response.data:
        raise RuntimeError("view_synthesizer: empty response from OpenAI")
    b64 = response.data[0].b64_json
    if not b64:
        raise RuntimeError("view_synthesizer: missing b64_json in response")

    grid_png = base64.b64decode(b64)
    elapsed = time.perf_counter() - start
    print(
        f"[view_synthesizer] grid generated elapsed={elapsed:.2f}s "
        f"bytes={len(grid_png)}"
    )
    return grid_png


def split_grid(grid_png: bytes) -> dict[str, bytes]:
    """Split a 1024x1024 grid PNG into 4 quadrant tiles → {front, left, back, right}.

    If the model returns a slightly different size we resize to 1024x1024
    first so the crop coordinates are predictable.
    """
    img = Image.open(io.BytesIO(grid_png))
    if img.size != (1024, 1024):
        img = img.resize((1024, 1024), Image.LANCZOS)
    coords = [
        ("front", (0,   0,    512,  512)),
        ("left",  (512, 0,    1024, 512)),
        ("back",  (0,   512,  512,  1024)),
        ("right", (512, 512,  1024, 1024)),
    ]
    tiles: dict[str, bytes] = {}
    for name, box in coords:
        tile = img.crop(box)
        buf = io.BytesIO()
        tile.save(buf, format="PNG")
        tiles[name] = buf.getvalue()
    return tiles


def synthesize_views_grid(front_portrait_bytes: bytes) -> dict[str, bytes]:
    """Convenience: one call → {front, left, back, right} 512x512 PNGs.

    For debugging access to the intermediate grid, call generate_grid_image
    and split_grid separately instead.
    """
    grid = generate_grid_image(front_portrait_bytes)
    tiles = split_grid(grid)
    print(
        f"[view_synthesizer] split into 4 tiles: "
        f"{ {k: len(v) for k, v in tiles.items()} }"
    )
    return tiles
