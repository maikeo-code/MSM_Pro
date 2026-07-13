"""
Lógica assíncrona para sincronização de reputação do vendedor.

Funções exportadas:
  - _sync_reputation_async: busca reputação de cada conta ML ativa e salva snapshot
"""
import logging

from sqlalchemy import select

from app.auth.models import MLAccount
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _sync_reputation_async():
    """Busca reputacao de cada conta ML ativa e salva snapshot.

    Grava SyncLog (task global, ml_account_id=None) para ficar observavel em
    /health/sync — antes a task rodava "invisivel" e nao dava p/ confirmar o beat
    de 3h do E14 (achado da paridade medicao 3, 2026-07-11)."""
    from app.reputacao.service import fetch_and_save_reputation

    from .tasks_helpers import _create_sync_log, _finish_sync_log

    async with AsyncSessionLocal() as db:
        log = await _create_sync_log(db, "sync_reputation")
        try:
            result = await db.execute(
                select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
            )
            accounts = result.scalars().all()

            logger.info(f"Sincronizando reputacao de {len(accounts)} contas ML")

            synced, errors_count = 0, 0
            for account in accounts:
                try:
                    snapshot = await fetch_and_save_reputation(db, account)
                    if snapshot:
                        synced += 1
                except Exception as e:
                    logger.error(
                        f"Erro ao sincronizar reputacao de {account.nickname}: {e}"
                    )
                    errors_count += 1

            await db.commit()
            logger.info(f"Reputacao: {synced} sincronizadas, {errors_count} erros")
            await _finish_sync_log(
                db, log, "success", items=synced, failed=errors_count
            )
            return {"success": True, "synced": synced, "errors": errors_count}
        except Exception as exc:
            await _finish_sync_log(db, log, "error", error=str(exc)[:500])
            raise
