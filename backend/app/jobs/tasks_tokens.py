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
    """Busca contas ML com token prestes a expirar e renova."""
    threshold = datetime.now(timezone.utc) + timedelta(hours=2)

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

                logger.info("Token renovado: account=%s nickname=%s expires=%s", account.id, account.nickname, account.token_expires_at)
                refreshed.append(str(account.id))

            except Exception as e:
                logger.error(f"Erro ao renovar token de {account.nickname}: {e}")
                errors.append(
                    {
                        "account_id": str(account.id),
                        "nickname": account.nickname,
                        "error": str(e),
                    }
                )

        await db.commit()

        logger.info(
            f"Renovação concluída: {len(refreshed)} sucesso, {len(errors)} erros"
        )
        return {
            "success": True,
            "refreshed": len(refreshed),
            "errors": len(errors),
            "error_details": errors,
        }
