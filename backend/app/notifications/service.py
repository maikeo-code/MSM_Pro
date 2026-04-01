"""Service de notificações."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import UserNotification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    user_id: UUID,
    type: str,
    title: str,
    message: str,
    action_url: str | None = None,
) -> UserNotification:
    """Cria uma notificação para um usuário.

    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário
        type: Tipo de notificação (token_expired, sync_failed, etc)
        title: Título da notificação
        message: Mensagem detalhada
        action_url: URL para ação (ex: /configuracoes)

    Returns:
        UserNotification criada
    """
    notif = UserNotification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        action_url=action_url,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    logger.info(
        "Notificação criada: user_id=%s type=%s title=%s",
        user_id, type, title
    )
    return notif


async def get_unread_notifications(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
) -> list[UserNotification]:
    """Busca notificações não lidas de um usuário, ordenadas por data decrescente.

    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário
        limit: Número máximo de notificações a retornar

    Returns:
        Lista de notificações não lidas
    """
    result = await db.execute(
        select(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == False,  # noqa: E712
        )
        .order_by(desc(UserNotification.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def get_all_notifications(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 50,
) -> list[UserNotification]:
    """Busca todas as notificações de um usuário, ordenadas por data decrescente.

    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário
        limit: Número máximo de notificações a retornar

    Returns:
        Lista de todas as notificações
    """
    result = await db.execute(
        select(UserNotification)
        .where(UserNotification.user_id == user_id)
        .order_by(desc(UserNotification.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def mark_notification_as_read(
    db: AsyncSession,
    notification_id: UUID,
    user_id: UUID,
) -> UserNotification | None:
    """Marca uma notificação como lida.

    Args:
        db: Sessão do banco de dados
        notification_id: ID da notificação
        user_id: ID do usuário (validação de propriedade)

    Returns:
        Notificação atualizada, ou None se não encontrada
    """
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()

    if notif:
        notif.is_read = True
        await db.commit()
        await db.refresh(notif)
        logger.debug(f"Notificação marcada como lida: {notification_id}")

    return notif


async def mark_all_as_read(db: AsyncSession, user_id: UUID) -> int:
    """Marca todas as notificações não lidas de um usuário como lidas.

    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário

    Returns:
        Número de notificações atualizadas
    """
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == False,  # noqa: E712
        )
    )
    notifs = result.scalars().all()

    for notif in notifs:
        notif.is_read = True

    await db.commit()

    logger.info(
        "Marcadas %d notificações como lidas para user_id=%s",
        len(notifs), user_id
    )
    return len(notifs)


async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
    """Conta notificações não lidas de um usuário.

    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário

    Returns:
        Número de notificações não lidas
    """
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == False,  # noqa: E712
        )
    )
    return len(result.scalars().all())


async def delete_notification(
    db: AsyncSession,
    notification_id: UUID,
    user_id: UUID,
) -> bool:
    """Deleta uma notificação.

    Args:
        db: Sessão do banco de dados
        notification_id: ID da notificação
        user_id: ID do usuário (validação de propriedade)

    Returns:
        True se deletada, False se não encontrada
    """
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()

    if notif:
        await db.delete(notif)
        await db.commit()
        logger.debug(f"Notificação deletada: {notification_id}")
        return True

    return False
