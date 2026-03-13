# Plano: Corrigir BUG _sync_ads_async sem db.commit()
Data: 2026-03-13
Baseado em: Falha #3 (ciclo 2)
Prioridade: P0

## Problema Identificado
A funcao _sync_ads_async em tasks.py nunca chama db.commit() apos sync_ads_from_ml().
Todas as escritas de AdCampaign e AdSnapshot sao descartadas quando a sessao fecha.
Outros sync tasks (orders, competitors, snapshots) todos fazem commit via _finish_sync_log.

## Solucao Proposta
1. Adicionar chamada _create_sync_log no inicio de _sync_ads_async
2. Adicionar await db.commit() apos sync_ads_from_ml
3. Adicionar _finish_sync_log no final (success/error)
4. Adicionar try/except com logger.exception (nao logger.error)
5. Seguir mesmo pattern de _sync_orders_async que funciona corretamente

## Arquivos Afetados
- backend/app/jobs/tasks.py (linhas 1111-1161)

## Riscos
- Baixo. E adicionar commit onde falta, nao mudar logica.

## Metricas de Sucesso
- Apos deploy, tabela ad_campaigns e ad_snapshots tem dados novos
- SyncLog registra execucao de sync_ads

## Status: PENDENTE
