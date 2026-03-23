# ESTRUTURA DO SUBPROJETO — Nubimetrics Intel

> Versao: 1.0
> Data: 2026-03-18
> Status: Aprovado
> Autor: Architect Reviewer Agent

---

## 1. ESTRUTURA DE PASTAS COMPLETA

### 1.1 Backend — Novos Arquivos

```
MSM_Pro/
└── backend/
    └── app/
        ├── intel/                              # RAIZ DO SUBPROJETO INTEL
        │   ├── __init__.py                     # Registra routers no FastAPI app
        │   │
        │   ├── market/                         # MODULO: Market Intelligence
        │   │   ├── __init__.py
        │   │   ├── models.py                   # MLCategory, CategorySnapshot, KeywordRanking, DemandOpportunity
        │   │   ├── schemas.py                  # CategoryResponse, KeywordResponse, OpportunityResponse
        │   │   ├── service.py                  # Orquestracao geral do modulo
        │   │   ├── service_categories.py       # Logica de navegacao/drill-down de categorias
        │   │   ├── service_keywords.py         # Coleta e ranking de keywords
        │   │   ├── service_demand.py           # Rankings de demanda, marcas, oportunidades
        │   │   └── router.py                   # Endpoints /api/v1/intel/market/*
        │   │
        │   ├── competitors/                    # MODULO: Competitive Intelligence
        │   │   ├── __init__.py
        │   │   ├── models.py                   # MonitoredSeller, SellerSnapshot
        │   │   ├── schemas.py                  # SellerCreate, SellerDashboard, ComparisonResponse
        │   │   ├── service.py                  # CRUD de sellers monitorados
        │   │   ├── service_discovery.py        # Motor de descoberta automatica de concorrentes
        │   │   ├── service_analysis.py         # Analise competitiva: pareto, vendas estimadas
        │   │   └── router.py                   # Endpoints /api/v1/intel/competitors/*
        │   │
        │   ├── optimizer/                      # MODULO: AI Optimization Engine
        │   │   ├── __init__.py
        │   │   ├── models.py                   # OptimizationReport, TitleSuggestion
        │   │   ├── schemas.py                  # ReportResponse, TitleSuggestionResponse
        │   │   ├── service.py                  # Orquestracao do motor de otimizacao
        │   │   ├── service_scoring.py          # Score de saude do anuncio (0-100)
        │   │   ├── service_titles.py           # Geracao de titulos otimizados
        │   │   ├── service_pricing.py          # Sugestao de preco inteligente
        │   │   ├── prompts.py                  # Templates de prompts para Claude
        │   │   └── router.py                   # Endpoints /api/v1/intel/optimizer/*
        │   │
        │   ├── analytics/                      # MODULO: Analytics Engine (transversal)
        │   │   ├── __init__.py
        │   │   ├── models.py                   # AnalyticsCache, UserInsight
        │   │   ├── schemas.py                  # ParetoResponse, ForecastResponse, InsightResponse
        │   │   ├── service.py                  # Orquestracao geral de analytics
        │   │   ├── service_pareto.py           # Analise Pareto 80/20
        │   │   ├── service_forecast.py         # Projecao de vendas (linear regression + MA)
        │   │   ├── service_seasonality.py      # Analise de sazonalidade
        │   │   ├── service_export.py           # Exportacao CSV/Excel (streaming)
        │   │   └── router.py                   # Endpoints /api/v1/intel/analytics/*
        │   │
        │   └── common/                         # UTILIDADES COMPARTILHADAS (intel-only)
        │       ├── __init__.py
        │       ├── ml_api_helpers.py           # Wrappers para endpoints ML usados por intel
        │       ├── cache.py                    # Decorator @intel_cache para Redis
        │       ├── rate_limiter.py             # Rate limiting interno (ML API + Claude)
        │       └── constants.py                # Constantes: TTLs, limites, tipos
        │
        ├── jobs/                               # CELERY TASKS (adicoes)
        │   ├── tasks_market.py                 # sync_category_tree, sync_category_snapshots, etc.
        │   ├── tasks_competitors_v2.py         # sync_all_monitored_sellers, sync_single_seller
        │   ├── tasks_optimizer.py              # generate_optimization_report (on-demand)
        │   └── tasks_analytics.py              # generate_daily_insights, cleanup_expired_cache
        │
        └── mercadolivre/
            └── client.py                       # ALTERACAO: adicionar ~10 novos metodos


MSM_Pro/
└── backend/
    ├── migrations/
    │   └── versions/
    │       ├── 0010_intel_analytics_base.py     # analytics_cache, user_insights
    │       ├── 0011_intel_market_categories.py  # ml_categories, category_snapshots
    │       ├── 0012_intel_market_keywords.py    # keyword_rankings, demand_opportunities
    │       ├── 0013_intel_competitors.py        # monitored_sellers, seller_snapshots
    │       ├── 0014_intel_optimizer.py          # optimization_reports, title_suggestions
    │       └── 0015_intel_listing_fields.py     # ADD search_position, health_score to listings
    │
    └── tests/
        └── intel/                               # TESTES DO SUBPROJETO
            ├── __init__.py
            ├── conftest.py                      # Fixtures compartilhadas (db session, mock ML API)
            ├── test_pareto.py                   # Testes da analise Pareto
            ├── test_forecast.py                 # Testes da projecao de vendas
            ├── test_categories.py               # Testes do explorador de categorias
            ├── test_keywords.py                 # Testes de keywords
            ├── test_competitors.py              # Testes de monitoramento de sellers
            ├── test_scoring.py                  # Testes do score de saude
            ├── test_optimizer.py                # Testes do motor de otimizacao
            └── test_export.py                   # Testes de exportacao CSV
```

### 1.2 Frontend — Novos Arquivos

```
MSM_Pro/
└── frontend/
    └── src/
        ├── pages/
        │   └── Intel/                           # RAIZ DAS PAGINAS INTEL
        │       ├── index.tsx                    # Hub de inteligencia (overview com cards)
        │       │
        │       ├── Market/                      # PAGINAS: Market Intelligence
        │       │   ├── index.tsx                # Pagina principal (entry point)
        │       │   ├── CategoryExplorer.tsx     # Explorador de categorias (tree + drill-down)
        │       │   ├── CategoryDetail.tsx       # Detalhes de uma categoria (stats + trends)
        │       │   ├── KeywordRankings.tsx      # Rankings de keywords por categoria
        │       │   └── DemandOpportunities.tsx  # Lista de oportunidades de demanda
        │       │
        │       ├── Competitors/                 # PAGINAS: Competitive Intelligence
        │       │   ├── index.tsx                # Lista de sellers monitorados
        │       │   ├── SellerDashboard.tsx      # Dashboard de um seller especifico
        │       │   ├── SellerComparison.tsx     # Comparacao lado-a-lado (meu vs dele)
        │       │   ├── PriceComparison.tsx      # Grafico de precos comparativo
        │       │   └── AddSellerModal.tsx       # Modal para adicionar seller
        │       │
        │       ├── Optimizer/                   # PAGINAS: AI Optimization
        │       │   ├── index.tsx                # Visao geral (bulk score table)
        │       │   ├── ListingScore.tsx         # Score detalhado de um anuncio
        │       │   ├── TitleOptimizer.tsx       # Otimizador de titulo (preview + apply)
        │       │   ├── PriceSuggestion.tsx      # Sugestao de preco com slider
        │       │   └── BulkScoreTable.tsx       # Tabela de todos anuncios + score
        │       │
        │       └── Analytics/                   # PAGINAS: Analytics
        │           ├── index.tsx                # Dashboard analytics (overview)
        │           ├── ParetoChart.tsx          # Grafico Pareto 80/20
        │           ├── SalesForecast.tsx        # Projecao de vendas (chart + tabela)
        │           ├── SeasonalityView.tsx      # Visualizacao de sazonalidade (heatmap)
        │           ├── SalesDistribution.tsx    # Distribuicao por anuncio (treemap)
        │           └── InsightsPanel.tsx        # Painel de insights gerados por IA
        │
        ├── components/
        │   └── intel/                           # COMPONENTES REUTILIZAVEIS INTEL
        │       ├── CategoryBreadcrumb.tsx       # Breadcrumb para navegacao de categorias
        │       ├── TrendBadge.tsx               # Badge de tendencia (seta verde/vermelha)
        │       ├── ScoreGauge.tsx               # Gauge circular de score (0-100)
        │       ├── CompetitorCard.tsx           # Card de resumo de concorrente
        │       ├── OpportunityCard.tsx          # Card de oportunidade de mercado
        │       ├── InsightCard.tsx              # Card de insight gerado
        │       ├── MetricDelta.tsx              # Indicador de variacao (+15%, -3%)
        │       ├── DateRangePicker.tsx          # Seletor de periodo (7d, 30d, 90d)
        │       ├── ExportButton.tsx             # Botao de exportacao CSV/Excel
        │       └── AsyncTaskStatus.tsx          # Indicador de progresso de task async
        │
        ├── services/
        │   └── intel/                           # SERVICES (API CLIENT)
        │       ├── marketService.ts             # GET /intel/market/*
        │       ├── competitorService.ts         # GET/POST/DELETE /intel/competitors/*
        │       ├── optimizerService.ts          # POST /intel/optimizer/*, GET reports
        │       └── analyticsService.ts          # GET /intel/analytics/*
        │
        └── hooks/
            └── intel/                           # REACT QUERY HOOKS
                ├── useCategories.ts             # Lista e detalhes de categorias
                ├── useCategoryStats.ts          # Stats de uma categoria (snapshots)
                ├── useKeywords.ts               # Keywords de uma categoria
                ├── useMonitoredSellers.ts       # CRUD de sellers monitorados
                ├── useSellerDashboard.ts        # Dashboard de um seller
                ├── useOptimizationReport.ts     # Report de otimizacao + polling
                ├── usePareto.ts                 # Dados Pareto
                ├── useForecast.ts               # Dados de forecast
                └── useInsights.ts               # Lista de insights do usuario
```

### 1.3 Documentacao — Novos Arquivos

```
MSM_Pro/
└── docs/
    └── nubimetrics_intel/
        ├── blueprint/                           # ESTE DIRETORIO
        │   ├── BLUEPRINT_ARQUITETURA.md         # Arquitetura completa
        │   ├── PLANO_IMPLEMENTACAO.md           # Plano faseado
        │   └── ESTRUTURA_SUBPROJETO.md          # Este arquivo
        │
        ├── api_endpoints/                       # Documentacao de endpoints ML usados
        │   ├── categories_api.md                # Endpoints de categorias
        │   ├── trends_api.md                    # Endpoints de trends
        │   └── search_api.md                    # Endpoints de search
        │
        ├── analises_brutas/                     # Analises iniciais de mercado
        │
        ├── categorias/                          # Dados sobre categorias ML
        │
        └── manual/                              # Manuais de uso das features
```

---

## 2. CONVENCOES DE NOMENCLATURA

### 2.1 Arquivos Backend

| Tipo | Padrao | Exemplo |
|------|--------|---------|
| Modelos SQLAlchemy | `models.py` (1 por modulo) | `intel/market/models.py` |
| Schemas Pydantic | `schemas.py` (1 por modulo) | `intel/market/schemas.py` |
| Logica de negocio | `service.py` ou `service_{dominio}.py` | `service_categories.py` |
| Rotas FastAPI | `router.py` (1 por modulo) | `intel/market/router.py` |
| Celery tasks | `tasks_{modulo}.py` | `jobs/tasks_market.py` |
| Testes | `test_{dominio}.py` | `tests/intel/test_pareto.py` |
| Prompts de IA | `prompts.py` | `intel/optimizer/prompts.py` |
| Constantes | `constants.py` | `intel/common/constants.py` |
| Utilidades | Descritivo em snake_case | `intel/common/cache.py` |

### 2.2 Arquivos Frontend

| Tipo | Padrao | Exemplo |
|------|--------|---------|
| Paginas | `PascalCase.tsx` (em pasta PascalCase) | `Intel/Market/CategoryExplorer.tsx` |
| Componentes | `PascalCase.tsx` (em pasta lowercase) | `components/intel/ScoreGauge.tsx` |
| Hooks | `use{Nome}.ts` | `hooks/intel/useCategories.ts` |
| Services | `{nome}Service.ts` | `services/intel/marketService.ts` |
| Tipos TypeScript | Dentro do `.tsx` ou `types.ts` se compartilhado | `intel/types.ts` |

### 2.3 Tabelas do Banco

| Padrao | Exemplo |
|--------|---------|
| Plural, snake_case | `monitored_sellers` |
| Prefixo por contexto quando ambiguo | `ml_categories` (para diferenciar de categorias internas) |
| Snapshots com sufixo `_snapshots` | `seller_snapshots`, `category_snapshots` |
| Logs/historico com sufixo descritivo | `optimization_reports`, `title_suggestions` |

### 2.4 Rotas da API

| Padrao | Exemplo |
|--------|---------|
| Prefixo `/api/v1/intel/` | `/api/v1/intel/market/categories` |
| Plural para colecoes | `/intel/competitors/sellers` |
| Singular para item | `/intel/competitors/sellers/{id}` |
| Verbo no HTTP method, nao na URL | `POST /intel/optimizer/analyze/{id}` (nao `/intel/optimizer/create-analysis`) |
| Acoes especiais como sub-recurso | `/intel/optimizer/titles/{id}/apply` |

### 2.5 Chaves Redis

| Padrao | Exemplo |
|--------|---------|
| `intel:{modulo}:{entidade}:{id}` | `intel:market:cat:MLB1051` |
| Separador `:` entre niveis | `intel:comp:seller:uuid-123` |
| TTL no nome do padrao (na doc, nao na chave) | Documentar: "TTL = 6h" |

### 2.6 Migrations Alembic

| Padrao | Exemplo |
|--------|---------|
| Numero sequencial + descricao | `0010_intel_analytics_base.py` |
| Prefixo `intel_` para migrations do subprojeto | `0011_intel_market_categories.py` |
| Uma migration por conjunto logico de tabelas | Nao criar 1 migration por tabela |

---

## 3. COMO O SUBPROJETO SE INTEGRA AO MSM_PRO

### 3.1 Registro de Routers

O arquivo `intel/__init__.py` expoe um router unico que agrega todos os sub-routers:

```python
# backend/app/intel/__init__.py

from fastapi import APIRouter

from app.intel.market.router import router as market_router
from app.intel.competitors.router import router as competitors_router
from app.intel.optimizer.router import router as optimizer_router
from app.intel.analytics.router import router as analytics_router

intel_router = APIRouter(prefix="/intel", tags=["intel"])

intel_router.include_router(market_router, prefix="/market", tags=["intel-market"])
intel_router.include_router(competitors_router, prefix="/competitors", tags=["intel-competitors"])
intel_router.include_router(optimizer_router, prefix="/optimizer", tags=["intel-optimizer"])
intel_router.include_router(analytics_router, prefix="/analytics", tags=["intel-analytics"])
```

E no `main.py` existente, uma unica linha adiciona tudo:

```python
# backend/app/main.py — unica alteracao necessaria

from app.intel import intel_router

app.include_router(intel_router, prefix="/api/v1")
```

### 3.2 Registro de Models

Todos os models do intel devem ser importados no `__init__.py` de cada modulo para que
o Alembic os detecte automaticamente. O `env.py` do Alembic ja importa `Base.metadata`,
entao basta garantir que os models sao importados em algum lugar no boot:

```python
# backend/app/intel/market/models.py

# SQLAlchemy models aqui...
# Alembic detecta automaticamente via Base.metadata
```

Verificar que o `alembic/env.py` importa a `Base` de `app.core.database` (ja faz).

### 3.3 Registro de Celery Tasks

Novas tasks sao registradas no `celery_app.py` adicionando ao `include`:

```python
# backend/app/core/celery_app.py — alteracao

celery_app = Celery("msm_pro")
celery_app.autodiscover_tasks([
    "app.jobs",                     # existente
    # As novas tasks em app/jobs/tasks_market.py etc. sao auto-descobertas
])
```

E os novos beat schedules sao adicionados ao `beat_schedule` existente.

### 3.4 Fluxo de Dados Entre Subprojeto e Projeto Principal

```
PROJETO PRINCIPAL (existente)                    SUBPROJETO INTEL (novo)
==================================               ==================================

vendas/models.py                                 intel/analytics/
  Listing ──────────────────────────────────────> service_pareto.py (calcula pareto)
  ListingSnapshot ──────────────────────────────> service_forecast.py (projeta vendas)
  Order ────────────────────────────────────────> service.py (calcula distribuicao)

concorrencia/models.py                           intel/competitors/
  Competitor ───────────────────────────────────> service.py (base para monitoramento)
  CompetitorSnapshot ───────────────────────────> service_analysis.py (analise)

produtos/models.py                               intel/analytics/
  Product (cost) ───────────────────────────────> service.py (calculo de margem)

mercadolivre/client.py                           intel/common/
  MLClient (metodos novos) ────────────────────> ml_api_helpers.py (wrappers)

alertas/models.py                                intel/competitors/
  AlertConfig <─────────────────────────────────  service.py (cria alertas novos)

                                                 intel/optimizer/
  Listing.health_score <────────────────────────  service_scoring.py (atualiza score)
  Listing.search_position <─────────────────────  tasks (atualiza posicao)
```

**Direcao de dependencia**: Intel DEPENDE de modulos existentes. Modulos existentes NAO dependem
de intel (exceto campos opcionais como `health_score`). Isso garante que o subprojeto pode ser
desligado sem quebrar o sistema principal.

### 3.5 Isolamento e Feature Flags

Para permitir deploy incremental, usar feature flags simples:

```python
# backend/app/core/config.py — adicao

class Settings(BaseSettings):
    # ... existente ...

    # Feature flags Intel
    INTEL_MARKET_ENABLED: bool = True
    INTEL_COMPETITORS_ENABLED: bool = True
    INTEL_OPTIMIZER_ENABLED: bool = True
    INTEL_ANALYTICS_ENABLED: bool = True
```

```python
# backend/app/intel/__init__.py — registro condicional

from app.core.config import settings

if settings.INTEL_MARKET_ENABLED:
    intel_router.include_router(market_router, prefix="/market")

if settings.INTEL_COMPETITORS_ENABLED:
    intel_router.include_router(competitors_router, prefix="/competitors")

# ... etc
```

---

## 4. PADROES DE CODIGO

### 4.1 Padrao de Service (Backend)

Todo service segue o mesmo contrato:

```python
# Exemplo: intel/analytics/service_pareto.py

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.intel.analytics.schemas import ParetoResponse, ParetoItem
from app.intel.common.cache import intel_cache


class ParetoService:
    """Calcula analise Pareto 80/20 dos anuncios do usuario."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @intel_cache("intel:analytics:pareto", ttl_seconds=14400)
    async def get_pareto(
        self,
        user_id: UUID,
        metric: str = "revenue",    # revenue | quantity
        period_days: int = 30,
    ) -> ParetoResponse:
        """
        Retorna lista de anuncios ordenados por contribuicao
        ao total, com percentil acumulado.
        """
        # 1. Query snapshots do periodo
        # 2. Agregar por listing_id
        # 3. Ordenar DESC por metrica
        # 4. Calcular percentil acumulado
        # 5. Marcar ponto de corte 80/20
        ...
```

### 4.2 Padrao de Router (Backend)

```python
# Exemplo: intel/analytics/router.py

from fastapi import APIRouter, Depends, Query
from uuid import UUID

from app.core.deps import get_current_user, get_db
from app.auth.models import User
from app.intel.analytics.service_pareto import ParetoService
from app.intel.analytics.schemas import ParetoResponse

router = APIRouter()


@router.get("/pareto", response_model=ParetoResponse)
async def get_pareto(
    metric: str = Query("revenue", regex="^(revenue|quantity)$"),
    period: int = Query(30, ge=7, le=365),
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analise Pareto 80/20 dos anuncios do usuario."""
    service = ParetoService(db)
    return await service.get_pareto(
        user_id=current_user.id,
        metric=metric,
        period_days=period,
    )
```

### 4.3 Padrao de Hook (Frontend)

```typescript
// Exemplo: hooks/intel/usePareto.ts

import { useQuery } from "@tanstack/react-query";
import { analyticsService } from "@/services/intel/analyticsService";

export function usePareto(metric: "revenue" | "quantity" = "revenue", period: number = 30) {
  return useQuery({
    queryKey: ["intel", "pareto", metric, period],
    queryFn: () => analyticsService.getPareto(metric, period),
    staleTime: 1000 * 60 * 15, // 15 min (backend cache = 4h)
  });
}
```

### 4.4 Padrao de Pagina (Frontend)

```typescript
// Exemplo: pages/Intel/Analytics/ParetoChart.tsx

import { usePareto } from "@/hooks/intel/usePareto";
import { DateRangePicker } from "@/components/intel/DateRangePicker";

export default function ParetoChart() {
  const [period, setPeriod] = useState(30);
  const { data, isLoading, error } = usePareto("revenue", period);

  if (isLoading) return <Skeleton />;
  if (error) return <ErrorAlert error={error} />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Analise Pareto 80/20</h1>
        <DateRangePicker value={period} onChange={setPeriod} />
      </div>
      {/* Chart + Table */}
    </div>
  );
}
```

---

## 5. PADRAO DE DOCUMENTACAO

### 5.1 Docstrings

- **Funcoes publicas complexas**: Docstring obrigatoria explicando o que faz, parametros e retorno
- **Funcoes simples/obvias**: Sem docstring (ex: `get_by_id`)
- **Classes**: Docstring explicando proposito
- **Modulos**: Docstring no topo do arquivo somente se o nome nao for auto-explicativo

### 5.2 Schemas Pydantic

Schemas servem como documentacao automatica do Swagger. Usar `Field(..., description="")`:

```python
class ForecastResponse(BaseModel):
    listing_id: UUID
    forecast_days: int = Field(..., description="Dias projetados (7, 30)")
    projected_sales: int = Field(..., description="Vendas estimadas no periodo")
    projected_revenue: Decimal = Field(..., description="Receita estimada em R$")
    confidence_pct: float = Field(..., description="Confianca da projecao (0-100)")
    trend_direction: str = Field(..., description="up | down | flat")
    data_points: int = Field(..., description="Quantidade de snapshots usados no calculo")
```

### 5.3 Comentarios no Codigo

- Explicar o **por que**, nao o **o que**
- Marcar decisoes nao-obvias com `# NOTE:` ou `# DESIGN:`
- Marcar limitacoes conhecidas com `# LIMITATION:`
- Marcar items futuros com `# TODO:` (com issue reference se possivel)

### 5.4 Changelog por Fase

Manter um arquivo `CHANGELOG_INTEL.md` na pasta `docs/nubimetrics_intel/`:

```markdown
# Changelog — Intel Subprojeto

## [Fase 1] - 2026-04-xx
### Adicionado
- Analise Pareto 80/20 (GET /intel/analytics/pareto)
- Projecao de vendas (GET /intel/analytics/forecast/{id})
- Distribuicao por anuncio (GET /intel/analytics/distribution)
- Score basico de saude do anuncio
- Calculo de margem/lucro integrado

### Alterado
- Adicionado campo health_score em listings
```

---

## 6. CHECKLIST DE SETUP PARA CADA FASE

### Antes de iniciar qualquer fase:

```
[ ] Ler CLAUDE.md do MSM_Pro (regras absolutas)
[ ] Ler BLUEPRINT_ARQUITETURA.md (contexto)
[ ] git pull origin main (estado atual)
[ ] alembic current (verificar migrations)
[ ] Verificar .env tem todas as variaveis necessarias para a fase
[ ] Consultar agente ml-api se houver novos endpoints ML
```

### Ao finalizar qualquer fase:

```
[ ] Todos os endpoints testados com curl + token real
[ ] Migrations aplicadas e verificadas com alembic current
[ ] Testes unitarios passando (pytest tests/intel/)
[ ] Frontend buildando sem erros (npx vite build)
[ ] Cache Redis testado (verificar TTLs)
[ ] Documentacao atualizada (schemas no Swagger, CHANGELOG)
[ ] git commit + push (deploy automatico Railway)
[ ] Verificar /health/intel no ambiente de producao
```

---

## 7. CONTAGEM DE ARQUIVOS POR FASE

| Fase | Backend (novos) | Frontend (novos) | Migrations | Tests | Total |
|------|----------------|-----------------|------------|-------|-------|
| 1 | 8 arquivos | 8 arquivos | 1 | 3 | 20 |
| 2 | 10 arquivos | 8 arquivos | 2 | 3 | 23 |
| 3 | 8 arquivos | 7 arquivos | 1 | 2 | 18 |
| 4 | 10 arquivos | 7 arquivos | 1 | 3 | 21 |
| 5 | 5 arquivos | 5 arquivos | 1 | 2 | 13 |
| **Total** | **41** | **35** | **6** | **13** | **95** |

---

## 8. REGRAS DE CONVIVENCIA COM CODIGO EXISTENTE

1. **Nunca modificar vendas/service.py** — e monolitico (2.109 linhas) e fragil. Criar novos services em intel/ que leiam os mesmos dados.

2. **Nunca duplicar models** — se intel precisa de `Listing`, importa de `vendas/models.py`. Nao criar copia.

3. **Novas tabelas via Alembic** — nunca CREATE TABLE manual. Sempre migration versionada.

4. **client.py: adicionar metodos, nao alterar existentes** — novos metodos para endpoints que intel precisa. Nao refatorar metodos que vendas/ ja usa.

5. **Router registration: 1 linha em main.py** — toda a complexidade de registro fica em `intel/__init__.py`.

6. **Feature flags** — todo modulo intel pode ser desligado via env var sem afetar o core.

7. **Testes isolados** — `tests/intel/` com conftest proprio. Nao depender de fixtures de testes existentes (que quase nao existem).

8. **Respeitar a fila de deploy** — intel tasks rodam em queues separadas para nao impactar o sync diario existente (06:00 BRT).

---

*Fim da Estrutura do Subprojeto*
