"""Router de notificações.

Prefixo: /api/v1/notifications
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.notifications import service
from app.notifications.schemas import NotificationCountOut, UserNotificationOut

router = APIRouter(prefix="/notifications", tags=["notificações"])


@router.get("/", response_model=list[UserNotificationOut])
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    unread_only: bool = Query(
        default=False, description="Mostrar apenas não lidas"
    ),
    limit: int = Query(
        default=50, ge=1, le=100, description="Número máximo de notificações"
    ),
):
    """Lista notificações do usuário.

    Query params:
    - unread_only: se true, retorna apenas não lidas
    - limit: máximo de notificações (1-100, padrão 50)

    Returns:
        Lista de notificações ordenadas por data decrescente
    """
    if unread_only:
        notifs = await service.get_unread_notifications(db, current_user.id, limit=limit)
    else:
        notifs = await service.get_all_notifications(db, current_user.id, limit=limit)

    return notifs


@router.post("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_as_read(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Marca uma notificação como lida."""
    result = await service.mark_notification_as_read(
        db, notification_id, current_user.id
    )

    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    return {"status": "ok"}


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Marca todas as notificações não lidas como lidas."""
    count = await service.mark_all_as_read(db, current_user.id)
    return {"status": "ok", "marked_count": count}


@router.get("/count", response_model=NotificationCountOut)
async def get_unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna contagem de notificações não lidas."""
    count = await service.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_notification(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Deleta uma notificação."""
    deleted = await service.delete_notification(db, notification_id, current_user.id)

    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    return {"status": "ok"}
