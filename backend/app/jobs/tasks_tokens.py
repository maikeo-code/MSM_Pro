"""
Lógica assíncrona para renovação de tokens OAuth do Mercado Livre.

Funções exportadas:
  - _refresh_expired_tokens_async: busca contas com token prestes a expirar e renova
  - Usa Redis lock distribuído para evitar race condition entre múltiplos workers Celery

PROBLEMA CRÍTICO RESOLVIDO:
  Refresh_token do ML é single-use. Se dois workers tentam refresh ao mesmo tempo,
  o segundo invalida o token do primeiro. Solução: Redis SETNX lock com TTL.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select

from app.auth.models import MLAccount
from app.auth.service import refresh_ml_token
from app.core.database import AsyncSessionLocal
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


async def _acquire_token_refresh_lock(account_id: str, timeout: int = 60) -> bool:
    """
    Adquire lock distribuído via Redis para refresh de token específico.
    Evita race condition entre múltiplos workers Celery.

    Args:
        account_id: UUID da conta ML em string
        timeout: TTL do lock em segundos (padrão 60s)

    Returns:
        bool: True se lock foi adquirido, False se outro worker já está fazendo refresh
    """
    redis = get_redis_client()
    lock_key = f"ml_token_refresh:{account_id}"

    try:
        # SETNX = SET if NOT eXists (atomic)
        # Retorna 1 se conseguiu settar (lock adquirido), 0 se já existia
        acquired = await redis.set(lock_key, "1", nx=True, ex=timeout)
        if acquired:
            logger.debug(f"Lock adquirido para refresh de {account_id}")
            return True
        else:
            logger.debug(f"Lock já existe para {account_id} — outro worker está refreshing")
            return False
    except Exception as e:
        logger.warning(f"Erro ao adquirir lock Redis para {account_id}: {e} — prosseguindo sem lock")
        # Fail-open: se Redis falhar, prossegue mesmo assim (pode ter race condition, mas app não quebra)
        return True


async def _release_token_refresh_lock(account_id: str) -> None:
    """Libera lock distribuído após refresh completado."""
    redis = get_redis_client()
    lock_key = f"ml_token_refresh:{account_id}"

    try:
        await redis.delete(lock_key)
        logger.debug(f"Lock liberado para {account_id}")
    except Exception as e:
        logger.warning(f"Erro ao liberar lock Redis para {account_id}: {e}")


async def _refresh_expired_tokens_async():
    """
    Busca contas ML com token prestes a expirar (próximas 2h) e renova.
    Retorna sucesso apenas se TODOS os refreshes forem bem-sucedidos.
    """
    # Renova tokens que expiram nas próximas 3 horas OU já expiraram
    # Isso cobre: tokens prestes a expirar + tokens já expirados por falha anterior
    threshold = datetime.now(timezone.utc) + timedelta(hours=3)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MLAccount).where(
                and_(
                    MLAccount.is_active == True,  # noqa: E712
                    MLAccount.token_expires_at <= threshold,
                    MLAccount.refresh_token.isnot(None),
                )
            )
        )
        accounts = result.scalars().all()

        logger.info(f"Renovando tokens para {len(accounts)} contas ML")

        refreshed = []
        errors = []
        skipped = []

        for account in accounts:
            account_id_str = str(account.id)

            # Tenta adquirir lock distribuído para esta conta
            # Evita race condition entre múltiplos workers
            lock_acquired = await _acquire_token_refresh_lock(account_id_str)
            if not lock_acquired:
                logger.info(
                    f"Refresh de {account.nickname} já em progresso por outro worker — pulando"
                )
                skipped.append(account_id_str)
                continue

            try:
                max_retries = 3
                retry_delay = 5  # segundos
                last_error = None

                for attempt in range(max_retries):
                    try:
                        token_data = await refresh_ml_token(account)

                        if token_data is None:
                            raise Exception("refresh_ml_token retornou None")

                        account.access_token = token_data["access_token"]
                        account.refresh_token = token_data.get(
                            "refresh_token", account.refresh_token
                        )
                        expires_in = token_data.get("expires_in", 21600)  # 6h padrão
                        account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=expires_in
                        )

                        logger.info(
                            "Token renovado com sucesso: account=%s nickname=%s expires=%s attempt=%d",
                            account.id,
                            account.nickname,
                            account.token_expires_at,
                            attempt + 1,
                        )
                        refreshed.append(account_id_str)
                        break  # Sucesso — sai do retry loop

                    except Exception as e:
                        last_error = str(e)
                        logger.warning(
                            f"Tentativa {attempt + 1}/{max_retries} falhou para {account.nickname}: {e}"
                        )

                        if attempt < max_retries - 1:
                            # Aguarda antes de tentar novamente
                            import asyncio
                            await asyncio.sleep(retry_delay)
                        else:
                            # Última tentativa falhou
                            logger.error(
                                f"Falha permanente ao renovar token de {account.nickname} após {max_retries} tentativas: {last_error}"
                            )
                            errors.append(
                                {
                                    "account_id": account_id_str,
                                    "nickname": account.nickname,
                                    "error": last_error,
                                    "attempts": max_retries,
                                }
                            )

            finally:
                # SEMPRE libera o lock, mesmo se houve erro
                await _release_token_refresh_lock(account_id_str)

        await db.commit()

        logger.info(
            f"Renovação de tokens concluída: {len(refreshed)} sucesso, {len(errors)} erros, {len(skipped)} pulados (lock ativo)"
        )

        # Dispara sync catch-up imediato para contas com token renovado
        if refreshed:
            from app.jobs.tasks import sync_all_snapshots
            logger.info(
                "Disparando sync catch-up para %d contas renovadas. Delay: 30s",
                len(refreshed),
            )
            # Agenda sync com delay de 30s para permitir propagação do token
            sync_all_snapshots.apply_async(countdown=30)

        # Dispara backfill automático para contas que ficaram desconectadas
        backfill_accounts = []
        for account in accounts:
            account_id_str = str(account.id)
            if account_id_str not in refreshed:
                continue

            # Verifica se estava expirado há mais de 1 dia
            now = datetime.now(timezone.utc)
            time_since_expiry = (now - account.token_expires_at).total_seconds() if account.token_expires_at else 0

            # Se expirou há mais de 24h, quer dizer que ficou desconectado
            if time_since_expiry > 86400:  # 24h em segundos
                days_disconnected = max(int(time_since_expiry / 86400), 1)
                # Backfill até 30 dias no máximo
                days_to_backfill = min(days_disconnected, 30)
                backfill_accounts.append((account_id_str, days_to_backfill))

        if backfill_accounts:
            from app.jobs.tasks import backfill_orders_after_reconnect
            logger.info(
                "Disparando backfill de pedidos para %d contas reconectadas",
                len(backfill_accounts),
            )
            for account_id, days in backfill_accounts:
                # Agenda backfill com delay de 60s (após sync catch-up)
                backfill_orders_after_reconnect.apply_async(
                    args=[account_id, days],
                    countdown=60,
                )

        return {
            "success": len(errors) == 0,  # Sucesso apenas se nenhum erro
            "refreshed": len(refreshed),
            "errors": len(errors),
            "skipped": len(skipped),
            "backfill_triggered": len(backfill_accounts),
            "error_details": errors,
        }
