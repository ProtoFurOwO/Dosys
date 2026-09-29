from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno. Los secretos viven solamente en backend/.env."""

    app_name: str = "D.O.S.Y.S API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    docs_enabled: bool = True

    database_url: str = Field(min_length=1)
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=5, le=120)
    cors_origins: str = "http://localhost:5173,http://10.0.2.2"

    # Seguridad del login.
    login_max_attempts: int = Field(default=5, ge=3, le=10)
    login_lock_minutes: int = Field(default=15, ge=1, le=120)
    totp_issuer: str = "D.O.S.Y.S"
    two_factor_challenge_minutes: int = Field(default=5, ge=1, le=15)

    # Documentos clínicos.
    documents_dir: str = "/data/documents"
    documents_max_mb: int = Field(default=10, ge=1, le=50)
    documents_signing_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
