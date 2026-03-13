# Regra #1: Celery Tasks Devem Ter Error Handling Completo
Fonte: Consenso ciclos 1-3
Confianca: 95%
Status: ATIVA

## Regra
Toda task Celery DEVE ter:
1. `try/except` com `logger.exception()` (NAO `logger.error()`)
2. `await db.commit()` explicito
3. `_create_sync_log` no inicio + `_finish_sync_log` no final
4. `bind=True` no decorator para acesso a `self.retry()`

## Evidencia
- _sync_ads_async: sem db.commit() (BUG P0)
- sync_recent_snapshots: sem try/except
- Multiplos pontos com logger.error sem traceback

## Quando Aplicar
Antes de criar ou modificar qualquer Celery task.
