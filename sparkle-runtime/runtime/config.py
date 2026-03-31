import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = os.environ.get("SUPABASE_URL", "")
    supabase_key: str = os.environ.get("SUPABASE_KEY", "")

    # Anthropic
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

    # Groq (Whisper transcription)
    groq_api_key: str = os.environ.get("GROQ_API_KEY", "")

    # Z-API
    zapi_base_url: str = os.environ.get("ZAPI_BASE_URL", "")
    zapi_instance_id: str = os.environ.get("ZAPI_INSTANCE_ID", "")
    zapi_token: str = os.environ.get("ZAPI_TOKEN", "")
    zapi_client_token: str = os.environ.get("ZAPI_CLIENT_TOKEN", "")

    # Runtime
    runtime_version: str = "0.1.0"
    sparkle_internal_client_id: str = "sparkle-internal"
    mauro_whatsapp: str = os.environ.get("MAURO_WHATSAPP", "")

    # ElevenLabs (TTS)
    elevenlabs_api_key: str = os.environ.get("ELEVENLABS_API_KEY", "")

    # Redis (ARQ)
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
