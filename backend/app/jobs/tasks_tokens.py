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

from sqlalchemy.orm import selectinload

from app.auth.models import MLAccount, User
from app.auth.service import refresh_ml_token
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.email import is_smtp_configured, send_alert_email
from app.core.redis_client import get_redis_client
from app.notifications.service import create_notification

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
        # BUG 3: fail-closed — refresh_token do ML é single-use.
        # Se dois workers tentam refresh simultaneamente, o segundo invalida o token do primeiro.
        # Melhor não fazer refresh do que corromper o token por race condition.
        logger.warning(
            f"Erro ao adquirir lock Redis para {account_id}: {e} — "
            f"abortando refresh por segurança (fail-closed para evitar invalidar refresh_token single-use)"
        )
        return False


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

        # Salva token_expires_at antigo ANTES de atualizar (para calcular gap de backfill)
        old_expires_map: dict[str, datetime | None] = {}

        for account in accounts:
            account_id_str = str(account.id)
            old_expires_map[account_id_str] = account.token_expires_at

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
                        # Atualiza campos de tracking
                        account.last_token_refresh_at = datetime.now(timezone.utc)
                        account.token_refresh_failures = 0
                        account.needs_reauth = False

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
                            # Atualiza campos de tracking para falha
                            account.last_token_refresh_at = datetime.now(timezone.utc)
                            account.token_refresh_failures = (account.token_refresh_failures or 0) + 1
                            if account.token_refresh_failures >= 5:
                                account.needs_reauth = True
                            errors.append(
                                {
                                    "account_id": account_id_str,
                                    "nickname": account.nickname,
                                    "error": last_error,
                                    "attempts": max_retries,
                                }
                            )
                            # Cria notificação in-app para o usuário
                            await create_notification(
                                db,
                                user_id=account.user_id,
                                type="token_expired",
                                title=f"Conta '{account.nickname}' desconectada",
                                message=(
                                    f"Não foi possível renovar o token da sua conta '{account.nickname}' no Mercado Livre "
                                    f"após {max_retries} tentativas. Reconecte a conta para continuar recebendo dados de vendas. "
                                    f"Erro: {last_error[:100]}"
                                ),
                                action_url="/configuracoes",
                            )

                            # Email imediato ao dono da conta
                            if is_smtp_configured():
                                user_row = await db.execute(
                                    select(User).where(User.id == account.user_id)
                                )
                                user_obj = user_row.scalar_one_or_none()
                                if user_obj and user_obj.email:
                                    body = (
                                        f"A conta '{account.nickname}' do Mercado Livre "
                                        f"foi desconectada do MSM_Pro após {max_retries} "
                                        f"tentativas de renovação automática do token OAuth.\n\n"
                                        f"Erro técnico: {last_error[:200]}\n\n"
                                        f"Enquanto a conta estiver desconectada, nenhum dado "
                                        f"novo de vendas, preços ou concorrentes será "
                                        f"capturado.\n\n"
                                        f"Ação necessária: acesse "
                                        f"{settings.frontend_url}/configuracoes e clique em "
                                        f"Reconectar para a conta '{account.nickname}'."
                                    )
                                    try:
                                        send_alert_email(
                                            to=user_obj.email,
                                            subject=f"[MSM_Pro] Conta '{account.nickname}' desconectada",
                                            body=body,
                                        )
                                    except Exception as exc:
                                        logger.error(
                                            "Falha ao enviar email de token expirado para %s: %s",
                                            user_obj.email,
                                            exc,
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
        now = datetime.now(timezone.utc)
        for account in accounts:
            account_id_str = str(account.id)
            if account_id_str not in refreshed:
                continue

            # Usa o token_expires_at ANTIGO (antes do refresh) para calcular gap real
            old_expires = old_expires_map.get(account_id_str)
            # BUG 4: se token_expires_at é None, usar last_token_refresh_at como heurística;
            # se ambos são None, assume 7 dias para garantir que backfill sempre dispara.
            if old_expires:
                time_since_expiry = (now - old_expires).total_seconds()
            elif account.last_token_refresh_at:
                time_since_expiry = (now - account.last_token_refresh_at).total_seconds()
            else:
                time_since_expiry = 86400 * 7  # 7 dias — sem informação, assume desconectado longo prazo

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
