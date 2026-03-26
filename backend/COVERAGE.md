# Test Coverage Configuration — MSM_Pro Backend

> Configuração de medição de cobertura de testes para o backend do MSM_Pro.

## Resumo Rápido

- **Tool**: pytest-cov (7.0.0)
- **Configuração**: `.coveragerc` + `pytest.ini`
- **Status Atual**: 17.42% de cobertura (507 testes passando)
- **Objetivo**: Aumentar para 60% antes de deploy em produção

---

## Instalação

```bash
pip install pytest-cov
```

> Já instalado. Versão: 7.0.0

---

## Rodar Testes com Cobertura

### Opção 1: Relatório no terminal
```bash
cd backend
python -m pytest tests/ -q --cov=app --cov-report=term-missing
```

### Opção 2: Relatório HTML (mais detalhado)
```bash
cd backend
python -m pytest tests/ -q --cov=app --cov-report=term-missing --cov-report=html
```

Após rodar, abra em navegador:
```
htmlcov/index.html
```

### Opção 3: Ignorar arquivo específico (ex: test_financeiro_features.py)
```bash
cd backend
python -m pytest tests/ -q --cov=app --cov-report=term-missing \
  --ignore=tests/test_financeiro_features.py
```

### Opção 4: Rodar apenas um módulo
```bash
cd backend
python -m pytest tests/test_auth.py -q --cov=app.auth --cov-report=term-missing
```

---

## Arquivos de Configuração

### `.coveragerc`
Define comportamento global da cobertura:
- **source**: mede apenas `app/`
- **omit**: ignora migrations e __pycache__
- **exclude_lines**: ignora código com `pragma: no cover`

### `pytest.ini`
Integra cobertura ao pytest (seção `[coverage:...]`)

---

## Última Execução (2026-03-26)

- **Total de testes**: 509 (507 passed, 2 failed)
- **Cobertura global**: 17.42% (1.638 / 8.218 statements)
- **Tempo de execução**: 17.71s

### Bugs encontrados
Dois testes de rate limiting falharam:
```
FAILED tests/test_rate_limiting.py::TestRateLimitDisableFeature::test_rate_limit_disabled_via_env
FAILED tests/test_rate_limiting.py::TestRateLimitDisabledBehavior::test_rate_limit_functions_return_none_when_disabled
```

Causa: `RATE_LIMIT_ENABLED=false` não está desativando o rate limit (retorna `'5/minute'` em vez de `None`).

---

## TOP 5 MÓDULOS COM MENOR COBERTURA

| Rank | Módulo | Cobertura | Statements |
|------|--------|-----------|-----------|
| 1 | app/ads/models.py | 0.00% | 39 |
| 2 | app/ads/router.py | 0.00% | 51 |
| 3 | app/ads/service.py | 0.00% | 112 |
| 4 | app/alertas/router.py | 0.00% | 36 |
| 5 | app/analise/router.py | 0.00% | 13 |

**Total em 0% de cobertura**: ~1.500 statements

---

## Módulos com Melhor Cobertura

| Módulo | Cobertura |
|--------|-----------|
| app/vendas/service_calculations.py | 97.84% |
| app/auth/oauth_state.py | 94.59% |
| app/core/crypto.py | 80.70% |
| app/vendas/service_mock.py | 80.00% |
| app/core/config.py | 79.55% |

---

## Estratégia para Aumentar Cobertura

### Fase 1: Priority 1 (Routers em 0%)
Routers são mais fáceis de testar:
1. `app/ads/router.py` (51 stmts)
2. `app/alertas/router.py` (36 stmts)
3. `app/analise/router.py` (13 stmts)
4. `app/atendimento/router.py` (91 stmts)
5. `app/concorrencia/router.py` (44 stmts)

Ganho esperado: ~235 statements = +2.8% na cobertura global

### Fase 2: Priority 2 (Jobs críticos)
Jobs são importantes para produção:
1. `app/jobs/tasks_listings.py` (278 stmts, 4.03%)
2. `app/jobs/tasks_competitors.py` (155 stmts, 6.40%)
3. `app/jobs/tasks_orders.py` (128 stmts, 6.88%)

Ganho esperado: ~370 statements = +4.5% na cobertura global

### Fase 3: Priority 3 (Services complexos)
Services em 0%:
1. `app/ads/service.py` (112 stmts)
2. `app/atendimento/service.py` (233 stmts)
3. `app/consultor/service.py` (243 stmts)
4. `app/concorrencia/service.py` (86 stmts)

Ganho esperado: ~675 statements = +8.2% na cobertura global

**Total esperado após 3 fases**: 17.42% + 2.8% + 4.5% + 8.2% = 32.92%

---

## Próximos Passos

1. [x] Instalar e configurar pytest-cov
2. [x] Criar `.coveragerc`
3. [x] Atualizar `pytest.ini`
4. [x] Rodar e documentar cobertura
5. [ ] Corrigir testes de rate_limit
6. [ ] Adicionar testes para routers em 0%
7. [ ] Adicionar testes para jobs críticos
8. [ ] Implementar CI/CD com gate de cobertura (ex: bloquear merge se < 60%)

---

## Referências

- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
- Arquivo de configuração: `backend/.coveragerc`
- Pytest config: `backend/pytest.ini`
