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
    )

    openai_api_key: str = ""
    runpod_api_key: str = ""
    runpod_endpoint_id: str = "pz2c4wvo2rcdw9"
    gpu_server_url: str = "https://api.runpod.ai/v2/pz2c4wvo2rcdw9"

    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def runpod_run_url(self) -> str:
        return f"{self.gpu_server_url}/run"

    @property
    def runpod_status_url_base(self) -> str:
        return f"{self.gpu_server_url}/status"


settings = Settings()

for _d in (AVATARS_DIR, ORIGINALS_DIR, SCANS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
