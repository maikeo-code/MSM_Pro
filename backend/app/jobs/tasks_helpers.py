"""
Funções auxiliares compartilhadas entre as Celery tasks de jobs.

Inclui:
  - _create_sync_log: cria registro de instrumentação
  - _finish_sync_log: finaliza registro com status e duração
  - run_async: executa coroutine assíncrona dentro de task Celery síncrona
  - extract_seller_shipping_cost: extrai custo do frete cobrado do vendedor
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional


def extract_seller_shipping_cost(
    shipment_detail: dict,
    logistic_type: Optional[str] = None,
) -> Decimal:
    """
    Extrai o custo do frete cobrado do vendedor a partir do payload de /shipments/{id}.

    Regras:
      - Full (logistic_type == 'fulfillment'): retorna 0. O ML cobra fulfillment
        via fatura mensal separada, não por shipment.
      - Outros (Flex, Coleta, ME2): usa `cost_components.sender_cost` quando presente
        (inclui zero — frete cheio do comprador SEM custo operacional).
      - NUNCA usar `loyal_discount` (é subsídio do programa de lealdade, não custo).
      - NUNCA usar `base_cost` como fallback (é o frete TOTAL antes de subsídios,
        inflaciona o valor pago pelo vendedor).

    Retorna Decimal sempre; nunca None.
    """
    if logistic_type == "fulfillment":
        return Decimal("0")

    cost_components = shipment_detail.get("cost_components") or {}
    sender_cost_raw = cost_components.get("sender_cost")

    if sender_cost_raw is None:
        # Campo ausente: assumir 0 (compatível com semantics "vendedor não pagou nada")
        return Decimal("0")

    try:
        return Decimal(str(sender_cost_raw))
    except Exception:
        return Decimal("0")


async def _create_sync_log(db, task_name: str, ml_account_id=None):
    """Cria um SyncLog com status 'running' e faz flush para obter o id."""
    from app.core.models import SyncLog

    log = SyncLog(task_name=task_name, ml_account_id=ml_account_id, status="running")
    db.add(log)
    await db.flush()
    return log


async def _finish_sync_log(
    db,
    log,
    status: str,
    items: int = 0,
    failed: int = 0,
    error: str | None = None,
) -> None:
    """Finaliza um SyncLog com status, contadores e duração calculada."""
    log.status = status
    log.items_processed = items
    log.items_failed = failed
    log.error_message = error
    log.finished_at = datetime.now(timezone.utc)
    if log.started_at:
        started = log.started_at
        # garante que ambos os datetimes são aware para subtração segura
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        log.duration_ms = int(
            (log.finished_at - started).total_seconds() * 1000
        )
    await db.commit()


def run_async(coro):
    """
    Executa coroutine assíncrona dentro de uma task Celery síncrona.

    Cada task cria um event loop NOVO. Para evitar 'Future attached to a
    different loop' do SQLAlchemy async, descartamos o pool de conexões
    do engine antes e depois da execução. Em contexto Celery, o engine
    já usa NullPool (ver app/core/database.py), mas o dispose extra é
    barato e garante que qualquer cliente Redis/HTTPX criado em loops
    anteriores não vaze.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        try:
            from app.core.database import engine
            loop.run_until_complete(engine.dispose())
        except Exception:
            pass
        return loop.run_until_complete(coro)
    finally:
        try:
            from app.core.database import engine
            loop.run_until_complete(engine.dispose())
        except Exception:
            pass
        loop.close()
