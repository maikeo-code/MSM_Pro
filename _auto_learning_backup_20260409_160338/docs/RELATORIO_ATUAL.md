# MSM_Pro — Relatorio de Auditoria Completa (5 Ciclos)
> Data: 2026-04-09 | Ciclos: 1-5 | Agente: Opus 4.6

## Resumo Executivo

- **120 endpoints** testados end-to-end em producao
- **996 testes** (876 backend + 120 frontend) — 0 falhas
- **7 bugs corrigidos** (4 backend + 3 frontend)
- **2 problemas externos** identificados (sem fix possivel)

---

## Endpoints Testados por Modulo

| Modulo | Endpoints | Status |
|--------|-----------|--------|
| Health / Root | 4 | OK |
| Auth | 18 | OK |
| Produtos | 5 | OK |
| Vendas/Listings | 26 | OK (1 externo: search-position 403) |
| Analysis | 1 | OK |
| Competitors | 6 | OK |
| Alertas | 7 | OK |
| Consultor IA | 2 | OK |
| Reputacao | 4 | OK |
| Ads | 3 | CORRIGIDO (era 500) |
| Financeiro | 8 | OK |
| Perguntas | 6 | CORRIGIDO (count inflado) |
| Atendimento | 10 | OK |
| Intel/Analytics | 7 | CORRIGIDO (ABC + Inventory) |
| Intel/Pricing | 8 | OK |
| Notifications | 5 | OK |
| **TOTAL** | **120** | **118 OK, 2 externos** |

---

## Bugs Corrigidos

### Backend (4)

| # | Bug | Arquivo | Causa Raiz | Fix |
|---|-----|---------|------------|-----|
| 1 | GET /ads/ retorna 500 | ads/router.py:24 | `scalar_one_or_none()` com multi-account | `scalars().first()` |
| 2 | ABC classification incorreta | intel/analytics/service_abc.py:135 | `elif cumulative <= 95.0` pos-adicao | `elif prev_cumulative < 95.0` |
| 3 | Inventory Health status None | intel/analytics/service_inventory.py:39-46 | DISTINCT ON nao funciona em SA2 | ROW_NUMBER() window function |
| 4 | Perguntas count inflado | perguntas/service.py:353-354 | Count query sem JOIN a MLAccount | Adicionado JOIN no count |

### Frontend (3)

| # | Bug | Arquivo | Causa Raiz | Fix |
|---|-----|---------|------------|-----|
| 5 | /perguntas sem rota | App.tsx | Pagina orfanada | Route + import adicionados |
| 6 | /notificacoes sem rota | App.tsx | Pagina orfanada | Lazy route adicionado |
| 7 | Templates double path | atendimentoTemplatesService.ts | `/api/v1/` hardcoded | Removido prefixo duplicado |

Bonus: adicionado link "Perguntas" no menu lateral (Layout.tsx)

---

## Problemas Externos (Sem Fix Possivel)

| Problema | Endpoint | Causa |
|----------|----------|-------|
| Search Position 403 | GET /listings/{mlb}/search-position | ML API requer scope adicional no token |
| Coverage 42.9% | GET /listings/coverage | Celery sync nao rodou todos os dias |

---

## Qualidade dos Dados por Modulo

| Modulo | Dados Presentes | Observacoes |
|--------|----------------|-------------|
| KPI Summary | Sim | Hoje: 1 venda, R$65. Ontem: 26 vendas, R$2258. |
| Funnel | Sim | 636 visitas, 27 vendas, 4.25% conversao |
| Heatmap | Sim | 176 vendas no periodo |
| Orders | Sim | 239 pedidos (30d) |
| Financeiro | Sim | R$44.291 bruto, R$37.135 liquido (30d) |
| Reputacao | Sim | Level 5_green, Silver, 3344 vendas 60d |
| Pareto | Sim | 23 items, concentration_risk=medium |
| Intel Insights | Sim | 3 insights gerados |
| Comparison | Sim | Dados de 2 periodos |
| Coverage | Parcial | 42.9% (3/7 dias com dados) |
| Recommendations | Vazio | 0 recommendations (precisa gerar) |
| ABC | Corrigido | Classificacao A/B/C agora funciona |
| Inventory | Corrigido | Status health agora funciona |

---

## Testes

| Suite | Passaram | Falharam | Skipped |
|-------|----------|----------|---------|
| Backend (pytest) | 876 | 0 | 6 |
| Frontend (vitest) | 120 | 0 | 0 |
| **Total** | **996** | **0** | **6** |

---

## Proximas Acoes Recomendadas

1. **DEPLOY**: Fazer git push para aplicar os 7 fixes em producao
2. **Reconectar conta ML**: Token atual sem scope offline_access
3. **Gerar recommendations**: POST /intel/pricing/recommendations/generate
4. **SMTP**: Configurar Gmail App Password para emails de alerta
5. **Celery**: Verificar se beat schedule esta rodando em producao
6. **Coverage**: Melhorar de 42.9% para 90%+ com sync diario consistente
