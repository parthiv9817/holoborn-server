import base64
import io
import time

from openai import OpenAI

from app.config import settings


PORTRAIT_PROMPT = (
    "Transform this photo into a clean professional portrait. "
    "Studio lighting with soft diffused front light. "
    "Plain white background, no other objects or environment visible. "
    "Preserve the person's exact face, facial hair, skin tone, "
    "hairstyle, clothing, accessories, body pose, and proportions. "
    "Full body visible from head to feet. "
    "Do not change, stylize, or idealize any facial features. "
    "Photorealistic output, not illustrated or painted."
)


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
        model="gpt-image-1.5",
        image=buf,
        prompt=PORTRAIT_PROMPT,
        size="1024x1536",
        quality="high",
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
