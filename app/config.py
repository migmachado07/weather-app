"""Configuração tipada; segredos ficam exclusivamente no servidor."""
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = Field(default=12, gt=0, le=60)
    port: int = Field(default=8000, ge=1, le=65535)
    host: str = "127.0.0.1"
    database_url: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'weather_app.db').as_posix()}"
    cache_ttl_seconds: int = Field(default=900, ge=1)
    cache_maxsize: int = Field(default=512, ge=1)
    http_timeout_seconds: float = Field(default=10, gt=0, le=60)
    cors_origins: list[str] = []
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "[::1]"]
    open_meteo_api_key: SecretStr = SecretStr("")
    forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"

