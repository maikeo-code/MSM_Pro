from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


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
