"""
Lógica assíncrona para sincronização de campanhas de publicidade (Ads).

Funções exportadas:
  - _sync_ads_async: para cada conta ML ativa, chama ads.service.sync_ads_from_ml()
"""
import logging

from sqlalchemy import select

from app.auth.models import MLAccount
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient

logger = logging.getLogger(__name__)


async def _sync_ads_async():
    """
    Para cada ml_account ativa:
    1. Cria MLClient com o token da conta
    2. Chama ads.service.sync_ads_from_ml() que faz upsert de AdCampaign e AdSnapshot
    """
    from app.ads.service import sync_ads_from_ml

    async with AsyncSessionLocal() as db:
        acc_result = await db.execute(
            select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
        )
        accounts = acc_result.scalars().all()

        logger.info(f"Sincronizando ads para {len(accounts)} contas ML")

        total_campaigns, total_snapshots, total_errors = 0, 0, 0

        for account in accounts:
            # Snapshot dos atributos ANTES de qualquer chamada que possa
            # causar rollback (sync_ads_from_ml faz rollback interno em
            # alguns paths). Sem isso, próxima iteração lê account.id e
            # dispara greenlet_spawn por estado expired.
            acc_id = account.id
            acc_token = account.access_token
            acc_nickname = account.nickname

            if not acc_token:
                logger.warning(f"Sem token ML para conta {acc_nickname} — ads pulados")
                continue

            client = MLClient(acc_token, ml_account_id=str(acc_id))
            try:
                result = await sync_ads_from_ml(db, client, account)
                total_campaigns += result.get("synced_campaigns", 0)
                total_snapshots += result.get("synced_snapshots", 0)
                logger.info(
                    f"Ads sync OK para {acc_nickname}: "
                    f"{result.get('synced_campaigns', 0)} campanhas, "
                    f"{result.get('synced_snapshots', 0)} snapshots"
                )
            except Exception as e:
                logger.error(f"Erro ao sincronizar ads de {acc_nickname}: {e}")
                total_errors += 1
            finally:
                await client.close()

        logger.info(
            f"Sync ads: {total_campaigns} campanhas, "
            f"{total_snapshots} snapshots, {total_errors} erros"
        )
        return {
            "success": True,
            "total_campaigns": total_campaigns,
            "total_snapshots": total_snapshots,
            "errors": total_errors,
        }
