# Especificação Técnica - Explorador de Categorias e Buscador

**Versão**: 1.0
**Data**: 2026-03-18
**Status**: Documento de Referência para Development

---

## 1. EXPLORADOR DE CATEGORIAS - SPEC TÉCNICA

### 1.1 Modelo de Dados

```python
# models.py

class CategoryMetric(Base):
    """
    Armazena métricas normalizadas de categorias do Mercado Livre.
    Atualizado mensalmente via Celery task.
    """
    __tablename__ = "category_metrics"

    # Identificação
    id = Column(UUID, primary_key=True, default=uuid4)
    category_id = Column(String(50), unique=True, index=True)
    category_name = Column(String(255))
    category_path = Column(String(500))  # "Eletrônicos > Celulares > iPhone"

    # Hierarquia
    l1_id = Column(String(50), index=True)
    l1_name = Column(String(100))  # Vertical (ex: "Eletrônicos")
    l2_id = Column(String(50), nullable=True)
    l2_name = Column(String(100), nullable=True)
    l3_id = Column(String(50), nullable=True)
    l3_name = Column(String(100), nullable=True)

    # Índices Normalizados (1-10)
    units_sold_index = Column(Integer, nullable=False)  # 1-10
    growth_index = Column(Integer, nullable=False)  # 1-10
    sellers_index = Column(Integer, nullable=False)  # 1-10
    catalog_index = Column(Integer, nullable=False)  # 1-10
    competition_index = Column(Integer, nullable=False)  # 1-10
    conversion_index = Column(Integer, nullable=False)  # 1-10
    revenue_index = Column(Integer, nullable=False)  # 1-10
    opportunity_index = Column(Integer, nullable=False)  # 1-10 (composite)

    # Valores Absolutos (últimos 12 meses)
    units_sold_12m = Column(Integer, nullable=False)
    units_growth_pct = Column(Numeric(5, 2))  # 45.23%

    revenue_12m = Column(Numeric(15, 2), nullable=False)  # R$ em centavos
    revenue_growth_pct = Column(Numeric(5, 2))

    sellers_active = Column(Integer, nullable=False)
    listings_count = Column(Integer, nullable=False)

    conversion_rate = Column(Numeric(5, 2))  # 2.34%
    visits_12m = Column(Integer, nullable=False)

    # Benchmarks (Mercado Geral)
    market_units_12m = Column(Integer)
    market_sellers = Column(Integer)
    market_conversion_pct = Column(Numeric(5, 2))
    market_revenue_12m = Column(Numeric(15, 2))

    # Timestamps
    snapshot_date = Column(Date, nullable=False)  # Data do snapshot
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Índices
    __table_args__ = (
        Index('idx_category_l1_snapshot', 'l1_id', 'snapshot_date'),
        Index('idx_category_opportunity', 'opportunity_index', 'snapshot_date'),
    )

class CategoryIndexLog(Base):
    """
    Log histórico de como os índices foram calculados.
    Útil para debugging e auditoria.
    """
    __tablename__ = "category_index_logs"

    id = Column(UUID, primary_key=True, default=uuid4)
    category_id = Column(String(50), ForeignKey("category_metrics.category_id"))
    index_type = Column(String(50))  # "units", "growth", "competition", etc
    raw_value = Column(Numeric(10, 2))
    min_benchmark = Column(Numeric(10, 2))
    max_benchmark = Column(Numeric(10, 2))
    normalized_value = Column(Integer)  # 1-10
    calculation_formula = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 1.2 Schemas Pydantic

```python
# schemas.py

class CategoryMetricOut(BaseModel):
    category_id: str
    category_name: str
    l1_name: str

    # Índices
    units_sold_index: int
    growth_index: int
    sellers_index: int
    competition_index: int
    opportunity_index: int

    # Valores absolutos
    units_sold_12m: int
    revenue_12m: Decimal
    sellers_active: int
    listings_count: int

    class Config:
        from_attributes = True

class CategoryFilterParams(BaseModel):
    """Parâmetros de filtro para explorador."""

    # Filtros por índice
    growth_min: Optional[int] = Field(None, ge=1, le=10)
    growth_max: Optional[int] = Field(None, ge=1, le=10)

    competition_max: Optional[int] = Field(None, ge=1, le=10)
    sellers_min: Optional[int] = None

    # Filtro de keyword
    category_contains: Optional[str] = None

    # Ordenação
    order_by: str = "opportunity_index"  # "opportunity_index", "growth_index", etc
    order_direction: str = "desc"  # "asc" ou "desc"

    # Paginação
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class CategoryDetailOut(BaseModel):
    """Detalhes completos com benchmarks."""
    metric: CategoryMetricOut
    benchmarks: dict = {
        "market_units_12m": int,
        "market_sellers": int,
        "market_conversion_pct": Decimal,
        "category_vs_market": {
            "units_ratio": Decimal,
            "sellers_ratio": Decimal,
            "conversion_delta": Decimal,
        }
    }
```

### 1.3 Endpoints do Backend

```python
# router.py - /api/v1/exploradores/categorias/

from fastapi import APIRouter, Query, Depends
from typing import Optional, List

router = APIRouter(prefix="/api/v1/exploradores/categorias", tags=["exploradores"])

@router.get("/")
async def explore_categories(
    # Filtros
    growth_min: Optional[int] = Query(None, ge=1, le=10),
    growth_max: Optional[int] = Query(None, ge=1, le=10),
    competition_max: Optional[int] = Query(None, ge=1, le=10),
    sellers_min: Optional[int] = Query(None),

    # Busca
    category_contains: Optional[str] = Query(None),
    l1_filter: Optional[str] = Query(None),

    # Preset
    preset: Optional[str] = Query(None),  # "alto_crescimento", "baixa_concorrencia", etc

    # Ordenação
    order_by: str = Query("opportunity_index"),
    order_direction: str = Query("desc"),

    # Paginação
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),

    # Colunas a retornar
    columns: Optional[List[str]] = Query(None),

    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Explorador de categorias com filtros customizáveis.

    Query Params:
    - growth_min, growth_max: Filtro de crescimento (1-10)
    - competition_max: Máximo índice de competição
    - category_contains: Keyword na categoria
    - preset: Usar filtro pré-determinado
    - order_by: Campo para ordenação
    - columns: Lista de colunas a retornar

    Returns:
    {
        "total": 1234,
        "page": 1,
        "page_size": 20,
        "categories": [
            {
                "category_id": "MLB123",
                "category_name": "Eletrônicos > Celulares",
                "growth_index": 8,
                "competition_index": 6,
                ...
            }
        ]
    }
    """
    pass

@router.get("/{category_id}")
async def get_category_details(
    category_id: str,
    current_user: User = Depends(get_current_user),
) -> CategoryDetailOut:
    """
    Detalhes completos de uma categoria com benchmarks.

    Returns:
    {
        "metric": {...},
        "benchmarks": {
            "market_units_12m": 250000,
            "market_sellers": 5000,
            "category_vs_market": {
                "units_ratio": 0.95,  # 95% do mercado
                "sellers_ratio": 0.04,  # 4% dos vendedores
                ...
            }
        }
    }
    """
    pass

@router.get("/presets/list")
async def list_presets(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Retorna lista de filtros pré-determinados.

    Returns:
    {
        "presets": [
            {
                "id": "alto_crescimento",
                "name": "Alto Crescimento",
                "description": "Crescimento >= 100%",
                "target_user": "iniciante",
                "filters": {
                    "growth_min": 7,
                    "sellers_min": 5
                }
            }
        ]
    }
    """
    pass
```

### 1.4 Service Layer

```python
# service.py

class CategoryService:

    @staticmethod
    async def get_categories_with_filters(
        filters: CategoryFilterParams,
        session: AsyncSession
    ) -> tuple[List[CategoryMetric], int]:
        """
        Busca categorias com filtros aplicados.
        Retorna (lista_categorias, total_count).
        """
        query = select(CategoryMetric)

        # Aplicar filtros de índice
        if filters.growth_min:
            query = query.where(CategoryMetric.growth_index >= filters.growth_min)
        if filters.growth_max:
            query = query.where(CategoryMetric.growth_index <= filters.growth_max)
        if filters.competition_max:
            query = query.where(CategoryMetric.competition_index <= filters.competition_max)

        # Aplicar filtro de keyword
        if filters.category_contains:
            query = query.where(
                CategoryMetric.category_name.icontains(filters.category_contains)
            )

        # Ordenação
        order_field = getattr(CategoryMetric, filters.order_by)
        if filters.order_direction == "asc":
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())

        # Contar total
        total = await session.scalar(
            select(func.count()).select_from(
                query.subquery()
            )
        )

        # Paginação
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)

        results = await session.execute(query)
        return results.scalars().all(), total

    @staticmethod
    def apply_preset(preset_id: str) -> CategoryFilterParams:
        """Aplica um preset de filtros pré-determinados."""
        presets = {
            "alto_crescimento": CategoryFilterParams(
                growth_min=7,
                sellers_min=5,
                order_by="growth_index"
            ),
            "baixa_concorrencia": CategoryFilterParams(
                competition_max=4,
                order_by="opportunity_index"
            ),
            "baixo_catalogo": CategoryFilterParams(
                # Aplicar lógica de percentil
                order_by="listings_count"
            ),
            "iniciante": CategoryFilterParams(
                growth_min=4,
                competition_max=6,
                sellers_min=2,
            ),
            "avancado": CategoryFilterParams(
                order_by="opportunity_index",
            ),
        }
        return presets.get(preset_id, CategoryFilterParams())
```

### 1.5 Celery Task - Coleta de Dados

```python
# tasks.py - Sincronização mensal de category metrics

from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def sync_category_metrics(self):
    """
    Sincroniza métricas de categorias do Mercado Livre.
    Executado 1x por mês no 1º dia às 02:00 BRT.

    Fluxo:
    1. Fetch lista de categorias do ML API
    2. Para cada categoria, buscar vendas + sellers + visitas
    3. Normalizar índices (1-10)
    4. Salvar em categoria_metrics
    """

    try:
        ml_client = MLClient()

        # 1. Fetch categorias
        categories = ml_client.get_categories()  # Todas as leaf categories

        logger.info(f"Sincronizando {len(categories)} categorias...")

        for category in categories:
            try:
                # 2. Buscar dados
                sales_data = ml_client.get_category_sales_data(
                    category_id=category['id'],
                    days_back=365
                )

                sellers_data = ml_client.get_category_sellers(category['id'])
                visits_data = ml_client.get_category_visits(category['id'])

                # 3. Extrair métricas brutas
                units_sold = sales_data['total_units']
                revenue = sales_data['total_revenue']
                sellers_count = len(sellers_data['sellers'])
                listings_count = sales_data['total_listings']
                visits = visits_data['total_visits']

                # 4. Normalizar índices (1-10)
                # Usar benchmarks do market para normalizar
                market_units = sales_data['market_units']
                market_sellers = sales_data['market_sellers']

                units_index = normalize_to_1_10(
                    units_sold,
                    min_value=0,
                    max_value=market_units * 2
                )

                growth_index = normalize_to_1_10(
                    sales_data['growth_pct'],
                    min_value=0,
                    max_value=200  # 200% growth
                )

                # 5. Salvar em banco
                metric = CategoryMetric(
                    category_id=category['id'],
                    category_name=category['name'],
                    category_path=category['path'],
                    l1_id=category['l1_id'],
                    l1_name=category['l1_name'],
                    units_sold_index=units_index,
                    growth_index=growth_index,
                    # ... outros índices
                    units_sold_12m=units_sold,
                    revenue_12m=revenue,
                    sellers_active=sellers_count,
                    listings_count=listings_count,
                    snapshot_date=date.today(),
                )

                session.merge(metric)

            except Exception as e:
                logger.error(f"Erro sincronizando categoria {category['id']}: {e}")
                continue

        session.commit()
        logger.info("Sincronização de categorias concluída!")

    except Exception as exc:
        logger.error(f"Erro na sincronização de categorias: {exc}")
        raise self.retry(exc=exc, countdown=60)

def normalize_to_1_10(value, min_value, max_value):
    """Normaliza valor para escala 1-10."""
    if max_value <= min_value:
        return 5  # Default

    normalized = (value - min_value) / (max_value - min_value)
    normalized = max(0, min(1, normalized))  # Clamp 0-1
    index = int(normalized * 9) + 1  # Scale 1-10
    return index
```

### 1.6 Caching Strategy

```python
# Redis cache keys

CATEGORY_LIST_CACHE_KEY = "explorer:categories:list:{page}:{preset}"
CATEGORY_DETAIL_CACHE_KEY = "explorer:category:{category_id}:details"
PRESET_LIST_CACHE_KEY = "explorer:presets:list"

# TTL: 24 horas (dados atualizados mensalmente, cache curto para UI)
CACHE_TTL = 86400  # 24 horas

# No momento do sync mensal:
# 1. Invalidar todos os caches
# 2. Reconstruir lista principal
# 3. Pré-popular cache dos 100 melhores por oportunidade
```

---

## 2. EXPLORADOR DE ANÚNCIOS - SPEC TÉCNICA

### 2.1 Modelo de Dados

```python
class AdHistory(Base):
    """
    Histórico diário de dados de um anúncio.
    Sincronizado diariamente via Celery.
    """
    __tablename__ = "ad_history"

    id = Column(UUID, primary_key=True, default=uuid4)
    mlb_id = Column(String(50), index=True)  # MLB ID no ML

    # Data do snapshot
    snapshot_date = Column(Date, index=True)

    # Dados diários
    price = Column(Numeric(10, 2))
    original_price = Column(Numeric(10, 2), nullable=True)

    daily_revenue = Column(Numeric(15, 2), nullable=True)  # Vendas do dia
    daily_units = Column(Integer, nullable=True)  # Unidades vendidas

    cumulative_revenue = Column(Numeric(15, 2), nullable=True)  # Desde publicação
    cumulative_units = Column(Integer, nullable=True)

    days_published = Column(Integer)  # Total de dias online

    visits_daily = Column(Integer, nullable=True)
    visits_cumulative = Column(Integer, nullable=True)

    stock = Column(Integer, nullable=True)

    # Status do anúncio
    status = Column(String(50))  # "active", "paused", "closed", etc

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Índices
    __table_args__ = (
        Index('idx_ad_mlb_date', 'mlb_id', 'snapshot_date'),
        Index('idx_ad_date', 'snapshot_date'),
    )

class AdSearchResult(Base):
    """
    Cache de resultados de busca expandida.
    Invalidado a cada pesquisa.
    """
    __tablename__ = "ad_search_results"

    id = Column(UUID, primary_key=True, default=uuid4)
    keyword = Column(String(255), index=True)
    mlb_id = Column(String(50))
    title = Column(String(500))

    # Score de relevância
    relevance_score = Column(Numeric(3, 2))

    # Última atualização
    last_sync = Column(DateTime, default=datetime.utcnow)
```

### 2.2 Endpoints do Backend

```python
# router.py - /api/v1/exploradores/anuncios/

@router.get("/search")
async def search_ads(
    q: str = Query(..., min_length=1),
    expanded: bool = Query(True),  # Pesquisa expandida
    category: Optional[str] = Query(None),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    min_sales: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Busca expandida de anúncios.

    Returns:
    {
        "total": 1234,
        "keyword": "iPhone 13",
        "ads": [
            {
                "mlb_id": "MLB-123",
                "title": "iPhone 13 Pro...",
                "price": 7999.00,
                "sales_12m": 456,
                "revenue_12m": 3600000.00,
                "days_published": 365,
                "last_update": "2026-03-18"
            }
        ]
    }
    """
    pass

@router.get("/{mlb_id}/history")
async def get_ad_history(
    mlb_id: str,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    metrics: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Histórico completo de um anúncio.

    Returns:
    {
        "mlb_id": "MLB-123",
        "history": [
            {
                "date": "2026-03-18",
                "price": 7999.00,
                "daily_revenue": 15900.00,
                "daily_units": 2,
                "cumulative_revenue": 3600000.00,
                "cumulative_units": 456,
                "days_published": 365
            }
        ]
    }
    """
    pass
```

---

## 3. COMPARE ANÚNCIOS - SPEC TÉCNICA

### 3.1 Modelo de Dados

```python
class CompetitionGroup(Base):
    """Grupo de anúncios para monitoramento de concorrência."""
    __tablename__ = "competition_groups"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), index=True)

    name = Column(String(255))  # "iPhone 13 - Análise de Preço"
    description = Column(String(1000), nullable=True)

    # Configuração
    daily_tracking = Column(Boolean, default=True)
    alert_on_price_change = Column(Boolean, default=False)

    # Membros
    members = relationship("GroupMember")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

class GroupMember(Base):
    """Membro de um grupo de concorrência."""
    __tablename__ = "group_members"

    id = Column(UUID, primary_key=True, default=uuid4)
    group_id = Column(UUID, ForeignKey("competition_groups.id"), index=True)
    mlb_id = Column(String(50))

    is_own_ad = Column(Boolean)  # True se é seu anúncio
    following = Column(Boolean, default=False)  # Receber alertas

    label = Column(String(100), nullable=True)  # "Concorrente A"

    added_at = Column(DateTime, default=datetime.utcnow)
```

### 3.2 Endpoints do Backend

```python
# router.py - /api/v1/concorrencia/grupos/

@router.post("/")
async def create_group(
    group_data: CompetitionGroupCreate,
    current_user: User = Depends(get_current_user),
) -> CompetitionGroupOut:
    """Cria novo grupo de concorrência."""
    pass

@router.get("/{group_id}/daily")
async def get_group_daily_data(
    group_id: UUID,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Dados diários do grupo de concorrência.

    Returns:
    {
        "group": {...},
        "daily_data": [
            {
                "date": "2026-03-18",
                "ads": [
                    {
                        "mlb_id": "MLB-123",
                        "label": "Seu Anúncio",
                        "price": 6500.00,
                        "daily_revenue": 13000.00,
                        "daily_units": 2,
                        "stock": 150
                    }
                ]
            }
        ]
    }
    """
    pass

@router.get("/{group_id}/members/{mlb_id}/details")
async def get_member_details(
    group_id: UUID,
    mlb_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Drill-down detalhado de um anúncio.

    Returns:
    {
        "mlb_id": "MLB-123",
        "title": "iPhone 13 Pro...",
        "current_price": 6500.00,
        "original_price": 7999.00,
        "price_history": [...],  # Últimas mudanças
        "sales_data": {
            "daily": 2,
            "average_daily": 1.8,
            "cumulative": 456
        },
        "changes_recent": [
            {"date": "2026-03-18", "type": "price_change", "from": 6600, "to": 6500"},
            {"date": "2026-03-17", "type": "stock_change", "from": 200, "to": 150}
        ]
    }
    """
    pass
```

---

## 4. COLETA DE DADOS - PIPELINE

### 4.1 Arquitetura Geral

```
┌─────────────────────────────────────────────────────┐
│                 ML API                              │
│  /categories | /items | /visits | /orders           │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│  Celery Tasks (Jobs)                                │
│  - sync_category_metrics (1x/mês)                  │
│  - sync_ad_history (1x/dia @ 06:00 BRT)            │
│  - sync_competition_groups (1x/dia @ 06:15 BRT)   │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│  PostgreSQL (Data Layer)                            │
│  - category_metrics                                 │
│  - ad_history                                       │
│  - competition_groups                               │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│  Redis Cache (Session)                              │
│  - explorer:categories:list                         │
│  - explorer:category:{id}:details                  │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│  FastAPI Backend (API Layer)                        │
│  /api/v1/exploradores/categorias                    │
│  /api/v1/exploradores/anuncios                      │
│  /api/v1/concorrencia/grupos                        │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│  React Frontend (UI)                                │
│  - Explorador de Categorias                         │
│  - Explorador de Anúncios                           │
│  - Compare Anúncios                                 │
└─────────────────────────────────────────────────────┘
```

### 4.2 Celery Beat Schedule

```python
# celery_app.py

from celery.schedules import crontab

beat_schedule = {
    'sync-category-metrics': {
        'task': 'app.jobs.tasks.sync_category_metrics',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),  # 1º dia do mês @ 02:00 BRT
    },
    'sync-ad-history': {
        'task': 'app.jobs.tasks.sync_ad_history',
        'schedule': crontab(hour=6, minute=0),  # Todo dia @ 06:00 BRT
    },
    'sync-competition-groups': {
        'task': 'app.jobs.tasks.sync_competition_groups',
        'schedule': crontab(hour=6, minute=15),  # Todo dia @ 06:15 BRT (após ad_history)
    },
}
```

---

## 5. MIGRATIONS ALEMBIC

```python
# migrations/versions/000X_add_explorer_tables.py

def upgrade():
    op.create_table(
        'category_metrics',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.String(50), nullable=False, unique=True),
        sa.Column('category_name', sa.String(255), nullable=False),
        # ... outras colunas
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_category_l1_snapshot', 'l1_id', 'snapshot_date'),
    )

    op.create_table(
        'ad_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('mlb_id', sa.String(50), nullable=False),
        # ... outras colunas
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_ad_mlb_date', 'mlb_id', 'snapshot_date'),
    )

    # ... mais tabelas

def downgrade():
    op.drop_table('category_metrics')
    op.drop_table('ad_history')
    # ... etc
```

---

## 6. ENVIRONMENT VARIABLES

```env
# .env

# ML API (para sincronização)
ML_API_BASE_URL=https://api.mercadolibre.com
ML_API_TIMEOUT=30
ML_API_MAX_RETRIES=3

# Celery (Jobs)
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Cache
REDIS_CACHE_URL=redis://localhost:6379/0
CACHE_TTL_CATEGORIES=86400  # 24 horas

# Database
DATABASE_URL=postgresql+asyncpg://...

# Logging
LOG_LEVEL=INFO
```

---

## 7. TESTES

```python
# tests/test_exploradores_categorias.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_explore_categories_default(client: AsyncClient):
    """Testa listagem básica de categorias."""
    response = await client.get(
        "/api/v1/exploradores/categorias/",
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    assert "categories" in response.json()

@pytest.mark.asyncio
async def test_explore_categories_with_filter(client: AsyncClient):
    """Testa filtro de crescimento."""
    response = await client.get(
        "/api/v1/exploradores/categorias/?growth_min=7&competition_max=5",
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(cat["growth_index"] >= 7 for cat in data["categories"])

@pytest.mark.asyncio
async def test_explore_categories_with_preset(client: AsyncClient):
    """Testa uso de preset."""
    response = await client.get(
        "/api/v1/exploradores/categorias/?preset=alto_crescimento",
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
```

---

## 8. DOCUMENTAÇÃO API (OpenAPI/Swagger)

```python
# routers/exploradores.py

class ExploreResponse(BaseModel):
    """Resposta do endpoint /exploradores/categorias/"""

    total: int = Field(..., description="Total de categorias matching filtros")
    page: int = Field(..., description="Página atual")
    page_size: int = Field(..., description="Tamanho da página")
    categories: List[CategoryMetricOut] = Field(..., description="Lista de categorias")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 1234,
                "page": 1,
                "page_size": 20,
                "categories": [
                    {
                        "category_id": "MLB123",
                        "category_name": "Eletrônicos > Celulares",
                        "growth_index": 8,
                        "competition_index": 6,
                    }
                ]
            }
        }
```

---

## 9. PERFORMANCE CONSIDERATIONS

### 9.1 Índices SQL
```sql
-- Category Metrics
CREATE INDEX idx_category_l1_snapshot ON category_metrics(l1_id, snapshot_date);
CREATE INDEX idx_category_opportunity ON category_metrics(opportunity_index DESC, snapshot_date);
CREATE INDEX idx_category_contains ON category_metrics USING GIN(to_tsvector('portuguese', category_name));

-- Ad History
CREATE INDEX idx_ad_mlb_date ON ad_history(mlb_id, snapshot_date DESC);
CREATE INDEX idx_ad_date ON ad_history(snapshot_date DESC);

-- Competition Groups
CREATE INDEX idx_group_user ON competition_groups(user_id, created_at DESC);
CREATE INDEX idx_member_group ON group_members(group_id, mlb_id);
```

### 9.2 Query Optimization
- Usar pagination sempre (default: page_size=20)
- Cache de lista principal de categorias (Redis TTL=24h)
- Lazy load de detalhes (drill-down)
- Batch fetch para ad_history (máx 30 dias por requisição)

### 9.3 Load Testing
- Assumir 1000 concurrent users
- Pico @ 06:00 BRT quando sync diária roda
- Usar connection pooling (min=5, max=20)

---

*Especificação Técnica - Explorador de Categorias e Buscador*
*Versão 1.0 - Documento de Referência*
