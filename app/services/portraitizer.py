import base64
import io
import time

from openai import OpenAI

from app.config import settings


PORTRAIT_PROMPT_V1 = (
    "Transform this photo into a clean professional portrait. "
    "Studio lighting with soft diffused front light. "
    "Plain white background, no other objects or environment visible. "
    "Preserve the person's exact face, facial hair, skin tone, "
    "hairstyle, clothing, accessories, body pose, and proportions. "
    "Full body visible from head to feet. "
    "Do not change, stylize, or idealize any facial features. "
    "Photorealistic output, not illustrated or painted."
)

PORTRAIT_PROMPT_V2 = (
    "This is a candid documentary photo of a real person, not a portrait session. "
    "Make ONLY ONE change: replace the background with a plain seamless white "
    "backdrop (RGB 245,245,245 to pure white). "
    "Do not change the person's face, facial features, facial hair, eye shape, "
    "nose, jaw, skin tone, skin texture, hairstyle, hair density, expression, "
    "clothing (including the lanyard with badge), accessories, body shape, body "
    "proportions, pose, hand position, or footwear in any way. Preserve their "
    "exact likeness as it appears in the source image. "
    "Match the lighting direction, color temperature, and exposure of the original "
    "photo. Light the subject as if photographed with available indoor light — "
    "not flash, not studio strobe, not retouched headshot lighting. "
    "Keep the person's full body visible from head to feet, centered, eye-level "
    "framing, 35mm documentary lens feel. "
    "Style: honest unposed documentary photography. Real skin texture with visible "
    "pores and natural skin imperfections. Real fabric texture with visible weave. "
    "Natural shadow falloff. No glamorization. No heavy retouching. No idealization "
    "of features. Not illustrated, not painted, not stylized."
)

# V3 — A-pose conditioning prompt. Validated 2026-05-07: the V3 portrait fed to
# TRELLIS produced a riggable GLB that Meshy auto-rigged + animated cleanly with
# no wing-pants deformation. Identity drifts ~50% on the face under degraded
# inputs (dim Quest captures); use a brightened or burst-averaged input for
# better identity fidelity. See drafts/draft_prompt_2.md for the full evolution.
PORTRAIT_PROMPT_V3 = (
    "Generate a new full-body documentary photograph of the person from this "
    "image, standing in a clean A-pose for 3D scanning.\n\n"
    "Identity: same face, same eye shape and colour, same skin tone, same facial "
    "hair, same hairstyle and density, same age, neutral relaxed expression. "
    "Real skin texture with visible pores and natural asymmetry. Same body "
    "proportions and limb lengths.\n\n"
    "Clothing: preserve EVERY clothing item visible in the input photo exactly "
    "as it appears — shirt, pants or skirt, footwear, AND any accessory that "
    "is actually visible in the source image. DO NOT add, remove, invent, or "
    "modify any clothing or accessory. If an item (lanyard, badge, glasses, "
    "hat, watch, jewelry, jacket, scarf, bag, etc.) is NOT visible in the "
    "input image, DO NOT render it in the output. Preserve fabric weave and "
    "texture; do not flatten patterns into solid colour.\n\n"
    "Pose, limb by limb:\n"
    "- Body and head facing the camera directly.\n"
    "- Both arms extended approximately 30 to 40 degrees away from the torso, "
    "reaching toward the LEFT and RIGHT edges of the image. Arms NOT touching "
    "the ribs or hips. Palms facing the thighs, fingers relaxed and slightly "
    "curled.\n"
    "- Both feet placed shoulder-width apart on the floor, NOT touching each "
    "other, toes pointing forward toward the camera.\n"
    "- Both legs straight but not locked, knees facing forward.\n"
    "- Shoulders level, spine straight, weight even on both feet.\n"
    "- Full body visible from the top of the head to the toes of both feet.\n\n"
    "Background: plain seamless light-grey backdrop, RGB approximately "
    "240,240,240. Subject centred horizontally and vertically. Slight headroom "
    "above the head, slight floor visible below the feet.\n\n"
    "Lighting: soft diffuse front key light, gentle fill from both sides, even "
    "illumination across the body. No harsh shadows, no rim glow, no halo, no "
    "coloured gels. Match the natural skin tone of the input photo; do not warm "
    "or cool the colour temperature.\n\n"
    "Style: shot on Hasselblad X2D with a 50mm lens, eye-level, f/8. Honest "
    "documentary photograph, photorealistic. Real fabric texture, real skin "
    "texture, natural shadow falloff. No retouching, no jaw sharpening, no eye "
    "enlargement, no skin smoothing, no idealization. Not illustrated, not "
    "painted, not stylised, not anime, not cartoon.\n\n"
    "Do not add accessories, text, logos, or watermarks that are not present "
    "in the input image."
)

PORTRAIT_PROMPT = PORTRAIT_PROMPT_V3


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key or settings.openai_api_key == "replace-me":
            raise RuntimeError("OPENAI_API_KEY is not set in .env")
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def portraitize(image_bytes: bytes) -> bytes:
    if not image_bytes:
        raise ValueError("empty image bytes")

    client = _get_client()
    start = time.perf_counter()

    buf = io.BytesIO(image_bytes)
    buf.name = "input.jpg"

    response = client.images.edit(
        model=settings.gpt_image_model,
        image=buf,
        prompt=PORTRAIT_PROMPT,
        size="1024x1536",
        quality="high",
        input_fidelity="high",
    )

    if not response.data:
        raise RuntimeError("portraitizer: empty response from OpenAI")

    b64 = response.data[0].b64_json
    if not b64:
        raise RuntimeError("portraitizer: missing b64_json in response")

    portrait = base64.b64decode(b64)
    elapsed = time.perf_counter() - start
    print(f"[portraitizer] elapsed={elapsed:.2f}s bytes={len(portrait)}")
    return portrait
