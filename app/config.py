from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
AVATARS_DIR = RESULTS_DIR / "avatars"
ORIGINALS_DIR = RESULTS_DIR / "originals"
SCANS_DIR = RESULTS_DIR / "scans"


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

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    @property
    def runpod_run_url(self) -> str:
        return f"{self.gpu_server_url}/run"

    @property
    def runpod_status_url_base(self) -> str:
        return f"{self.gpu_server_url}/status"


settings = Settings()


def get_settings() -> Settings:
    return settings


for _d in (AVATARS_DIR, ORIGINALS_DIR, SCANS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
