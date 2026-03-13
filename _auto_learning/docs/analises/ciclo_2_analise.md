# Analise do Ciclo 2
Data: 2026-03-13

## Metricas
- Perguntas geradas: 5
- Respondidas: 5 (100%)
- Aprovadas: 2 (indexes parcial, N+1 com solucao)
- Rejeitadas/Falhas: 3 (testes, data retention, error handling)
- Sucessos: 2 | Falhas: 3

## Descobertas Criticas

### BUG REAL: _sync_ads_async sem db.commit()
- **Arquivo**: tasks.py linhas 1111-1161
- **Impacto**: Dados de campanhas de ads nunca sao persistidos no banco
- **Prioridade**: P0 — bug em producao
- **Acao**: Adicionar db.commit() e _finish_sync_log

### Cobertura de Testes: 3%
- Apenas 2 testes triviais (health check)
- Zero testes em logica de negocio (vendas, financeiro, alertas, ML client)
- Sem conftest.py, sem fixtures, sem testes frontend
- **Prioridade**: P1

### N+1 Queries: 5 pontos identificados
- _sync_competitor_snapshots_async: 2 queries/competitor
- _check_competitor_stockout: ate 4 queries/competitor
- alertas _check_competitor_price_change: O(listings x competitors)
- **Prioridade**: P2

### Data Retention: Inexistente
- Snapshots crescem ~24 rows/dia sem cleanup
- Projecao 1 ano: ~8700 rows
- **Prioridade**: P3 (volume atual e pequeno)

### Error Handling Gaps
- sync_recent_snapshots sem try/except
- _get_ads_data engole excecoes sem log
- logger.error sem traceback em multiplos pontos
- **Prioridade**: P2

## Padroes Emergentes (Ciclo 1 + 2)
1. **Seguranca defensiva presente** mas com gaps pontuais (webhook, CORS)
2. **Performance aceitavel** mas com divida tecnica em N+1 queries
3. **Operacional fragil** — sem testes, sem data retention, health check raso
4. **Design patterns bons** — retry, rate limit, upsert — mas aplicacao inconsistente
