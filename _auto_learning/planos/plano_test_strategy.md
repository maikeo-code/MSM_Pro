# Plano: Estrategia de Testes — De 3% a 60% Cobertura
Data: 2026-03-13
Baseado em: Ciclo 6 — QA Expert Analysis
Prioridade: P1

## Fase 1 — Pure Unit Tests (1 dia, 3% -> 25%)
Sem infraestrutura. Apenas pytest.

### Arquivos a criar:
1. backend/tests/unit/test_financeiro_calculos.py (14 testes)
   - calcular_taxa_ml: classico, premium, full, unknown, override, zero override
   - calcular_margem: normal, zero price, negative margin, full type, frete

2. backend/tests/unit/test_vendas_analytics.py (17 testes)
   - _calculate_price_bands: empty, single, zero visits, multi-band, optimal
   - _calculate_stock_projection: zero stock, empty snaps, boundaries
   - _calculate_health_score: title boundary, types, zero stock
   - _generate_alerts: no snaps, stock critical, no competitor

3. backend/tests/unit/test_financeiro_periodo.py (3 testes)
   - _parse_period: 7d, 30d, unknown

### Deps necessarias:
```
pytest==8.0.*
```

## Fase 2 — DB Integration Tests (1 dia, 25% -> 45%)
Com aiosqlite in-memory.

### Pre-req:
- backend/tests/conftest.py com async engine + session fixtures
- aiosqlite==0.20.*

### Arquivos:
4. backend/tests/integration/test_alertas_conditions.py
5. backend/tests/integration/test_kpi_queries.py

## Fase 3 — HTTP Mocked Tests (1 dia, 45% -> 60%)
Com respx para mock httpx.

### Deps:
- respx==0.21.*

### Arquivos:
6. backend/tests/mocked/test_ml_client_retry.py
7. backend/tests/mocked/test_tasks_order_matching.py

## Fase 4 — Endpoint E2E + Frontend (ongoing, 60% -> 80%)
8. backend/tests/integration/test_auth_endpoints.py
9. backend/tests/integration/test_listings_endpoints.py
10. Frontend: Vitest + React Testing Library

## Status: PENDENTE
