"""Schemas Pydantic para notificações."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserNotificationOut(BaseModel):
    """Saída de notificação para o cliente."""
    id: UUID
    type: str = Field(..., description="Tipo: token_expired, sync_failed, data_gap, account_disabled, warning")
    title: str
    message: str
    is_read: bool
    action_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCountOut(BaseModel):
    """Contagem de notificações não lidas."""
    unread_count: int
