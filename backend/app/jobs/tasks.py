"""
Celery tasks para sincronização de dados do Mercado Livre.

Tasks:
  - sync_all_snapshots: sincroniza snapshots de todos os anúncios ativos diariamente
  - sync_recent_snapshots: sincroniza snapshots de anúncios com mudança recente de preço
  - refresh_expired_tokens: renova tokens ML que vão expirar
  - sync_listing_snapshot: sincroniza snapshot de um anúncio específico
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, select

from app.auth.models import MLAccount
from app.auth.service import refresh_ml_token
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient, MLClientError
from app.vendas.models import Listing, ListingSnapshot

logger = logging.getLogger(__name__)


# --- Helper para rodar async dentro do Celery ---

def run_async(coro):
    """Executa coroutine assíncrona dentro de uma task Celery síncrona."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Task: Sincronizar snapshot de um anúncio específico ---

@celery_app.task(
    name="app.jobs.tasks.sync_listing_snapshot",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_listing_snapshot(self, listing_id: str):
    """
    Sincroniza snapshot de um anúncio específico.
    Chama a API ML e salva o snapshot no banco.
    """
    try:
        return run_async(_sync_listing_snapshot_async(listing_id))
    except Exception as exc:
        logger.error(f"Erro ao sincronizar snapshot de {listing_id}: {exc}")
        # Retry com backoff exponencial
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _sync_listing_snapshot_async(listing_id: str):
    """Lógica assíncrona do sync de snapshot."""
    async with AsyncSessionLocal() as db:
        # Busca o listing com a conta ML
        result = await db.execute(
            select(Listing).where(Listing.id == listing_id)
        )
        listing = result.scalar_one_or_none()
        if not listing:
            logger.warning(f"Listing {listing_id} não encontrado")
            return {"error": f"Listing {listing_id} não encontrado"}

        # Busca a conta ML
        acc_result = await db.execute(
            select(MLAccount).where(MLAccount.id == listing.ml_account_id)
        )
        account = acc_result.scalar_one_or_none()
        if not account or not account.access_token:
            logger.warning(f"Conta ML não encontrada para listing {listing_id}")
            return {"error": f"Conta ML não encontrada para listing {listing_id}"}

        # Chama a API ML
        client = None
        try:
            client = MLClient(account.access_token)

            # Busca dados do item
            item_data = await client.get_item(listing.mlb_id)
            price = Decimal(str(item_data.get("price", listing.price)))
            stock = item_data.get("available_quantity", 0)
            status = item_data.get("status", listing.status)

            # Extrai original_price e sale_price
            original_price_raw = item_data.get("original_price")
            original_price = Decimal(str(original_price_raw)) if original_price_raw else None

            sale_price_data = item_data.get("sale_price")
            sale_price_val = None
            if sale_price_data and isinstance(sale_price_data, dict):
                sp_amount = sale_price_data.get("amount")
                if sp_amount is not None:
                    sale_price_val = Decimal(str(sp_amount))

            # Se sale_price existe e é menor que price, price é o preço original
            if sale_price_val is not None and original_price is None and price > sale_price_val:
                original_price = price

            # Busca visitas do dia
            visits = 0
            try:
                visits_data = await client.get_item_visits(listing.mlb_id, days=1)
                if visits_data and isinstance(visits_data, list) and visits_data:
                    visits = visits_data[0].get("total", 0)
            except MLClientError:
                logger.debug(f"Não conseguiu buscar visitas para {listing.mlb_id}")

            # Busca vendas do dia
            sales_today = 0
            try:
                mlb_normalized = listing.mlb_id.upper().replace("-", "")
                orders_data = await client.get_item_orders(listing.mlb_id, account.ml_user_id, days=1)
                if orders_data and isinstance(orders_data, list):
                    for order in orders_data:
                        for oi in order.get("order_items", []):
                            item_id = oi.get("item", {}).get("id", "")
                            if item_id == mlb_normalized:
                                sales_today += oi.get("quantity", 1)
            except MLClientError:
                logger.debug(f"Não conseguiu buscar pedidos para {listing.mlb_id}")

            # Busca perguntas
            questions_count = 0
            try:
                questions_data = await client.get_item_questions(listing.mlb_id)
                if isinstance(questions_data, dict):
                    questions_count = questions_data.get("total", 0)
            except MLClientError:
                logger.debug(f"Não conseguiu buscar perguntas para {listing.mlb_id}")

            # Calcula taxa de conversão
            conversion_rate = None
            if visits > 0 and sales_today > 0:
                conversion_rate = Decimal(str(round((sales_today / visits) * 100, 4)))

            # Salva snapshot
            snapshot = ListingSnapshot(
                listing_id=listing.id,
                price=price,
                visits=visits,
                sales_today=sales_today,
                questions=questions_count,
                stock=stock,
                conversion_rate=conversion_rate,
            )
            db.add(snapshot)

            # Atualiza preço, status e campos de desconto do listing
            listing.price = price
            listing.original_price = original_price
            listing.sale_price = sale_price_val
            listing.status = status
            listing.updated_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info(f"Snapshot sincronizado para {listing.mlb_id}: R$ {price}")

            return {
                "success": True,
                "listing_id": listing_id,
                "mlb_id": listing.mlb_id,
                "price": float(price),
                "visits": visits,
                "sales_today": sales_today,
            }

        except MLClientError as e:
            logger.error(f"Erro ML ao sincronizar {listing.mlb_id}: {e}")
            await db.rollback()
            return {"error": str(e), "listing_id": listing_id}
        except Exception as e:
            logger.exception(f"Erro inesperado ao sincronizar {listing_id}: {e}")
            await db.rollback()
            return {"error": str(e), "listing_id": listing_id}
        finally:
            if client:
                await client.close()


# --- Task: Sincronizar snapshots de todos os anúncios ---

@celery_app.task(name="app.jobs.tasks.sync_all_snapshots", bind=True)
def sync_all_snapshots(self):
    """
    Sincroniza snapshots de todos os anúncios ativos.
    Executado diariamente às 06:00 BRT.
    """
    try:
        return run_async(_sync_all_snapshots_async())
    except Exception as exc:
        logger.error(f"Erro em sync_all_snapshots: {exc}")
        raise


async def _sync_all_snapshots_async():
    """Busca todos os listings ativos e sincroniza snapshots de cada um."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Listing).where(Listing.status == "active")
        )
        listings = result.scalars().all()

        logger.info(f"Iniciando sincronização de {len(listings)} anúncios ativos")

        dispatched = []
        for listing in listings:
            sync_listing_snapshot.delay(str(listing.id))
            dispatched.append(str(listing.id))

        logger.info(f"Enfileiradas {len(dispatched)} tasks de snapshot")
        return {
            "success": True,
            "dispatched": len(dispatched),
            "listing_ids": dispatched,
        }


# --- Task: Sincronizar snapshots recentes (horária) ---

@celery_app.task(name="app.jobs.tasks.sync_recent_snapshots")
def sync_recent_snapshots():
    """
    Sincroniza snapshots de anúncios com mudança recente de preço.
    Executado a cada hora para capturar mudanças rápidas.
    """
    try:
        return run_async(_sync_recent_snapshots_async())
    except Exception as exc:
        logger.error(f"Erro em sync_recent_snapshots: {exc}")
        raise


async def _sync_recent_snapshots_async():
    """Sincroniza apenas anúncios que tiveram mudança nas últimas horas."""
    async with AsyncSessionLocal() as db:
        # Busca listings ativos que foram atualizados nas últimas 2 horas
        threshold = datetime.now(timezone.utc) - timedelta(hours=2)

        result = await db.execute(
            select(Listing).where(
                and_(
                    Listing.status == "active",
                    Listing.updated_at >= threshold,
                )
            )
        )
        listings = result.scalars().all()

        logger.info(f"Sincronizando {len(listings)} anúncios com mudança recente")

        for listing in listings:
            sync_listing_snapshot.delay(str(listing.id))

        return {
            "success": True,
            "synced": len(listings),
        }


# --- Task: Renovar tokens ML expirados ---

@celery_app.task(name="app.jobs.tasks.refresh_expired_tokens", bind=True)
def refresh_expired_tokens(self):
    """
    Renova tokens ML que vão expirar nas próximas 2 horas.
    Executado a cada 4 horas.
    """
    try:
        return run_async(_refresh_expired_tokens_async())
    except Exception as exc:
        logger.error(f"Erro em refresh_expired_tokens: {exc}")
        raise


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
                account.refresh_token = token_data.get("refresh_token", account.refresh_token)
                expires_in = token_data.get("expires_in", 21600)  # 6h padrão
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )

                logger.info(f"Token renovado para conta {account.nickname}")
                refreshed.append(str(account.id))

            except Exception as e:
                logger.error(f"Erro ao renovar token de {account.nickname}: {e}")
                errors.append({"account_id": str(account.id), "nickname": account.nickname, "error": str(e)})

        await db.commit()

        logger.info(f"Renovação concluída: {len(refreshed)} sucesso, {len(errors)} erros")
        return {
            "success": True,
            "refreshed": len(refreshed),
            "errors": len(errors),
            "error_details": errors,
        }
