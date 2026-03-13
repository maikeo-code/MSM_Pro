# MSM_Pro — Análise Cruzada & Proposta de Arquitetura v2

**Data:** 12/03/2026
**Autor:** Claude Opus 4.6 (Análise Completa)
**Fontes cruzadas:** CLAUDE.md, ml_architecture_blueprint.md, código backend (9 módulos), código frontend (11 páginas), QA reports, architecture_report.md, code_quality_report.md

---

## 1. Diagnóstico Geral — Estado Real do Projeto

### O que já existe (e funciona)

O MSM_Pro está **muito mais avançado** do que o CLAUDE.md documenta. O código real mostra:

| Área | CLAUDE.md diz | Realidade |
|------|--------------|-----------|
| Módulos backend | 7 (auth, vendas, produtos, concorrência, alertas, financeiro, ws) | **10 módulos** (+reputação, ads, consultor IA) |
| Migrations | Descreve 3 | **10 migrations** (0001–0010) |
| Celery tasks | "sync diário 06:00" | **8 tasks** com schedules diferentes |
| Frontend pages | 7 páginas | **11 rotas** (+ financeiro, publicidade, reputação, detalhe) |
| Testes | Não menciona | 1 teste (test_health.py) — praticamente zero |

### Score consolidado (dos reports de análise existentes)

| Dimensão | Score | Comentário |
|----------|-------|-----------|
| Arquitetura geral | 74/100 | Boa fundação, mas monólito crescendo |
| Qualidade de código | 65/100 | vendas/service.py com ~2000 linhas é o maior risco |
| Naming conventions | 88/100 | Consistente, mistura PT/EN intencional |
| DRY (duplicação) | 54/100 | Dashboard e Anúncios copiam lógica |
| SOLID principles | 62/100 | Service files fazem tudo |
| Complexidade ciclomática | 48/100 | Funções muito longas |
| Type safety | 72/100 | Bom no TS, razoável no Python |
| Error handling | 78/100 | try/except genéricos demais |
| Cobertura de testes | ~2/100 | Praticamente inexistente |
| Frontend completude | 85-90% | Profissional, mas sem testes |

---

## 2. Gaps Críticos — O que o Blueprint Propõe vs. O que Existe

### 2.1 Módulos que existem NO BLUEPRINT mas NÃO no código

| Módulo Blueprint | Status Real | Gap |
|-----------------|-------------|-----|
| financial_daily_summary (tabela) | Financeiro calcula on-the-fly, sem tabela de cache | **FALTA** — cada request recalcula tudo |
| ads_campaigns / ads_metrics_daily | Existem como modelos (migration 0009) | OK, mas dados dependem de scraping manual |
| WebSocket (tempo real) | Pasta ws/ vazia, só placeholder | **FALTA** — sem push notifications |

### 2.2 Features que existem NO CÓDIGO mas NÃO no Blueprint

| Feature | Onde está | Observação |
|---------|----------|-----------|
| Consultor IA (Anthropic Claude) | consultor/service.py + router | Não documentado em nenhum lugar |
| Risk Simulator (reputação) | reputacao/router.py | Blueprint menciona mas não detalha |
| Cashflow D+8 projection | financeiro/service.py | Blueprint menciona superficialmente |
| Orders table (model completo) | vendas/models.py (Order) | Blueprint não descreve |

### 2.3 Dados do Blueprint sem implementação

| Dado Extraído (Missão) | Implementado? | Prioridade |
|------------------------|--------------|-----------|
| Heat Map vendas dia×hora | Sim (frontend heatmap) | — |
| Recuperação de Carrinho | Não | BAIXA (requer scraping) |
| Quality Score 0-100 | Sim (campo existe, sync parcial) | MÉDIA |
| ACOS/ROAS de Ads | Sim (modelo + cálculo) | ALTA (sem API pública) |
| Waterfall financeiro por transação | Parcial (calcula mas sem drill-down) | ALTA |
| Custo de frete real por anúncio | Campo existe, sync pendente | **CRÍTICO** |
| Taxa real por categoria (centavos) | Endpoint documentado, implementação parcial | **CRÍTICO** |

---

## 3. Problemas Estruturais Identificados

### 3.1 🔴 O Monólito vendas/service.py (~2000 linhas)

Este é o **problema #1** do projeto. Um único arquivo contém:

- Sync de listings do ML
- Listagem com agregação por período
- KPI por período
- Análise detalhada por MLB
- Funnel analytics
- Heatmap de vendas
- Formatação de dados para o frontend

**Impacto:** Qualquer mudança em vendas arrisca quebrar tudo. Impossível testar unitariamente. Difícil para múltiplos agentes trabalharem simultaneamente.

**Proposta:** Quebrar em 5 services:
```
vendas/
├── sync_service.py      ← sync_listings_from_ml, sync snapshots
├── listings_service.py  ← list_listings, get_listing_analysis
├── kpi_service.py       ← get_kpi_by_period, get_kpi_summary
├── analytics_service.py ← get_funnel_analytics, get_heatmap_data
└── formatters.py        ← _formatar_listing, _aggregate_snaps
```

### 3.2 🔴 Rate Limiter Global Mutável no ML Client

O `MLClient` usa um rate limiter global (variável de instância com `asyncio.Lock`). Quando múltiplos Celery workers rodam em paralelo, cada um tem sua própria instância — o rate limit **não é compartilhado** entre workers.

**Impacto:** Com 2+ workers, podem ocorrer 2+ req/s ao ML → rate limit 429 → tokens de retry.

**Proposta:** Usar Redis como rate limiter distribuído:
```python
# Em vez de asyncio.Lock local:
async def _rate_limit(self):
    key = "ml_api_rate_limit"
    while not await redis.set(key, 1, nx=True, ex=1):
        await asyncio.sleep(0.1)
```

### 3.3 🟡 Tokens OAuth em Texto Puro no Banco

Os `access_token` e `refresh_token` do ML estão armazenados como VARCHAR(2000) sem criptografia.

**Impacto:** Se o banco for comprometido, todos os tokens ficam expostos.

**Proposta:** Criptografar com Fernet (symmetric encryption):
```python
from cryptography.fernet import Fernet
# Encrypt antes de salvar, decrypt ao ler
```

### 3.4 🟡 Sem Índices Compostos nas Queries Mais Usadas

As queries mais frequentes são:
```sql
-- Lista de listings por user + período
WHERE listing_id = X AND captured_at >= Y AND captured_at <= Z

-- KPI por user
WHERE user_id = X AND captured_at >= Y
```

**Impacto:** Full table scan em listing_snapshots conforme a tabela cresce. Com 16 anúncios × 365 dias × 1 sync/dia = ~5.840 rows no primeiro ano. Suportável, mas com 100+ anúncios vai degradar.

**Proposta:** Adicionar migration com índices:
```sql
CREATE INDEX ix_snapshot_listing_date ON listing_snapshots(listing_id, captured_at DESC);
CREATE INDEX ix_snapshot_user_date ON listing_snapshots(listing_id, captured_at)
  INCLUDE (price, visits, sales_today, stock);
```

### 3.5 🟡 Frontend: Duplicação entre Dashboard e Anúncios

As páginas Dashboard (929 linhas) e Anúncios (518 linhas) compartilham:
- Mesma tabela de listings com colunas quase idênticas
- Mesma função `exportCSV` copiada verbatim
- Mesma lógica de formatação de moeda/percentual

**Proposta:** Extrair componentes compartilhados:
```
components/
├── ListingsTable/
│   ├── index.tsx          ← tabela reutilizável
│   ├── columns.tsx        ← definição de colunas
│   └── exportCSV.ts       ← utilidade compartilhada
├── KpiCards/
│   └── index.tsx          ← cards de KPI reutilizáveis
└── PeriodSelector/
    └── index.tsx          ← seletor de período
```

### 3.6 🟡 Sem Paginação no Frontend

Todas as tabelas carregam todos os resultados de uma vez. Com 16 anúncios é OK, mas com 100+ vai travar.

**Proposta:** Implementar paginação server-side:
```python
# Backend
@router.get("/listings/")
async def list_listings(page: int = 1, per_page: int = 50, ...):
    offset = (page - 1) * per_page
    ...
```

### 3.7 🟡 Celery Tasks Sem Observabilidade

As 8 tasks rodam em silêncio. Se uma falha, ninguém sabe até notar dados desatualizados.

**Proposta:** Adicionar tabela `sync_logs`:
```sql
CREATE TABLE sync_logs (
    id UUID PRIMARY KEY,
    task_name VARCHAR(100),
    ml_account_id UUID,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    status VARCHAR(20),  -- success, failed, partial
    items_processed INT,
    errors TEXT,
    duration_ms INT
);
```

---

## 4. Proposta de Nova Arquitetura

### 4.1 Visão Geral — Arquitetura Alvo

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React SPA)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │Dashboard │ │Anúncios  │ │Financeiro│ │Reputação │  ...   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       └─────────────┴────────────┴─────────────┘             │
│                    React Query + Zustand                      │
│                    Services Layer (typed)                     │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS (JWT Bearer)
┌───────────────────────────┴──────────────────────────────────┐
│                    API GATEWAY (FastAPI)                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Middleware: Auth │ RateLimit │ CORS │ ErrorHandler      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │  Auth   │ │ Vendas  │ │Financ.  │ │Alertas  │  ...      │
│  │ Module  │ │ Module  │ │ Module  │ │ Module  │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
│       │           │           │           │                  │
│  ┌────┴───────────┴───────────┴───────────┴────────────────┐│
│  │              DOMAIN SERVICES LAYER                       ││
│  │  sync_service │ kpi_service │ margin_service │ etc.     ││
│  └──────────────────────────┬───────────────────────────────┘│
│                             │                                │
│  ┌──────────────────────────┴───────────────────────────────┐│
│  │              INFRASTRUCTURE LAYER                         ││
│  │  MLClient │ Repository │ Cache │ EventBus │ EmailSender  ││
│  └───┬──────────┬──────────┬──────────┬─────────────────────┘│
└──────┼──────────┼──────────┼──────────┼──────────────────────┘
       │          │          │          │
  ┌────┴───┐ ┌───┴────┐ ┌───┴───┐ ┌───┴────┐
  │ ML API │ │Postgres│ │ Redis │ │ SMTP   │
  └────────┘ └────────┘ └───────┘ └────────┘
                              │
                    ┌─────────┴──────────┐
                    │   Celery Workers    │
                    │  (8 scheduled tasks │
                    │   + on-demand sync) │
                    └────────────────────┘
```

### 4.2 Refatoração do Backend — Por Módulo

#### Módulo vendas/ (PRIORIDADE MÁXIMA)
```
vendas/
├── models.py              ← Listing, ListingSnapshot, Order (sem mudança)
├── schemas.py             ← Pydantic schemas (sem mudança)
├── router.py              ← Rotas HTTP (delega para services)
├── sync_service.py        ← NOVO: sync_listings_from_ml()
├── listings_service.py    ← NOVO: list_listings(), get_listing_analysis()
├── kpi_service.py         ← NOVO: get_kpi_by_period(), _kpi_single_day()
├── analytics_service.py   ← NOVO: get_funnel_analytics(), get_heatmap_data()
├── formatters.py          ← NOVO: _formatar_listing(), _aggregate_snaps()
└── repository.py          ← NOVO: queries SQL encapsuladas
```

#### Módulo financeiro/ (PRECISA DE MODELO)
```
financeiro/
├── models.py              ← NOVO: FinancialDailySummary (cache diário)
├── schemas.py
├── router.py
├── service.py             ← calcular_margem(), get_resumo(), get_timeline()
└── cache_service.py       ← NOVO: pre-calcula P&L diário via Celery
```

#### Infraestrutura (NOVO)
```
core/
├── config.py
├── database.py
├── celery_app.py
├── constants.py
├── deps.py
├── email.py
├── rate_limiter.py        ← NOVO: Redis-based distributed rate limiter
├── encryption.py          ← NOVO: Fernet encrypt/decrypt para tokens
├── cache.py               ← NOVO: Redis cache helpers
└── event_bus.py           ← NOVO: pub/sub para WebSocket + alertas
```

### 4.3 Novas Tabelas Propostas

```sql
-- 1. Cache financeiro diário (evita recalcular)
CREATE TABLE financial_daily_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ml_account_id UUID REFERENCES ml_accounts(id),
    date DATE NOT NULL,
    gross_sales DECIMAL(14,2) DEFAULT 0,
    total_fees DECIMAL(12,2) DEFAULT 0,
    total_shipping DECIMAL(12,2) DEFAULT 0,
    total_cost DECIMAL(12,2) DEFAULT 0,
    net_revenue DECIMAL(14,2) DEFAULT 0,
    margin_pct DECIMAL(8,4),
    orders_count INTEGER DEFAULT 0,
    units_sold INTEGER DEFAULT 0,
    UNIQUE(ml_account_id, date)
);

-- 2. Log de sincronizações (observabilidade)
CREATE TABLE sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name VARCHAR(100) NOT NULL,
    ml_account_id UUID REFERENCES ml_accounts(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    error_message TEXT,
    duration_ms INTEGER
);

-- 3. Cache de taxas ML por categoria (evita chamar API a cada request)
CREATE TABLE ml_category_fees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id VARCHAR(50) NOT NULL,
    listing_type_id VARCHAR(50) NOT NULL,
    price_from DECIMAL(12,2),
    price_to DECIMAL(12,2),
    percentage_fee DECIMAL(8,4),
    fixed_fee DECIMAL(10,2),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(category_id, listing_type_id, price_from)
);

-- 4. Índices para performance
CREATE INDEX ix_snapshot_listing_date
    ON listing_snapshots(listing_id, captured_at DESC);
CREATE INDEX ix_orders_seller_date
    ON orders(ml_account_id, created_at DESC);
CREATE INDEX ix_competitor_snapshot_date
    ON competitor_snapshots(competitor_id, captured_at DESC);
```

### 4.4 Frontend — Componentes Compartilhados

```
frontend/src/
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx           ← já existe
│   │   └── PageHeader.tsx        ← NOVO: título + breadcrumb + ações
│   ├── data-display/
│   │   ├── ListingsTable/        ← NOVO: tabela reutilizável
│   │   │   ├── index.tsx
│   │   │   ├── columns.tsx       ← definição de colunas configurável
│   │   │   ├── ListingRow.tsx    ← row com thumbnail, badges, etc
│   │   │   └── TableFooter.tsx   ← totais
│   │   ├── KpiCard.tsx           ← NOVO: card KPI com variação
│   │   ├── KpiGrid.tsx           ← NOVO: grid de N cards
│   │   └── EmptyState.tsx        ← NOVO: estado vazio padronizado
│   ├── charts/
│   │   ├── TimelineChart.tsx     ← NOVO: gráfico temporal reutilizável
│   │   ├── FunnelChart.tsx       ← extrair do Dashboard
│   │   └── HeatmapChart.tsx      ← extrair do Dashboard
│   ├── forms/
│   │   ├── PeriodSelector.tsx    ← NOVO: seletor de período global
│   │   ├── SearchInput.tsx       ← NOVO: busca padronizada
│   │   └── ConfirmDialog.tsx     ← NOVO: confirmação de ações
│   └── feedback/
│       ├── LoadingSkeleton.tsx   ← NOVO: substituir "Carregando..."
│       └── ErrorAlert.tsx        ← NOVO: erro padronizado
├── hooks/
│   ├── useListings.ts           ← NOVO: React Query wrapper
│   ├── useKpi.ts                ← NOVO: React Query wrapper
│   ├── useFinanceiro.ts         ← NOVO: React Query wrapper
│   └── usePagination.ts        ← NOVO: paginação server-side
├── utils/
│   ├── formatters.ts            ← NOVO: extrair formatCurrency etc
│   └── exportCSV.ts             ← NOVO: utilidade compartilhada
```

---

## 5. Roadmap de Implementação — Ordem Sugerida

### Fase 0 — Housekeeping (1-2 sessões)

| # | Tarefa | Impacto | Risco |
|---|--------|---------|-------|
| 0.1 | Atualizar CLAUDE.md para refletir os 10 módulos reais | DOC | Nenhum |
| 0.2 | Documentar consultor, reputacao, ads no CLAUDE.md | DOC | Nenhum |
| 0.3 | Adicionar índices compostos (migration 0011) | PERF | Baixo |
| 0.4 | Criar tabela sync_logs (migration 0012) | OBS | Baixo |
| 0.5 | Limpar dead code (base_price não usado, etc) | QUAL | Nenhum |

### Fase 1 — Refatoração Crítica (2-3 sessões)

| # | Tarefa | Impacto | Risco |
|---|--------|---------|-------|
| 1.1 | Quebrar vendas/service.py em 5 arquivos | QUAL/MAINT | MÉDIO |
| 1.2 | Extrair ListingsTable como componente compartilhado | DRY | Baixo |
| 1.3 | Extrair KpiCards, PeriodSelector, exportCSV | DRY | Baixo |
| 1.4 | Implementar rate limiter distribuído (Redis) | STAB | Baixo |
| 1.5 | Adicionar logging estruturado nas Celery tasks | OBS | Baixo |

### Fase 2 — Features de Alto Valor (do Cronograma existente)

| # | Tarefa | Fase Original | Impacto |
|---|--------|--------------|---------|
| 2.1 | Taxa real por categoria (tabela cache + sync) | Fase 2 | "Você Recebe" preciso |
| 2.2 | Frete real por anúncio (shipping_options API) | Fase 3 | "Você Recebe" completo |
| 2.3 | Cadastro de custo por SKU (UI + vinculação auto) | Fase 4 | Margem real |
| 2.4 | Calculadora de margem completa | Fase 4 | Decisão de preço |
| 2.5 | Financial daily summary (cache Celery) | NOVO | Performance |

### Fase 3 — Qualidade & Testes (contínuo)

| # | Tarefa | Tipo |
|---|--------|------|
| 3.1 | Testes unitários para services (pytest + pytest-asyncio) | Backend |
| 3.2 | Testes de integração para routers (TestClient) | Backend |
| 3.3 | Testes E2E básicos (Playwright) | Frontend |
| 3.4 | CI/CD pipeline (GitHub Actions) | Infra |
| 3.5 | Criptografia de tokens OAuth no banco | Segurança |

### Fase 4 — Features Avançadas

| # | Tarefa | Sprint Original |
|---|--------|----------------|
| 4.1 | WebSocket para push notifications | Sprint 5+ |
| 4.2 | Simulador de preço (What-If) | Fase 5 |
| 4.3 | Paginação server-side em todas as tabelas | NOVO |
| 4.4 | Loading skeletons no lugar de "Carregando..." | NOVO |
| 4.5 | Validação com Zod nos forms do frontend | NOVO |

---

## 6. Métricas de Sucesso

| Métrica | Atual | Meta |
|---------|-------|------|
| Cobertura de testes | ~2% | 60%+ |
| Maior arquivo (linhas) | ~2000 (vendas/service.py) | <400 |
| DRY score | 54/100 | 80+ |
| Tempo de resposta /kpi/summary | ? | <500ms |
| Tempo de sync completo | ? | <3min (16 anúncios) |
| Uptime Railway | ? | 99%+ |

---

## 7. Quick Wins — Pode Fazer AGORA

1. **Migration 0011**: Adicionar índices compostos (5 min de código, grande impacto futuro)
2. **Migration 0012**: Tabela sync_logs (10 min de código, observabilidade)
3. **Extrair exportCSV**: De Dashboard e Anúncios para utils/ (10 min, elimina duplicação)
4. **Atualizar CLAUDE.md**: Documentar módulos reais (15 min, evita confusão futura)
5. **Remover dead code**: base_price e variáveis não usadas (5 min)

---

## 8. Resumo Executivo

O MSM_Pro tem uma **base sólida** com funcionalidades que vão além do documentado. O backend cobre 10 módulos com 8 Celery tasks automatizadas, e o frontend tem 11 páginas profissionais com React Query e Zustand.

Os **3 maiores riscos** são:
1. **vendas/service.py monolítico** — precisa ser quebrado antes de crescer mais
2. **Sem testes** — qualquer mudança pode quebrar silenciosamente
3. **CLAUDE.md desatualizado** — agentes Claude trabalham com informação incompleta

As **3 maiores oportunidades** são:
1. **Taxa real + frete real** — transforma o "Você Recebe" de estimativa em dado preciso
2. **Cache financeiro diário** — elimina recálculos e abre caminho para dashboards rápidos
3. **Componentes compartilhados** — acelera desenvolvimento de novas páginas em 3x

A arquitetura proposta mantém a stack atual (FastAPI + React) mas reorganiza internamente para escalar de 16 para 500+ anúncios sem dor.
