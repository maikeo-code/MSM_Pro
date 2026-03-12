from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    environment: str = "development"
    debug: bool = True
    frontend_url: str = "http://localhost:5173"

    # --- Banco de Dados ---
    database_url: str = "postgresql+asyncpg://msm:msm@localhost:5432/msm_pro"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT ---
    secret_key: str = "insecure-default-secret-change-in-production"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    # --- Email ---
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None

    # --- Celery ---
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Mercado Livre ---
    ml_client_id: Optional[str] = None
    ml_client_secret: Optional[str] = None
    ml_redirect_uri: str = "http://localhost:8000/api/v1/auth/ml/callback"
    ml_api_base: str = "https://api.mercadolibre.com"
    ml_auth_url: str = "https://auth.mercadolivre.com.br/authorization"
    ml_token_url: str = "https://api.mercadolibre.com/oauth/token"


settings = Settings()
