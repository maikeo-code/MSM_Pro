"""
Celery tasks para sincronização de dados do Mercado Livre.

Beat schedule:
  - sync_all_listings: todo dia às 06:00 BRT (09:00 UTC)
  - refresh_expired_tokens: a cada 4 horas
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# --- Configuração do Celery ---

celery_app = Celery(
    "msm_pro",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# --- Beat Schedule ---

celery_app.conf.beat_schedule = {
    "sync-all-listings-daily": {
        "task": "app.jobs.tasks.sync_all_listings",
        "schedule": crontab(hour=9, minute=0),  # 09:00 UTC = 06:00 BRT
    },
    "refresh-expired-tokens": {
        "task": "app.jobs.tasks.refresh_expired_tokens",
        "schedule": crontab(minute=0, hour="*/4"),  # A cada 4 horas
    },
}


# --- Helper para rodar async dentro do Celery ---

def run_async(coro):
    """Executa coroutine assíncrona dentro de uma task Celery síncrona."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Tasks ---

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
    return run_async(_sync_listing_snapshot_async(listing_id))


async def _sync_listing_snapshot_async(listing_id: str):
    """Lógica assíncrona do sync de snapshot."""
    from sqlalchemy import select

    from app.auth.models import MLAccount
    from app.core.database import AsyncSessionLocal
    from app.mercadolivre.client import MLClient
    from app.vendas.models import Listing, ListingSnapshot

    async with AsyncSessionLocal() as db:
        # Busca o listing com a conta ML
        result = await db.execute(
            select(Listing).where(Listing.id == listing_id)
        )
        listing = result.scalar_one_or_none()
        if not listing:
            return {"error": f"Listing {listing_id} não encontrado"}

        # Busca a conta ML
        acc_result = await db.execute(
            select(MLAccount).where(MLAccount.id == listing.ml_account_id)
        )
        account = acc_result.scalar_one_or_none()
        if not account or not account.access_token:
            return {"error": f"Conta ML não encontrada para listing {listing_id}"}

        # Chama a API ML
        try:
            async with MLClient(account.access_token) as client:
                item_data = await client.get_listing(listing.mlb_id)

                # Extrai dados do anúncio
                price = Decimal(str(item_data.get("price", 0)))
                stock = 0
                available_qty = item_data.get("available_quantity", 0)
                if isinstance(available_qty, int):
                    stock = available_qty

                sales_today = 0  # ML não fornece vendas do dia diretamente
                questions = item_data.get("questions", {})
                if isinstance(questions, dict):
                    questions_count = questions.get("total", 0)
                else:
                    questions_count = 0

                # Tenta pegar visitas do dia
                today = datetime.now(timezone.utc).date()
                try:
                    visits_data = await client.get_listing_visits(
                        listing.mlb_id, today, today
                    )
                    visits = 0
                    if isinstance(visits_data, list) and visits_data:
                        visits = visits_data[0].get("total_visits", 0)
                except Exception:
                    visits = 0

                # Calcula conversion_rate
                conversion_rate = None
                if visits > 0 and sales_today > 0:
                    conversion_rate = Decimal(str(sales_today / visits * 100)).quantize(
                        Decimal("0.0001")
                    )

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

                # Atualiza preço atual do listing
                listing.price = price
                listing.updated_at = datetime.now(timezone.utc)

                await db.commit()
                return {
                    "success": True,
                    "listing_id": listing_id,
                    "mlb_id": listing.mlb_id,
                    "price": float(price),
                }

        except Exception as e:
            await db.rollback()
            return {"error": str(e), "listing_id": listing_id}


@celery_app.task(
    name="app.jobs.tasks.sync_all_listings",
    bind=True,
)
def sync_all_listings(self):
    """
    Dispara sync_listing_snapshot para cada listing ativo.
    Executado diariamente às 06:00 BRT.
    """
    return run_async(_sync_all_listings_async())


async def _sync_all_listings_async():
    """Busca todos os listings ativos e enfileira sync de cada um."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.vendas.models import Listing

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Listing).where(Listing.status == "active")
        )
        listings = result.scalars().all()

        dispatched = []
        for listing in listings:
            sync_listing_snapshot.delay(str(listing.id))
            dispatched.append(str(listing.id))

        return {
            "dispatched": len(dispatched),
            "listing_ids": dispatched,
        }


@celery_app.task(
    name="app.jobs.tasks.refresh_expired_tokens",
    bind=True,
)
def refresh_expired_tokens(self):
    """
    Renova tokens ML que vão expirar nas próximas 2 horas.
    Executado a cada 4 horas.
    """
    return run_async(_refresh_expired_tokens_async())


async def _refresh_expired_tokens_async():
    """Busca contas ML com token prestes a expirar e renova."""
    from sqlalchemy import select

    from app.auth.models import MLAccount
    from app.auth.service import refresh_ml_token
    from app.core.database import AsyncSessionLocal

    threshold = datetime.now(timezone.utc) + timedelta(hours=2)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MLAccount).where(
                MLAccount.is_active == True,  # noqa: E712
                MLAccount.token_expires_at <= threshold,
                MLAccount.refresh_token.isnot(None),
            )
        )
        accounts = result.scalars().all()

        refreshed = []
        errors = []

        for account in accounts:
            try:
                token_data = await refresh_ml_token(account)

                account.access_token = token_data["access_token"]
                account.refresh_token = token_data.get("refresh_token", account.refresh_token)
                expires_in = token_data.get("expires_in", 21600)
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )
                refreshed.append(str(account.id))
            except Exception as e:
                errors.append({"account_id": str(account.id), "error": str(e)})

        await db.commit()
        return {
            "refreshed": len(refreshed),
            "errors": errors,
        }
