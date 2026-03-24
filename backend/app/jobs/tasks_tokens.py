"""
Lógica assíncrona para renovação de tokens OAuth do Mercado Livre.

Funções exportadas:
  - _refresh_expired_tokens_async: busca contas com token prestes a expirar e renova
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select

from app.auth.models import MLAccount
from app.auth.service import refresh_ml_token
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


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

        for account in accounts:
            max_retries = 3
            retry_delay = 5  # segundos
            last_error = None

            for attempt in range(max_retries):
                try:
                    token_data = await refresh_ml_token(account)

                    account.access_token = token_data["access_token"]
                    account.refresh_token = token_data.get(
                        "refresh_token", account.refresh_token
                    )
                    expires_in = token_data.get("expires_in", 21600)  # 6h padrão
                    account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=expires_in
                    )

                    logger.info(
                        "Token renovado: account=%s nickname=%s expires=%s attempt=%d",
                        account.id,
                        account.nickname,
                        account.token_expires_at,
                        attempt + 1,
                    )
                    refreshed.append(str(account.id))
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
                            f"Falha permanente ao renovar token de {account.nickname}: {last_error}"
                        )
                        errors.append(
                            {
                                "account_id": str(account.id),
                                "nickname": account.nickname,
                                "error": last_error,
                                "attempts": max_retries,
                            }
                        )

        await db.commit()

        logger.info(
            f"Renovação concluída: {len(refreshed)} sucesso, {len(errors)} erros"
        )
        return {
            "success": len(errors) == 0,  # Sucesso apenas se nenhum erro
            "refreshed": len(refreshed),
            "errors": len(errors),
            "error_details": errors,
        }
