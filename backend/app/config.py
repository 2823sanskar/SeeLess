from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "SeeLess"
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./seeless.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    STORAGE_DIR: str = "../storage"
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_VIDEO_DURATION_SECONDS: int = 600

    # Visual Intelligence & Description Generation (Gemini)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"

    # Gnani AI Audio Services (Exclusive AI STT & TTS)
    GNANI_API_KEY: str = ""
    GNANI_STT_ENDPOINT: str = "https://api.vachana.ai/stt/v3"
    GNANI_TTS_ENDPOINT: str = "https://api.vachana.ai/api/v1/tts/inference"
    GNANI_STT_MODEL: str = "prisma-v3.0"
    GNANI_TTS_MODEL: str = "timbre-v2.5"
    GNANI_VOICE_ID: str = "Nalini"
    GNANI_LANGUAGE_CODE: str = "en-IN"

settings = Settings()

# Resolve absolute path for storage relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_PATH = (REPO_ROOT / "storage").resolve()
STORAGE_PATH.mkdir(parents=True, exist_ok=True)
