# BLUEPRINT DE ARQUITETURA — Nubimetrics Intel para MSM_Pro

> Versao: 1.0
> Data: 2026-03-18
> Status: Aprovado para implementacao
> Autor: Architect Reviewer Agent

---

## 1. VISAO GERAL DO SISTEMA

### 1.1 Proposito

Implementar funcionalidades equivalentes ao Nubimetrics dentro do MSM_Pro, transformando-o
de um dashboard de vendas basico em uma plataforma completa de inteligencia de mercado para
vendedores do Mercado Livre. O sistema adicionara tres pilares de inteligencia que hoje nao
existem: **Market Intelligence**, **Competitive Intelligence** e **AI-Powered Optimization**.

### 1.2 Diagrama de Sistema (Alto Nivel)

```
                         USUARIO (Browser)
                              |
                    +---------+---------+
                    |   React Frontend  |
                    |  (SPA + Vite)     |
                    +---------+---------+
                              |
                         HTTPS/REST
                              |
                    +---------+---------+
                    |  FastAPI Gateway   |
                    |  /api/v1/intel/*   |
                    +---------+---------+
                              |
         +--------+-----------+-----------+---------+
         |        |           |           |         |
    +----v---+ +--v-----+ +--v------+ +--v----+ +--v--------+
    | Market | | Compet. | | Optim.  | | Sales | | Analytics |
    | Intel  | | Intel   | | Engine  | | Proj. | | Engine    |
    | Module | | Module  | | (IA)    | | Module| | (Core)    |
    +----+---+ +--+-----+ +--+------+ +--+----+ +--+--------+
         |        |           |           |         |
         +--------+-----------+-----------+---------+
                              |
                   +----------+----------+
                   |                     |
            +------v------+      +------v------+
            |  PostgreSQL  |      |    Redis     |
            |  (primary)   |      |  (cache +    |
            |              |      |   queues)    |
            +--------------+      +------+------+
                                         |
                                  +------v------+
                                  |   Celery     |
                                  |  Workers     |
                                  |  (async)     |
                                  +------+------+
                                         |
                                  +------v------+
                                  |  ML API      |
                                  |  (mercado    |
                                  |   libre)     |
                                  +--------------+
```

### 1.3 Principios Arquiteturais

1. **Modular por dominio** — cada pilar de inteligencia e um modulo independente no backend
2. **Dados primeiro** — coletar e armazenar antes de analisar; analytics rodam sobre dados proprios
3. **Cache agressivo** — dados de mercado mudam devagar; cache de 1h-24h reduz chamadas a ML API
4. **Processamento async** — toda coleta pesada via Celery; frontend nunca espera scraping
5. **Evolucao incremental** — cada fase entrega valor completo; nao ha dependencia circular entre fases
6. **Reutilizacao do client.py existente** — toda chamada a ML API passa pelo client com retry/rate-limit

---

## 2. DECOMPOSICAO DE MODULOS

### 2.1 Mapa de Modulos (Novos)

```
backend/app/
|
+-- intel/                          <-- NOVO: Namespace raiz para inteligencia
|   +-- __init__.py
|   +-- market/                     <-- NOVO: Market Intelligence
|   |   +-- __init__.py
|   |   +-- models.py              Tabelas: categories, category_snapshots, keyword_rankings
|   |   +-- schemas.py             Pydantic schemas para request/response
|   |   +-- service.py             Logica de negocio (explorador, rankings)
|   |   +-- service_categories.py  Drill-down de categorias ML
|   |   +-- service_keywords.py    Rankings de palavras-chave
|   |   +-- service_demand.py      Analise de demanda e oportunidades
|   |   +-- router.py              Endpoints /api/v1/intel/market/*
|   |
|   +-- competitors/                <-- NOVO: Competitive Intelligence (expande concorrencia/)
|   |   +-- __init__.py
|   |   +-- models.py              Tabelas: monitored_sellers, seller_snapshots
|   |   +-- schemas.py
|   |   +-- service.py             Logica de monitoramento
|   |   +-- service_discovery.py   Motor de descoberta automatica
|   |   +-- service_analysis.py    Analise competitiva (Pareto, estimativas)
|   |   +-- router.py              Endpoints /api/v1/intel/competitors/*
|   |
|   +-- optimizer/                  <-- NOVO: AI Optimization Engine
|   |   +-- __init__.py
|   |   +-- models.py              Tabelas: optimization_reports, title_suggestions
|   |   +-- schemas.py
|   |   +-- service.py             Orquestracao do motor de IA
|   |   +-- service_titles.py      Otimizacao de titulos
|   |   +-- service_pricing.py     Sugestao de preco inteligente
|   |   +-- service_scoring.py     Score/saude do anuncio
|   |   +-- prompts.py             Templates de prompts para Claude
|   |   +-- router.py              Endpoints /api/v1/intel/optimizer/*
|   |
|   +-- analytics/                  <-- NOVO: Analytics Engine (transversal)
|   |   +-- __init__.py
|   |   +-- models.py              Tabelas: analytics_cache, user_insights
|   |   +-- schemas.py
|   |   +-- service.py             Calculos estatisticos
|   |   +-- service_pareto.py      Analise Pareto 80/20
|   |   +-- service_forecast.py    Projecao de vendas
|   |   +-- service_seasonality.py Sazonalidade
|   |   +-- service_export.py      Exportacao CSV/Excel
|   |   +-- router.py              Endpoints /api/v1/intel/analytics/*
|   |
|   +-- common/                     <-- NOVO: Utilidades compartilhadas
|       +-- __init__.py
|       +-- ml_api_helpers.py       Helpers especificos para endpoints ML usados por intel
|       +-- cache.py                Decorator de cache Redis para intel
|       +-- rate_limiter.py         Rate limiting interno para coleta
|       +-- constants.py            Constantes do modulo intel
|
+-- jobs/
|   +-- tasks_market.py             <-- NOVO: Celery tasks para Market Intel
|   +-- tasks_competitors_v2.py     <-- NOVO: Tasks expandidas de concorrencia
|   +-- tasks_optimizer.py          <-- NOVO: Tasks de otimizacao IA
|   +-- tasks_analytics.py          <-- NOVO: Tasks de analytics batch
```

### 2.2 Modulos Existentes Afetados

| Modulo Existente | Alteracao Necessaria |
|------------------|---------------------|
| `vendas/` | Adicionar relacao com analytics; novos campos em ListingSnapshot |
| `concorrencia/` | Extender Competitor model; reusar como base para intel/competitors |
| `mercadolivre/client.py` | Adicionar metodos para categories, trends, search |
| `jobs/tasks.py` | Registrar novas tasks no beat schedule |
| `core/celery_app.py` | Incluir schedules para coleta de mercado |
| `core/config.py` | Novas config vars (ANTHROPIC_API_KEY, cache TTLs) |
| `alertas/` | Novos tipos de alerta (posicao, oportunidade) |

### 2.3 Fronteiras de Modulo — Regras de Dependencia

```
intel/market       --> mercadolivre/client.py, core/database, intel/common
intel/competitors  --> mercadolivre/client.py, core/database, intel/common, concorrencia/models
intel/optimizer    --> mercadolivre/client.py, core/database, intel/common, intel/market, intel/analytics
intel/analytics    --> core/database, intel/common, vendas/models
intel/common       --> core/* (somente)

PROIBIDO:
- intel/* nunca importa de auth/ (exceto deps.py para get_current_user)
- intel/market nunca importa de intel/competitors (independentes)
- intel/analytics nunca importa de intel/optimizer (analytics e input, nunca output)
```

---

## 3. FLUXOS DE DADOS

### 3.1 Fluxo: Coleta de Dados de Mercado (Market Intel)

```
                    Celery Beat (a cada 6h)
                           |
                           v
              +---------------------------+
              | tasks_market.py           |
              | sync_category_tree()      |
              +---------------------------+
                           |
         +-----------------+-----------------+
         |                                   |
         v                                   v
+------------------+              +-------------------+
| ML API           |              | ML API            |
| /sites/MLB/      |              | /trends/MLB/      |
| categories/...   |              | search?category=  |
+--------+---------+              +---------+---------+
         |                                  |
         v                                  v
+------------------+              +-------------------+
| category_tree    |              | keyword_rankings  |
| (PostgreSQL)     |              | (PostgreSQL)      |
+--------+---------+              +---------+---------+
         |                                  |
         +----------------------------------+
                           |
                           v
              +---------------------------+
              | Redis Cache               |
              | intel:market:cat:{id}     |
              | TTL = 6 horas             |
              +---------------------------+
                           |
                           v
              +---------------------------+
              | Frontend                  |
              | GET /api/v1/intel/market/ |
              | categories/{id}          |
              +---------------------------+
```

### 3.2 Fluxo: Monitoramento Competitivo

```
    Usuario adiciona concorrente          Celery Beat (diario 07:00 BRT)
    POST /intel/competitors/              |
    {seller_id: "12345"}                  |
           |                              |
           v                              v
    +------------------+       +----------------------+
    | monitored_sellers|       | tasks_competitors_v2 |
    | (PostgreSQL)     |<------| sync_all_competitors |
    +------------------+       +----------+-----------+
                                          |
                          +---------------+---------------+
                          |               |               |
                          v               v               v
                    ML API          ML API          ML API
                    /users/         /items/         /items/{id}/
                    {id}/items      {id}            visits/time_window
                          |               |               |
                          v               v               v
                    +------------------------------------------+
                    | seller_snapshots + competitor_snapshots   |
                    | (PostgreSQL)                              |
                    +--------------------+---------------------+
                                         |
                                         v
                    +------------------------------------------+
                    | Analytics Engine                         |
                    | - Calcula delta de vendas                |
                    | - Compara precos                         |
                    | - Gera alertas se configurado            |
                    +------------------------------------------+
```

### 3.3 Fluxo: Otimizacao de Anuncio (IA)

```
    Usuario clica "Otimizar"             Celery task async
    POST /intel/optimizer/               |
    analyze/{listing_id}                 |
           |                             |
           v                             v
    +------------------+       +----------------------+
    | Coleta contexto  |       | service_scoring.py   |
    | - listing data   |       | Calcula score base   |
    | - snapshots 30d  |       | (10 criterios)       |
    | - category rank  |       +----------+-----------+
    | - keywords top   |                  |
    | - competitors    |                  v
    +--------+---------+       +----------------------+
             |                 | service_titles.py    |
             |                 | Keywords da categoria|
             |                 | + titulo atual       |
             |                 +----------+-----------+
             |                            |
             +----------------------------+
                          |
                          v
               +----------------------+
               | Claude API           |
               | (Haiku para score,   |
               |  Sonnet para titulo) |
               +----------+-----------+
                          |
                          v
               +----------------------+
               | optimization_reports |
               | title_suggestions    |
               | (PostgreSQL)         |
               +----------+-----------+
                          |
                          v
               +----------------------+
               | Frontend             |
               | Mostra score, gaps,  |
               | sugestoes de titulo, |
               | botao "Aplicar"      |
               +----------------------+
```

### 3.4 Fluxo: Projecao de Vendas (Analytics)

```
    GET /intel/analytics/forecast/{listing_id}?days=30
                          |
                          v
               +----------------------+
               | Redis Cache check    |
               | intel:forecast:{id}  |
               | TTL = 4 horas        |
               +----------+-----------+
                     |           |
                   HIT         MISS
                     |           |
                     v           v
               Retorna      +----------------------+
               cache        | service_forecast.py  |
                            | 1. Busca snapshots   |
                            |    ultimos 90 dias   |
                            | 2. Linear regression |
                            |    + moving average  |
                            | 3. Ajuste sazonal    |
                            +----------+-----------+
                                       |
                                       v
                            +----------------------+
                            | Resultado:           |
                            | - trend_direction    |
                            | - forecast_30d       |
                            | - confidence_pct     |
                            | - seasonal_factor    |
                            +----------+-----------+
                                       |
                                       v
                            Salva em Redis + retorna
```

---

## 4. SCHEMA DE BANCO DE DADOS (ADICOES)

### 4.1 Diagrama Entidade-Relacionamento (Novas Tabelas)

```
TABELAS EXISTENTES (referencia)          NOVAS TABELAS
================================         ================================

+-------------+                          +---------------------+
| users       |---+                      | ml_categories       |
+-------------+   |                      |---------------------|
                   |                      | id (PK, VARCHAR)    |
+-------------+   |                      | parent_id (FK self) |
| ml_accounts |---+                      | name                |
+-------------+   |                      | path_from_root      |
                   |                      | total_items_qty     |
+-------------+   |                      | updated_at          |
| listings    |---+                      +---------------------+
+-------------+   |                             |
      |           |                      +------v--------------+
      |           |                      | category_snapshots  |
+-----v-------+   |                      |-----------------------|
| listing_    |   |                      | id (PK, UUID)       |
| snapshots   |   |                      | category_id (FK)    |
+-------------+   |                      | avg_price           |
                   |                      | total_sold_qty      |
+-------------+   |                      | active_listings_count|
| competitors |   |                      | avg_days_to_sell    |
+-------------+   |                      | top_seller_share_pct|
      |           |                      | captured_at         |
+-----v-------+   |                      +---------------------+
| competitor_ |   |
| snapshots   |   |                      +---------------------+
+-------------+   |                      | keyword_rankings    |
                   |                      |---------------------|
+-------------+   |                      | id (PK, UUID)       |
| products    |---+                      | category_id (FK)    |
+-------------+   |                      | keyword             |
                   |                      | search_volume       |
+-------------+   |                      | position            |
| alert_      |   |                      | trend (up/down/flat)|
| configs     |   |                      | captured_at         |
+-------------+   |                      +---------------------+
                   |
                   |                      +---------------------+
                   |                      | monitored_sellers   |
                   |                      |---------------------|
                   +--------------------->| id (PK, UUID)       |
                                          | user_id (FK users)  |
                                          | ml_seller_id        |
                                          | nickname            |
                                          | alias               |
                                          | seller_type         |
                                          | is_active           |
                                          | created_at          |
                                          +---------------------+
                                                 |
                                          +------v--------------+
                                          | seller_snapshots    |
                                          |-----------------------|
                                          | id (PK, UUID)       |
                                          | seller_id (FK)      |
                                          | total_listings      |
                                          | total_sold_qty      |
                                          | avg_price           |
                                          | reputation_level    |
                                          | captured_at         |
                                          +---------------------+

                                          +---------------------+
                                          | optimization_reports|
                                          |---------------------|
                                          | id (PK, UUID)       |
                                          | listing_id (FK)     |
                                          | user_id (FK)        |
                                          | overall_score (0-100)|
                                          | title_score         |
                                          | price_score         |
                                          | category_score      |
                                          | description_score   |
                                          | photo_score         |
                                          | gaps (JSONB)        |
                                          | recommendations     |
                                          |   (JSONB)           |
                                          | created_at          |
                                          +---------------------+

                                          +---------------------+
                                          | title_suggestions   |
                                          |---------------------|
                                          | id (PK, UUID)       |
                                          | listing_id (FK)     |
                                          | original_title      |
                                          | suggested_title     |
                                          | keywords_used       |
                                          |   (JSONB)           |
                                          | expected_impact     |
                                          | applied (BOOL)      |
                                          | applied_at          |
                                          | created_at          |
                                          +---------------------+

                                          +---------------------+
                                          | demand_opportunities|
                                          |---------------------|
                                          | id (PK, UUID)       |
                                          | user_id (FK)        |
                                          | category_id (FK)    |
                                          | keyword             |
                                          | search_volume       |
                                          | supply_count        |
                                          | demand_supply_ratio |
                                          | avg_price           |
                                          | opportunity_score   |
                                          | created_at          |
                                          +---------------------+

                                          +---------------------+
                                          | analytics_cache     |
                                          |---------------------|
                                          | id (PK, UUID)       |
                                          | user_id (FK)        |
                                          | cache_key           |
                                          | cache_value (JSONB) |
                                          | expires_at          |
                                          | created_at          |
                                          +---------------------+
```

### 4.2 DDL Detalhado (Novas Tabelas)

```sql
-- =====================================================
-- MARKET INTELLIGENCE
-- =====================================================

CREATE TABLE ml_categories (
    id              VARCHAR(50) PRIMARY KEY,  -- ML category ID (ex: "MLB1051")
    parent_id       VARCHAR(50) REFERENCES ml_categories(id),
    name            VARCHAR(500) NOT NULL,
    path_from_root  TEXT,                     -- "Eletronicos > Celulares > Smartphones"
    total_items_qty INTEGER DEFAULT 0,
    settings        JSONB DEFAULT '{}',       -- children_categories, currency, etc.
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_categories_parent ON ml_categories(parent_id);

CREATE TABLE category_snapshots (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id             VARCHAR(50) NOT NULL REFERENCES ml_categories(id) ON DELETE CASCADE,
    avg_price               NUMERIC(12,2),
    median_price            NUMERIC(12,2),
    total_sold_qty          INTEGER DEFAULT 0,
    active_listings_count   INTEGER DEFAULT 0,
    new_listings_count      INTEGER DEFAULT 0,
    avg_days_to_sell        NUMERIC(8,2),
    top_seller_share_pct    NUMERIC(5,2),       -- % do top 1 seller
    top10_seller_share_pct  NUMERIC(5,2),       -- % dos top 10 sellers
    captured_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_cat_snap_category ON category_snapshots(category_id);
CREATE INDEX idx_cat_snap_captured ON category_snapshots(captured_at);

CREATE TABLE keyword_rankings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id     VARCHAR(50) NOT NULL REFERENCES ml_categories(id) ON DELETE CASCADE,
    keyword         VARCHAR(500) NOT NULL,
    search_volume   INTEGER DEFAULT 0,       -- estimativa de volume
    position        INTEGER NOT NULL,         -- rank na categoria
    trend           VARCHAR(10) DEFAULT 'flat',  -- up | down | flat
    results_count   INTEGER DEFAULT 0,        -- quantos resultados retorna
    captured_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_kw_category ON keyword_rankings(category_id);
CREATE INDEX idx_kw_captured ON keyword_rankings(captured_at);
CREATE INDEX idx_kw_keyword ON keyword_rankings(keyword);

CREATE TABLE demand_opportunities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id         VARCHAR(50) NOT NULL REFERENCES ml_categories(id) ON DELETE CASCADE,
    keyword             VARCHAR(500) NOT NULL,
    search_volume       INTEGER DEFAULT 0,
    supply_count        INTEGER DEFAULT 0,       -- quantos anuncios competem
    demand_supply_ratio NUMERIC(10,4),            -- volume / supply
    avg_price           NUMERIC(12,2),
    avg_sold_qty        INTEGER DEFAULT 0,
    opportunity_score   NUMERIC(5,2) DEFAULT 0,   -- 0-100
    status              VARCHAR(20) DEFAULT 'new', -- new | reviewed | dismissed
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_demand_opp_user ON demand_opportunities(user_id);
CREATE INDEX idx_demand_opp_score ON demand_opportunities(opportunity_score DESC);

-- =====================================================
-- COMPETITIVE INTELLIGENCE
-- =====================================================

CREATE TABLE monitored_sellers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ml_seller_id    VARCHAR(50) NOT NULL,
    nickname        VARCHAR(255),
    alias           VARCHAR(255),           -- nome amigavel dado pelo usuario
    seller_type     VARCHAR(30) DEFAULT 'normal',  -- normal | official_store | platinum
    reputation_level VARCHAR(30),
    is_active       BOOLEAN DEFAULT TRUE NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    UNIQUE(user_id, ml_seller_id)
);
CREATE INDEX idx_mon_sellers_user ON monitored_sellers(user_id);

CREATE TABLE seller_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id           UUID NOT NULL REFERENCES monitored_sellers(id) ON DELETE CASCADE,
    total_listings      INTEGER DEFAULT 0,
    active_listings     INTEGER DEFAULT 0,
    total_sold_qty      INTEGER DEFAULT 0,      -- sold_quantity acumulado
    estimated_revenue   NUMERIC(14,2) DEFAULT 0,
    avg_price           NUMERIC(12,2),
    reputation_score    NUMERIC(5,2),
    reputation_level    VARCHAR(30),
    captured_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_seller_snap_seller ON seller_snapshots(seller_id);
CREATE INDEX idx_seller_snap_captured ON seller_snapshots(captured_at);

-- =====================================================
-- AI OPTIMIZATION ENGINE
-- =====================================================

CREATE TABLE optimization_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id          UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    overall_score       INTEGER NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    title_score         INTEGER CHECK (title_score BETWEEN 0 AND 100),
    price_score         INTEGER CHECK (price_score BETWEEN 0 AND 100),
    category_score      INTEGER CHECK (category_score BETWEEN 0 AND 100),
    description_score   INTEGER CHECK (description_score BETWEEN 0 AND 100),
    photo_score         INTEGER CHECK (photo_score BETWEEN 0 AND 100),
    visibility_score    INTEGER CHECK (visibility_score BETWEEN 0 AND 100),
    gaps                JSONB DEFAULT '[]',       -- lista de gaps encontrados
    recommendations     JSONB DEFAULT '[]',       -- lista de recomendacoes
    ai_model_used       VARCHAR(50),              -- haiku-3 | sonnet-4 etc
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_opt_report_listing ON optimization_reports(listing_id);
CREATE INDEX idx_opt_report_user ON optimization_reports(user_id);

CREATE TABLE title_suggestions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id          UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    report_id           UUID REFERENCES optimization_reports(id) ON DELETE SET NULL,
    original_title      VARCHAR(500) NOT NULL,
    suggested_title     VARCHAR(500) NOT NULL,
    keywords_used       JSONB DEFAULT '[]',
    expected_impact     VARCHAR(20) DEFAULT 'medium', -- low | medium | high
    reasoning           TEXT,
    applied             BOOLEAN DEFAULT FALSE NOT NULL,
    applied_at          TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_title_sug_listing ON title_suggestions(listing_id);

-- =====================================================
-- ANALYTICS ENGINE
-- =====================================================

CREATE TABLE analytics_cache (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cache_key       VARCHAR(255) NOT NULL,
    cache_value     JSONB NOT NULL,
    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    UNIQUE(user_id, cache_key)
);
CREATE INDEX idx_analytics_cache_key ON analytics_cache(user_id, cache_key);
CREATE INDEX idx_analytics_cache_expires ON analytics_cache(expires_at);

CREATE TABLE user_insights (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    insight_type    VARCHAR(50) NOT NULL,   -- pareto | forecast | seasonality | opportunity
    payload         JSONB NOT NULL,
    priority        VARCHAR(10) DEFAULT 'medium',
    is_read         BOOLEAN DEFAULT FALSE,
    generated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_insights_user ON user_insights(user_id);
CREATE INDEX idx_insights_type ON user_insights(insight_type);
```

### 4.3 Alteracoes em Tabelas Existentes

```sql
-- Adicionar campos ao listings para suportar intel
ALTER TABLE listings ADD COLUMN IF NOT EXISTS
    search_position INTEGER;                     -- posicao no ranking de busca da categoria
ALTER TABLE listings ADD COLUMN IF NOT EXISTS
    health_score INTEGER;                        -- score 0-100 do otimizador
ALTER TABLE listings ADD COLUMN IF NOT EXISTS
    last_optimized_at TIMESTAMP WITH TIME ZONE;  -- quando foi otimizado por ultimo

-- Adicionar campo ao listing_snapshots para posicao
ALTER TABLE listing_snapshots ADD COLUMN IF NOT EXISTS
    search_position INTEGER;                     -- posicao no resultado de busca
ALTER TABLE listing_snapshots ADD COLUMN IF NOT EXISTS
    category_rank INTEGER;                       -- rank dentro da categoria
```

---

## 5. DESIGN DE API (Novos Endpoints)

### 5.1 Market Intelligence — `/api/v1/intel/market`

```
GET  /categories                         Lista categorias raiz do ML Brasil
GET  /categories/{category_id}           Detalhes + subcategorias
GET  /categories/{category_id}/tree      Arvore completa ate folha
GET  /categories/{category_id}/stats     Estatisticas da categoria (snapshots)
GET  /categories/{category_id}/trends    Evolucao 12 meses (vendas, precos, sellers)
GET  /categories/{category_id}/keywords  Ranking de palavras-chave
GET  /categories/{category_id}/top-items Top itens vendidos
GET  /categories/{category_id}/opportunity Score de oportunidade

GET  /keywords/search?q={term}           Buscar keyword e ver volume
GET  /keywords/trending                  Keywords em alta (cross-category)

GET  /demand/opportunities               Oportunidades para o usuario (demanda insatisfeita)
POST /demand/opportunities/{id}/dismiss  Dispensar oportunidade
```

**Paginacao**: Todos os endpoints de lista usam `?page=1&per_page=20`.
**Cache**: Resultados de `/categories/*` cached por 6h no Redis.

### 5.2 Competitive Intelligence — `/api/v1/intel/competitors`

```
GET    /sellers                          Lista sellers monitorados pelo usuario
POST   /sellers                          Adicionar seller para monitorar
DELETE /sellers/{id}                      Remover seller do monitoramento
PATCH  /sellers/{id}                     Atualizar alias/status

GET    /sellers/{id}/dashboard           Dashboard consolidado do seller
GET    /sellers/{id}/snapshots           Historico de snapshots do seller
GET    /sellers/{id}/items               Anuncios do seller monitorado
GET    /sellers/{id}/pareto              Analise Pareto 80/20 do seller

GET    /compare                          Comparacao: meu preco vs concorrentes
                                         ?listing_id={uuid}&competitor_ids={csv}
GET    /discover                         Motor de descoberta automatica
                                         ?category_id={id}&limit=10

GET    /price-alerts                     Alertas de variacao de preco de concorrentes
```

**Limites**: Max 20 sellers monitorados por usuario (plano free). Max 120 anuncios tracked.

### 5.3 AI Optimization Engine — `/api/v1/intel/optimizer`

```
POST   /analyze/{listing_id}             Gera relatorio de otimizacao (async, retorna task_id)
GET    /analyze/{listing_id}/status      Status da analise (polling)
GET    /reports/{listing_id}             Ultimo relatorio de otimizacao
GET    /reports/{listing_id}/history     Historico de relatorios

GET    /titles/{listing_id}/suggestions  Sugestoes de titulo
POST   /titles/{listing_id}/apply        Aplicar titulo sugerido no ML

GET    /pricing/{listing_id}/suggestion  Sugestao de preco ideal
GET    /pricing/{listing_id}/analysis    Analise detalhada de precificacao

GET    /bulk-score                       Score de todos os anuncios do usuario
                                         (retorna lista com health_score)
```

**Rate limit IA**: Max 10 analises/hora por usuario (custo Anthropic API).

### 5.4 Analytics Engine — `/api/v1/intel/analytics`

```
GET  /pareto                             Analise Pareto 80/20 do usuario
                                         ?metric=revenue|quantity&period=30d
GET  /forecast/{listing_id}              Projecao de vendas por anuncio
                                         ?days=30
GET  /forecast/total                     Projecao total do usuario
GET  /seasonality/{category_id}          Analise de sazonalidade da categoria
GET  /distribution                       Distribuicao de vendas por anuncio
                                         ?period=7d|30d|90d

GET  /insights                           Insights gerados para o usuario
POST /insights/{id}/read                 Marcar insight como lido

GET  /export/listings                    Exportar anuncios (CSV)
GET  /export/sales                       Exportar vendas (CSV)
GET  /export/competitors                 Exportar dados de concorrentes (CSV)
```

### 5.5 Padrao de Response

Todos os endpoints seguem o padrao existente do MSM_Pro:

```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

Para endpoints async (IA):

```json
{
  "task_id": "uuid-da-task",
  "status": "processing",
  "estimated_seconds": 15
}
```

---

## 6. HIERARQUIA DE COMPONENTES FRONTEND

### 6.1 Novas Paginas

```
frontend/src/pages/
|
+-- Intel/                              <-- NOVO: Namespace para inteligencia
|   +-- index.tsx                       Hub central de inteligencia (overview)
|   |
|   +-- Market/
|   |   +-- index.tsx                   Pagina principal Market Intel
|   |   +-- CategoryExplorer.tsx        Explorador de categorias (drill-down)
|   |   +-- CategoryDetail.tsx          Detalhes da categoria (stats + trends)
|   |   +-- KeywordRankings.tsx         Rankings de palavras-chave
|   |   +-- DemandOpportunities.tsx     Oportunidades de demanda insatisfeita
|   |
|   +-- Competitors/
|   |   +-- index.tsx                   Pagina principal Concorrencia
|   |   +-- SellerDashboard.tsx         Dashboard de um seller especifico
|   |   +-- SellerComparison.tsx        Comparacao lado-a-lado
|   |   +-- PriceComparison.tsx         Grafico de precos meu vs concorrente
|   |   +-- AddSellerModal.tsx          Modal para adicionar seller
|   |
|   +-- Optimizer/
|   |   +-- index.tsx                   Pagina principal do otimizador
|   |   +-- ListingScore.tsx            Score de um anuncio especifico
|   |   +-- TitleOptimizer.tsx          Otimizacao de titulo (com preview)
|   |   +-- PriceSuggestion.tsx         Sugestao de preco
|   |   +-- BulkScoreTable.tsx          Tabela de scores de todos anuncios
|   |
|   +-- Analytics/
|       +-- index.tsx                   Pagina principal Analytics
|       +-- ParetoChart.tsx             Grafico Pareto 80/20
|       +-- SalesForecast.tsx           Projecao de vendas (grafico + tabela)
|       +-- SeasonalityView.tsx         Visualizacao de sazonalidade
|       +-- SalesDistribution.tsx       Distribuicao por anuncio
|       +-- InsightsPanel.tsx           Painel de insights gerados
```

### 6.2 Novos Componentes Reutilizaveis

```
frontend/src/components/
|
+-- intel/                              <-- NOVO: Componentes de inteligencia
|   +-- CategoryBreadcrumb.tsx          Breadcrumb de categorias (drill-down)
|   +-- TrendBadge.tsx                  Badge de tendencia (up/down/flat)
|   +-- ScoreGauge.tsx                  Gauge visual de score (0-100)
|   +-- CompetitorCard.tsx              Card de resumo de concorrente
|   +-- OpportunityCard.tsx             Card de oportunidade
|   +-- InsightCard.tsx                 Card de insight gerado
|   +-- MetricDelta.tsx                 Componente de delta (ex: +15% verde, -3% vermelho)
|   +-- DateRangePicker.tsx             Seletor de periodo (7d, 30d, 90d, custom)
|   +-- ExportButton.tsx                Botao de exportacao CSV
|   +-- AsyncTaskStatus.tsx             Indicador de status de task async
```

### 6.3 Novos Services (API Client)

```
frontend/src/services/
|
+-- intel/                              <-- NOVO
|   +-- marketService.ts                Chamadas para /intel/market/*
|   +-- competitorService.ts            Chamadas para /intel/competitors/*
|   +-- optimizerService.ts             Chamadas para /intel/optimizer/*
|   +-- analyticsService.ts             Chamadas para /intel/analytics/*
```

### 6.4 Novos Hooks

```
frontend/src/hooks/
|
+-- intel/                              <-- NOVO
|   +-- useCategories.ts                React Query hook para categorias
|   +-- useCategoryStats.ts             Stats de uma categoria
|   +-- useKeywords.ts                  Keywords de uma categoria
|   +-- useMonitoredSellers.ts          Lista de sellers monitorados
|   +-- useSellerDashboard.ts           Dashboard de um seller
|   +-- useOptimizationReport.ts        Relatorio de otimizacao
|   +-- usePareto.ts                    Dados do Pareto
|   +-- useForecast.ts                  Projecao de vendas
|   +-- useInsights.ts                  Insights do usuario
```

### 6.5 Navegacao Atualizada

```
Sidebar (existente)                     Adicoes
====================                    ====================
Dashboard                               |
Anuncios                                |
Pedidos                                 |
Financeiro                              |
Concorrencia                            --> migra para Intel > Competitors
Alertas                                 |
Reputacao                               |
Configuracoes                           |
                                        |
                                        +-- Inteligencia (novo)
                                        |   +-- Visao Geral
                                        |   +-- Mercado
                                        |   +-- Concorrentes
                                        |   +-- Otimizador (IA)
                                        |   +-- Analytics
```

---

## 7. DESIGN DE BACKGROUND JOBS (Celery)

### 7.1 Novos Beat Schedules

```python
# core/celery_app.py — adicoes ao beat_schedule

CELERY_BEAT_SCHEDULE = {
    # ... schedules existentes ...

    # MARKET INTEL
    "sync-category-tree": {
        "task": "app.jobs.tasks_market.sync_category_tree",
        "schedule": crontab(hour=2, minute=0),   # 02:00 BRT (diario)
        "options": {"queue": "intel"},
    },
    "sync-category-snapshots": {
        "task": "app.jobs.tasks_market.sync_category_snapshots",
        "schedule": crontab(hour=3, minute=0),   # 03:00 BRT (diario)
        "options": {"queue": "intel"},
    },
    "sync-keyword-rankings": {
        "task": "app.jobs.tasks_market.sync_keyword_rankings",
        "schedule": crontab(hour=4, minute=0),   # 04:00 BRT (diario)
        "options": {"queue": "intel"},
    },
    "detect-demand-opportunities": {
        "task": "app.jobs.tasks_market.detect_demand_opportunities",
        "schedule": crontab(hour=5, minute=0, day_of_week=1),  # Segunda 05:00
        "options": {"queue": "intel"},
    },

    # COMPETITIVE INTEL
    "sync-monitored-sellers": {
        "task": "app.jobs.tasks_competitors_v2.sync_all_monitored_sellers",
        "schedule": crontab(hour=7, minute=0),   # 07:00 BRT (diario, apos sync proprio)
        "options": {"queue": "intel"},
    },

    # ANALYTICS
    "generate-daily-insights": {
        "task": "app.jobs.tasks_analytics.generate_daily_insights",
        "schedule": crontab(hour=8, minute=0),   # 08:00 BRT (apos todos os syncs)
        "options": {"queue": "analytics"},
    },
    "cleanup-analytics-cache": {
        "task": "app.jobs.tasks_analytics.cleanup_expired_cache",
        "schedule": crontab(hour=1, minute=0),   # 01:00 BRT
        "options": {"queue": "analytics"},
    },
}
```

### 7.2 Detalhamento de Tasks

| Task | Tipo | Duracao Estimada | Rate Limit | Queue |
|------|------|-----------------|------------|-------|
| `sync_category_tree` | Periodica (diaria) | 2-5 min | 1 req/s ML | intel |
| `sync_category_snapshots` | Periodica (diaria) | 10-30 min | 1 req/s ML | intel |
| `sync_keyword_rankings` | Periodica (diaria) | 5-15 min | 1 req/s ML | intel |
| `detect_demand_opportunities` | Periodica (semanal) | 5-10 min | Dados proprios | intel |
| `sync_all_monitored_sellers` | Periodica (diaria) | 5-20 min | 1 req/s ML | intel |
| `sync_single_seller` | Sub-task (fanout) | 1-3 min | 1 req/s ML | intel |
| `generate_optimization_report` | On-demand (usuario) | 10-30s | 10/hora/user | optimizer |
| `generate_daily_insights` | Periodica (diaria) | 2-5 min | Dados proprios | analytics |
| `cleanup_expired_cache` | Periodica (diaria) | <1 min | Dados proprios | analytics |

### 7.3 Queues de Celery

```python
# Nova configuracao de queues
CELERY_TASK_ROUTES = {
    "app.jobs.tasks_market.*": {"queue": "intel"},
    "app.jobs.tasks_competitors_v2.*": {"queue": "intel"},
    "app.jobs.tasks_optimizer.*": {"queue": "optimizer"},
    "app.jobs.tasks_analytics.*": {"queue": "analytics"},
    # tasks existentes continuam na queue "default"
}
```

**Justificativa**: Separar queues permite escalar workers independentemente. A queue `intel`
faz chamadas externas a ML API (I/O bound); a queue `optimizer` usa Claude API (I/O bound com
custo); a queue `analytics` e CPU-bound (calculos sobre dados proprios).

### 7.4 Orquestacao de Timeline Diario

```
01:00  cleanup_expired_cache          (limpa cache velho)
02:00  sync_category_tree             (atualiza arvore de categorias)
03:00  sync_category_snapshots        (coleta stats de categorias monitoradas)
04:00  sync_keyword_rankings          (atualiza ranking de keywords)
05:00  detect_demand_opportunities    (apenas segunda-feira)
06:00  sync_all_snapshots             (EXISTENTE - sync dos proprios listings)
07:00  sync_all_monitored_sellers     (sync de concorrentes)
08:00  generate_daily_insights        (gera insights com todos dados frescos)
```

---

## 8. ESTRATEGIA DE CACHE (Redis)

### 8.1 Namespaces de Cache

```
Redis Key Pattern                        TTL       Tipo
=======================================  ========  ============
intel:market:cat:{category_id}           6h        JSON (stats)
intel:market:cat:{category_id}:tree      24h       JSON (tree)
intel:market:cat:{category_id}:keywords  6h        JSON (list)
intel:market:cat:{category_id}:top       6h        JSON (list)
intel:market:trending_keywords           4h        JSON (list)

intel:comp:seller:{seller_id}            4h        JSON (dashboard)
intel:comp:compare:{hash}                2h        JSON (comparison)

intel:opt:score:{listing_id}             12h       JSON (score)
intel:opt:report:{listing_id}            24h       JSON (full report)

intel:analytics:pareto:{user_id}:{period} 4h      JSON (pareto)
intel:analytics:forecast:{listing_id}    4h        JSON (forecast)
intel:analytics:distribution:{user_id}   4h        JSON (distribution)

intel:ratelimit:ml_api:{minute}          60s       Counter
intel:ratelimit:claude:{user_id}         3600s     Counter
```

### 8.2 Cache Invalidation Strategy

| Evento | Caches Invalidados |
|--------|-------------------|
| Novo snapshot coletado | `intel:analytics:pareto:*`, `intel:analytics:forecast:{listing}` |
| Seller monitorado atualizado | `intel:comp:seller:{id}`, `intel:comp:compare:*` |
| Category snapshot coletado | `intel:market:cat:{id}`, `intel:market:cat:{id}:keywords` |
| Optimization report gerado | `intel:opt:score:{listing}`, `intel:opt:report:{listing}` |
| Titulo alterado no ML | `intel:opt:score:{listing}` |

### 8.3 Implementacao do Cache Decorator

```python
# intel/common/cache.py

from functools import wraps
from typing import Callable
import json
import hashlib

from app.core.config import settings
import redis.asyncio as redis

_redis = redis.from_url(settings.REDIS_URL)

def intel_cache(prefix: str, ttl_seconds: int = 3600):
    """
    Decorator para cachear resultados de funcoes async no Redis.

    Uso:
        @intel_cache("intel:market:cat", ttl_seconds=21600)
        async def get_category_stats(category_id: str) -> dict:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Gerar chave de cache baseada nos argumentos
            key_parts = [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            key_hash = hashlib.md5(":".join(key_parts).encode()).hexdigest()[:12]
            cache_key = f"{prefix}:{key_hash}"

            # Tentar ler do cache
            cached = await _redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Executar funcao e cachear resultado
            result = await func(*args, **kwargs)
            if result is not None:
                await _redis.setex(cache_key, ttl_seconds, json.dumps(result, default=str))
            return result
        return wrapper
    return decorator
```

---

## 9. ENDPOINTS DA ML API NECESSARIOS

### 9.1 Endpoints Novos (nao usados atualmente no MSM_Pro)

| Endpoint ML | Modulo Intel | Proposito |
|-------------|-------------|-----------|
| `GET /sites/MLB/categories` | Market | Arvore raiz de categorias |
| `GET /categories/{id}` | Market | Detalhes de uma categoria |
| `GET /categories/{id}/attributes` | Market | Atributos da categoria |
| `GET /sites/MLB/search?category={id}` | Market | Buscar itens da categoria |
| `GET /trends/MLB/search?category={id}` | Market | Tendencias de busca |
| `GET /trends/MLB/{category_id}` | Market | Tendencias da categoria |
| `GET /highlights/MLB/{category_id}` | Market | Destaques da categoria |
| `GET /users/{seller_id}` | Competitors | Info do seller concorrente |
| `GET /users/{seller_id}/items/search` | Competitors | Anuncios do concorrente |
| `GET /sites/MLB/search?q={keyword}` | Market/Keywords | Volume de busca estimado |
| `GET /items/{id}/description` | Optimizer | Descricao para analise IA |

### 9.2 Metodos a Adicionar em `client.py`

```python
# Novos metodos no MLClient

async def get_site_categories(self) -> list[dict]:
    """GET /sites/MLB/categories — arvore raiz"""

async def get_category(self, category_id: str) -> dict:
    """GET /categories/{category_id} — detalhes"""

async def get_category_attributes(self, category_id: str) -> list[dict]:
    """GET /categories/{category_id}/attributes"""

async def search_category(self, category_id: str, offset: int = 0, limit: int = 50) -> dict:
    """GET /sites/MLB/search?category={id}&offset=&limit="""

async def get_trends(self, category_id: str) -> dict:
    """GET /trends/MLB/search?category={id}"""

async def get_category_trends(self, category_id: str) -> dict:
    """GET /trends/MLB/{category_id}"""

async def search_query(self, query: str, category_id: str = None, limit: int = 50) -> dict:
    """GET /sites/MLB/search?q={query}&category={cat}"""

async def get_seller_info(self, seller_id: str) -> dict:
    """GET /users/{seller_id}"""

async def get_seller_items(self, seller_id: str, offset: int = 0) -> dict:
    """GET /users/{seller_id}/items/search?status=active"""

async def get_item_description(self, item_id: str) -> dict:
    """GET /items/{item_id}/description"""
```

---

## 10. SEGURANCA

### 10.1 Principios

- **Todo endpoint intel requer JWT** — nao ha acesso publico
- **Anthropic API key em variavel de ambiente** — nunca em codigo
- **Rate limiting por usuario** — evita abuso de IA e ML API
- **Dados de concorrentes sao do usuario** — multi-tenant isolado por user_id
- **Logs de IA nao armazenam dados sensiveis** — prompts sao templates, nao dados

### 10.2 Novas Variaveis de Ambiente

```env
# IA (Anthropic)
ANTHROPIC_API_KEY=                        # Chave da API Claude
ANTHROPIC_MODEL_SCORING=claude-3-haiku    # Modelo para scoring (barato)
ANTHROPIC_MODEL_OPTIMIZATION=claude-sonnet-4-20250514  # Modelo para otimizacao (preciso)
ANTHROPIC_MAX_REQUESTS_PER_HOUR=100       # Rate limit global

# Intel
INTEL_MAX_MONITORED_SELLERS=20            # Limite de sellers por usuario
INTEL_MAX_TRACKED_ITEMS=120               # Limite de items de concorrentes
INTEL_CACHE_TTL_CATEGORIES=21600          # 6h em segundos
INTEL_CACHE_TTL_FORECASTS=14400           # 4h em segundos
INTEL_OPTIMIZATION_COOLDOWN=3600          # 1h entre otimizacoes do mesmo listing
```

---

## 11. ESTIMATIVAS DE VOLUME

### 11.1 Dados Armazenados (estimativa para 1 usuario com 20 sellers monitorados)

| Tabela | Registros/dia | Registros/mes | Registros/ano |
|--------|-------------|-------------|-------------|
| `category_snapshots` | ~50 | ~1.500 | ~18.000 |
| `keyword_rankings` | ~500 | ~15.000 | ~180.000 |
| `seller_snapshots` | ~20 | ~600 | ~7.200 |
| `optimization_reports` | ~5 | ~150 | ~1.800 |
| `demand_opportunities` | ~10/semana | ~40 | ~500 |
| `user_insights` | ~3 | ~90 | ~1.080 |
| `analytics_cache` | (auto-limpeza) | ~200 max | ~200 max |

**Total incremental**: ~600 registros/dia por usuario ativo.
Para 10 usuarios ativos: ~6.000 registros/dia = ~2.2M registros/ano.

### 11.2 Chamadas a ML API (estimativa diaria por usuario)

| Acao | Chamadas/dia |
|------|-------------|
| Sync categorias monitoradas (~50 cats) | ~55 |
| Sync keywords (~50 cats x 1) | ~50 |
| Sync sellers (20 sellers x 3 endpoints) | ~60 |
| Sync items concorrentes (120 items) | ~120 |
| Buscas on-demand (usuario navegando) | ~30 |
| **Total** | **~315 chamadas/dia** |

Com rate limit de 1 req/s, isso exige ~5 minutos de coleta pura.

---

## 12. DECISOES ARQUITETURAIS REGISTRADAS (ADR)

### ADR-001: Modulos intel como subpackage do backend existente

**Decisao**: Os modulos de inteligencia ficam em `backend/app/intel/` como subpackage
do monolito FastAPI existente, nao como microsservico separado.

**Justificativa**: O MSM_Pro tem 1 usuario ativo e deploy Railway com container unico.
Microsservicos adicionariam complexidade de rede, deploy e observabilidade sem ganho proporcional.
Quando o volume justificar, o namespace `intel/` esta pronto para ser extraido.

### ADR-002: Claude Haiku para scoring, Sonnet para otimizacao

**Decisao**: Usar Haiku para tarefas de classificacao/scoring (barato, rapido) e Sonnet
para geracao de titulos e recomendacoes (mais preciso).

**Justificativa**: Scoring de anuncio e um problema de classificacao que Haiku resolve bem
a ~$0.25/1M tokens. Geracao de titulo exige criatividade e contexto que Sonnet fornece
a ~$3/1M tokens. Opus seria overkill para ambos os casos.

### ADR-003: Cache agressivo em Redis para dados de mercado

**Decisao**: Cachear dados de mercado por 4-24h no Redis, nao consultar ML API em tempo real.

**Justificativa**: Dados de categorias e rankings mudam no maximo 1x/dia. Cache reduz
chamadas a ML API em ~90%, evita rate limiting, e garante respostas <100ms para o frontend.

### ADR-004: Celery queues separadas por tipo de workload

**Decisao**: Tres queues: `intel` (I/O ML API), `optimizer` (I/O Claude API), `analytics` (CPU).

**Justificativa**: Permite escalar workers por tipo. Se a queue de intel estiver lenta
(ML API com rate limit), nao bloqueia analytics. Se Claude API estiver indisponivel,
coleta de dados continua normalmente.

### ADR-005: PostgreSQL JSONB para dados semi-estruturados

**Decisao**: Usar JSONB para gaps, recommendations, keywords_used em vez de tabelas normalizadas.

**Justificativa**: Esses dados sao gerados por IA e variam entre execucoes. Normalizar
exigiria schema migration frequente. JSONB permite flexibilidade sem sacrificar queries
(PostgreSQL indexa JSONB com GIN indexes).

---

## 13. METRICAS E OBSERVABILIDADE

### 13.1 Health Checks

```
GET /health                     (existente)
GET /health/intel               Novo - status dos modulos intel
    {
      "market": {"last_sync": "2026-03-18T03:00:00Z", "status": "healthy"},
      "competitors": {"last_sync": "2026-03-18T07:00:00Z", "status": "healthy"},
      "optimizer": {"queue_depth": 2, "status": "healthy"},
      "analytics": {"cache_size": 142, "status": "healthy"}
    }
```

### 13.2 Metricas Chave

- **Latencia de API**: P50 < 200ms, P99 < 2s (endpoints cached)
- **Latencia de otimizacao**: P50 < 15s, P99 < 45s (inclui Claude API)
- **Taxa de cache hit**: > 80% para dados de mercado
- **Chamadas ML API/dia**: < 500 por usuario
- **Erros de sync**: < 5% de tasks falhando

---

*Fim do Blueprint de Arquitetura*
