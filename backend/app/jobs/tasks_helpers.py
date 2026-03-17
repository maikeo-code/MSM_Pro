"""
Funções auxiliares compartilhadas entre as Celery tasks de jobs.

Inclui:
  - _create_sync_log: cria registro de instrumentação
  - _finish_sync_log: finaliza registro com status e duração
  - run_async: executa coroutine assíncrona dentro de task Celery síncrona
"""
import asyncio
from datetime import datetime, timezone


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
    """Executa coroutine assíncrona dentro de uma task Celery síncrona."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
