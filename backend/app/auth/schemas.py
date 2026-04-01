from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_code: str | None = Field(default=None, min_length=1, max_length=256)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class MLAccountOut(BaseModel):
    id: UUID
    ml_user_id: str
    nickname: str
    email: str | None
    token_expires_at: datetime | None
    is_active: bool
    created_at: datetime
    active_listings_count: int = 0  # será preenchido no router
    last_sync_at: datetime | None = None  # será preenchido no router

    model_config = {"from_attributes": True}


class MLConnectURL(BaseModel):
    auth_url: str
    message: str = "Acesse a URL para autorizar a conta do Mercado Livre"


class UserPreferenceOut(BaseModel):
    active_ml_account_id: UUID | None = None

    model_config = {"from_attributes": True}


class UserPreferenceUpdate(BaseModel):
    active_ml_account_id: UUID | None = None


class TokenDiagnosticAccount(BaseModel):
    """Diagnóstico de token para uma conta ML."""
    id: UUID
    nickname: str
    token_status: str  # "healthy" | "expiring_soon" | "expired" | "unknown"
    token_expires_at: datetime | None
    remaining_hours: float | None
    has_refresh_token: bool
    last_successful_sync: datetime | None
    last_refresh_attempt: datetime | None
    last_refresh_success: bool
    days_since_last_sync: int | None
    data_gap_warning: str | None
    refresh_failure_count: int
    needs_reauth: bool

    model_config = {"from_attributes": True}


class TokenDiagnosticResponse(BaseModel):
    """Resposta completa do diagnóstico de tokens."""
    celery_status: str  # "online" | "offline" | "unknown"
    last_token_refresh_task: datetime | None
    accounts: list[TokenDiagnosticAccount]
    recommendations: list[str]
