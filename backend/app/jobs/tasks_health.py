"""
Health check independente do pipeline de sincronização.

Objetivo: detectar quando o sistema está silenciosamente quebrado.
Se nenhum listing_snapshot foi criado nas últimas 24h E há contas ML
ativas, algo está errado (Celery worker travado, bug de event loop,
token expirado sem alertar, etc.) — notifica o usuário imediatamente.

Esta task NÃO depende do refresh de token nem da API do Mercado Livre.
É uma verificação puramente local no banco, então funciona mesmo quando
todo o resto do pipeline está quebrado.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.auth.models import MLAccount, User
from app.core.database import AsyncSessionLocal
from app.notifications.service import create_notification
from app.vendas.models import ListingSnapshot

logger = logging.getLogger(__name__)


async def _check_sync_health_async() -> dict:
    """
    Verifica se o pipeline de sincronização está saudável.

    Critério: nas últimas 24h, deve haver pelo menos 1 listing_snapshot
    para cada conta ML ativa. Caso contrário, cria notificação de alerta
    para o usuário dono da conta.
    """
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        # 1. Conta total de snapshots nas últimas 24h
        total_snaps_q = await db.execute(
            select(func.count(ListingSnapshot.id)).where(
                ListingSnapshot.captured_at >= cutoff
            )
        )
        total_snaps = total_snaps_q.scalar() or 0

        # 2. Contas ML ativas
        accounts_q = await db.execute(
            select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
        )
        accounts = accounts_q.scalars().all()
        active_count = len(accounts)

        result = {
            "snapshots_last_24h": total_snaps,
            "active_accounts": active_count,
            "healthy": True,
            "alerts_created": 0,
        }

        # 3. Se há contas ativas mas zero snapshots → ALERTA GLOBAL
        if active_count > 0 and total_snaps == 0:
            result["healthy"] = False
            logger.error(
                "SYNC HEALTH CHECK FALHOU: %d contas ativas, 0 snapshots em 24h",
                active_count,
            )

            # Notificar TODOS os donos de conta ML ativa
            user_ids_seen: set = set()
            for acc in accounts:
                if acc.user_id in user_ids_seen:
                    continue
                user_ids_seen.add(acc.user_id)

                await create_notification(
                    db,
                    user_id=acc.user_id,
                    type="sync_failed",
                    title="Sincronização não está rodando",
                    message=(
                        "Detectamos que nenhuma sincronização foi concluída "
                        "nas últimas 24 horas. Os dados de vendas, preços e "
                        "estoque podem estar desatualizados. Verifique se as "
                        "contas do Mercado Livre estão conectadas ou contate "
                        "o suporte."
                    ),
                    action_url="/configuracoes",
                )
                result["alerts_created"] += 1

            await db.commit()
        else:
            logger.info(
                "Sync health OK: %d snapshots em 24h para %d contas",
                total_snaps,
                active_count,
            )

        return result
