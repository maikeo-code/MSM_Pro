import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    environment: str = "development"
    debug: bool = False
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""

    # --- Banco de Dados ---
    database_url: str = "postgresql+asyncpg://msm:msm@localhost:5432/msm_pro"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT ---
    secret_key: str = "insecure-default-secret-change-in-production"
    access_token_expire_minutes: int = 1440  # 24h (em vez de 30 dias)
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

    # --- Token Encryption ---
    token_encryption_key: Optional[str] = None  # Fernet key; derived from secret_key if not set

    # --- Anthropic (Consultor IA) ---
    anthropic_api_key: str = ""

    # --- Registration Control ---
    registration_open: bool = True  # Allow registration by default (backward compat)

    # --- Rate Limiting ---
    rate_limit_enabled: bool = True  # Can disable for testing via RATE_LIMIT_ENABLED=false

    def model_post_init(self, __context):
        """Valida configurações críticas de segurança após inicialização."""
        if self.environment == "production":
            if self.secret_key == "insecure-default-secret-change-in-production":
                logger.critical(
                    "SECURITY ALERT: Usando secret_key padrão em PRODUÇÃO! "
                    "Defina SECRET_KEY em variáveis de ambiente imediatamente."
                )
            if not self.ml_client_id or not self.ml_client_secret:
                logger.warning("SECURITY ALERT: ML OAuth credentials não configuradas")


settings = Settings()
