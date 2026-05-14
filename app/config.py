from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
AVATARS_DIR = RESULTS_DIR / "avatars"
ORIGINALS_DIR = RESULTS_DIR / "originals"
SCANS_DIR = RESULTS_DIR / "scans"
QUEST_TEST_UPLOADS_DIR = RESULTS_DIR / "quest_test_uploads"


# TRELLIS sampler presets — sent to GPU handler as input-dict overrides.
# `fast` matches the GPU handler's hardcoded defaults (validated 2026-05-07,
# produced the 28.3MB GLB that rigged cleanly on Meshy).
# `demo_premium` is the locked tune from the 2026-05-06 second-opinion brief,
# tuned for organic humans per fal.ai parameter guide + TRELLIS issue #92.
TRELLIS_PRESETS: dict[str, dict[str, float | int]] = {
    "fast": {
        "sparse_struct_guidance": 8.0,
        "sparse_struct_steps": 12,
        "shape_slat_guidance": 8.0,
        "shape_slat_steps": 12,
        "tex_slat_guidance": 1.0,
        "tex_slat_steps": 12,
        "decimation": 50000,
    },
    "demo_premium": {
        "sparse_struct_guidance": 6.5,
        "sparse_struct_steps": 18,
        "shape_slat_guidance": 4.75,
        "shape_slat_steps": 18,
        "tex_slat_guidance": 3.0,
        "tex_slat_steps": 18,
        "decimation": 200000,
    },
    # demo_max: pushes guidance + steps to fal.ai range endpoints, keeps decimation
    # at Quest-safe 200k. ~22% more compute than demo_premium. No on-device perf risk.
    "demo_max": {
        "sparse_struct_guidance": 7.0,
        "sparse_struct_steps": 22,
        "shape_slat_guidance": 4.0,
        "shape_slat_steps": 22,
        "tex_slat_guidance": 3.5,
        "tex_slat_steps": 22,
        "decimation": 200000,
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str = ""
    gpt_image_model: str = "gpt-image-1.5"

    runpod_api_key: str = ""
    runpod_endpoint_id: str = "pz2c4wvo2rcdw9"
    gpu_server_url: str = "https://api.runpod.ai/v2/pz2c4wvo2rcdw9"

    runpod_s3_access_key: str = ""
    runpod_s3_secret_key: str = ""
    runpod_s3_endpoint: str = ""
    runpod_s3_bucket: str = ""
    runpod_s3_region: str = ""
    runpod_s3_keep_after_download: bool = False

    runpod_poll_interval_s: float = 5.0
    runpod_poll_timeout_s: float = 600.0

    # Meshy API (Retexture / Rigging / Animation endpoints).
    # When meshy_api_key is empty, meshy_client falls back to the dummy test key
    # `msy_dummy_api_key_for_test_mode_12345678` which returns mock responses.
    # meshy_public_host is the ngrok host that serves staged GLBs + portraits
    # back to Meshy (e.g. "grinning-flyable-golf.ngrok-free.dev").
    meshy_api_key: str = ""
    meshy_base_url: str = "https://api.meshy.ai/openapi/v1"
    meshy_public_host: str = ""
    meshy_poll_interval_s: float = 3.0
    meshy_poll_timeout_s: float = 600.0

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    quest_test_mode: bool = True

    # Test-mode bypasses for the spawn ritual demo while OpenAI billing is hard-limited.
    test_portrait_override: str = ""   # path to a pre-cached portrait; skips OpenAI when set
    test_portrait_delay_s: float = 0.0  # cinematic sleep before runpod submit (gives P2a vortex its window)

    @property
    def runpod_run_url(self) -> str:
        return f"{self.gpu_server_url}/run"

    @property
    def runpod_status_url_base(self) -> str:
        return f"{self.gpu_server_url}/status"


settings = Settings()


def get_settings() -> Settings:
    return settings


for _d in (AVATARS_DIR, ORIGINALS_DIR, SCANS_DIR, QUEST_TEST_UPLOADS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
