# Plano: Implementar Data Retention para Snapshots
Data: 2026-03-13
Baseado em: Falha #2 (ciclo 2)
Prioridade: P3

## Problema Identificado
Tabelas listing_snapshots e competitor_snapshots crescem indefinidamente (~24 rows/dia).
Sem mecanismo de purge ou particionamento. Projecao 3 anos: ~26k rows.

## Solucao Proposta
1. Criar Celery task purge_old_snapshots que roda semanalmente
2. Politica: manter snapshots dos ultimos 90 dias em detalhe
3. Para dados > 90 dias: consolidar em 1 snapshot/semana (media semanal)
4. Para dados > 1 ano: consolidar em 1 snapshot/mes
5. Adicionar config RETENTION_DAYS=90 em settings

## Arquivos Afetados
- backend/app/jobs/tasks.py — nova task
- backend/app/core/celery_app.py — novo beat schedule
- backend/app/core/config.py — nova config

## Riscos
- Perda de granularidade historica em dados antigos
- Mitigacao: consolidar com medias em vez de deletar

## Metricas de Sucesso
- Tabela listing_snapshots nunca ultrapassa ~6000 rows
- Dados historicos consolidados disponiveis para analise

## Status: PENDENTE
