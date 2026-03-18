"""
Celery tasks para sincronização de dados do Mercado Livre.

Este arquivo contém APENAS as definições das tasks Celery (@celery_app.task).
A lógica assíncrona está nos submódulos:
  - tasks_helpers.py    — run_async, _create_sync_log, _finish_sync_log
  - tasks_listings.py   — _sync_listing_snapshot_async, _sync_all_snapshots_async, _sync_recent_snapshots_async
  - tasks_tokens.py     — _refresh_expired_tokens_async
  - tasks_competitors.py — _sync_competitor_snapshots_async, _check_competitor_stockout
  - tasks_orders.py     — _sync_orders_async
  - tasks_ads.py        — _sync_ads_async
  - tasks_alerts.py     — _evaluate_alerts_async
  - tasks_reputation.py — _sync_reputation_async
  - tasks_digest.py     — _send_weekly_digest_async

Tasks agendadas (beat schedule em core/celery_app.py):
  - sync_all_snapshots:       diariamente às 06:00 BRT (09:00 UTC)
  - sync_recent_snapshots:    a cada hora
  - refresh_expired_tokens:   a cada 4 horas
  - sync_competitor_snapshots: diariamente às 07:00 BRT (10:00 UTC)
  - sync_reputation:          diariamente às 06:30 BRT (09:30 UTC)
  - evaluate_alerts:          a cada 2 horas
  - sync_orders:              a cada 2 horas
  - sync_ads:                 diariamente às 10:00 UTC (07:00 BRT)
  - send_weekly_digest:       todo domingo às 20:00 BRT (23:00 UTC)
"""
import asyncio
import logging

from app.core.celery_app import celery_app
from .tasks_lock import acquire_task_lock, release_task_lock

from .tasks_ads import _sync_ads_async
from .tasks_alerts import _evaluate_alerts_async
from .tasks_competitors import _sync_competitor_snapshots_async
from .tasks_digest import _send_weekly_digest_async
from .tasks_helpers import run_async
from .tasks_listings import (
    _sync_all_snapshots_async,
    _sync_listing_snapshot_async,
    _sync_recent_snapshots_async,
)
from .tasks_orders import _sync_orders_async
from .tasks_reputation import _sync_reputation_async
from .tasks_tokens import _refresh_expired_tokens_async

logger = logging.getLogger(__name__)


# --- Task: Sincronizar snapshot de um anúncio específico ---

@celery_app.task(
    name="app.jobs.tasks.sync_listing_snapshot",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_listing_snapshot(self, listing_id: str, visits_override: int | None = None):
    """
    Sincroniza snapshot de um anúncio específico.
    Chama a API ML e salva o snapshot no banco.

    visits_override: quando fornecido pelo bulk caller (sync_all_snapshots),
    pula a chamada individual de visitas e usa este valor diretamente.
    """
    try:
        return run_async(
            _sync_listing_snapshot_async(listing_id, visits_override=visits_override)
        )
    except Exception as exc:
        logger.error(f"Erro ao sincronizar snapshot de {listing_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


# --- Task: Sincronizar snapshots de todos os anúncios ---

@celery_app.task(name="app.jobs.tasks.sync_all_snapshots", bind=True)
def sync_all_snapshots(self):
    """
    Sincroniza snapshots de todos os anúncios ativos.
    Executado diariamente às 06:00 BRT.
    Uses Redis lock to prevent duplicate execution across workers.
    """
    loop = asyncio.new_event_loop()
    try:
        if not loop.run_until_complete(acquire_task_lock("sync_all_snapshots", timeout=900)):
            return {"status": "skipped", "reason": "lock_held"}
        return run_async(_sync_all_snapshots_async())
    except Exception as exc:
        logger.error(f"Erro em sync_all_snapshots: {exc}")
        raise
    finally:
        loop.run_until_complete(release_task_lock("sync_all_snapshots"))
        loop.close()


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


# --- Task: Sincronizar snapshots dos concorrentes ---

@celery_app.task(name="app.jobs.tasks.sync_competitor_snapshots", bind=True)
def sync_competitor_snapshots(self):
    """
    Sincroniza o preço atual de todos os concorrentes ativos.
    Executado diariamente às 07:00 BRT (10:00 UTC), após o sync principal.
    """
    try:
        return run_async(_sync_competitor_snapshots_async())
    except Exception as exc:
        logger.error(f"Erro em sync_competitor_snapshots: {exc}")
        raise


# --- Task: Avaliar alertas e disparar notificações ---

@celery_app.task(name="app.jobs.tasks.evaluate_alerts", bind=True)
def evaluate_alerts(self):
    """
    Avalia todas as configurações de alerta ativas.
    Executado a cada 2 horas.
    """
    try:
        return run_async(_evaluate_alerts_async())
    except Exception as exc:
        logger.error(f"Erro em evaluate_alerts: {exc}")
        raise


# --- Task: Sincronizar reputacao do vendedor ---

@celery_app.task(name="app.jobs.tasks.sync_reputation", bind=True)
def sync_reputation(self):
    """
    Sincroniza reputacao de todas as contas ML ativas.
    Executado diariamente as 06:30 BRT (09:30 UTC).
    """
    try:
        return run_async(_sync_reputation_async())
    except Exception as exc:
        logger.error(f"Erro em sync_reputation: {exc}")
        raise


# --- Task: Sincronizar pedidos individuais ---

@celery_app.task(name="app.jobs.tasks.sync_orders", bind=True)
def sync_orders(self):
    """
    Sincroniza pedidos individuais dos ultimos 2 dias.
    Uses Redis lock to prevent duplicate execution.
    """
    loop = asyncio.new_event_loop()
    try:
        if not loop.run_until_complete(acquire_task_lock("sync_orders", timeout=600)):
            return {"status": "skipped", "reason": "lock_held"}
        return run_async(_sync_orders_async())
    except Exception as exc:
        logger.error(f"Erro em sync_orders: {exc}")
        raise
    finally:
        loop.run_until_complete(release_task_lock("sync_orders"))
        loop.close()


# --- Task: Enviar digest semanal ---

@celery_app.task(
    name="app.jobs.tasks.send_weekly_digest",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def send_weekly_digest(self):
    """
    Envia o resumo semanal por email para todos os usuários ativos.
    Executado todo domingo às 20:00 BRT (23:00 UTC).
    """
    try:
        return run_async(_send_weekly_digest_async())
    except Exception as exc:
        logger.error("Erro em send_weekly_digest: %s", exc)
        raise


# --- Task: Sincronizar campanhas de ads ---

@celery_app.task(name="app.jobs.tasks.sync_ads", bind=True)
def sync_ads(self):
    """
    Sincroniza campanhas e metricas de ads do Mercado Livre.
    Para cada conta ML ativa, chama ads/service.sync_ads_from_ml().
    Executado diariamente as 10:00 UTC (07:00 BRT).
    """
    try:
        return run_async(_sync_ads_async())
    except Exception as exc:
        logger.error(f"Erro em sync_ads: {exc}")
        raise
