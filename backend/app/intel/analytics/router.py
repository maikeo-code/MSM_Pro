from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from .schemas import (
    ABCResponse,
    ComparisonResponse,
    DistributionResponse,
    ForecastResponse,
    InsightsResponse,
    InventoryHealthResponse,
    ParetoResponse,
)
from .service_abc import get_abc_analysis
from .service_comparison import get_temporal_comparison
from .service_distribution import get_sales_distribution
from .service_forecast import get_sales_forecast
from .service_insights import generate_insights
from .service_inventory import get_inventory_health
from .service_pareto import get_pareto_analysis

router = APIRouter(prefix="/intel/analytics", tags=["Intel - Analytics"])


@router.get("/pareto", response_model=ParetoResponse)
async def pareto(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=7, le=90, description="Periodo de analise em dias (7-90)"),
) -> ParetoResponse:
    """
    Analise Pareto 80/20 da receita por anuncio.

    Classifica cada anuncio em:
    - core: top listings que representam 0-80% da receita
    - productive: listings que representam 80-95%
    - long_tail: listings que representam 95-100%

    Retorna tambem o risco de concentracao (high/medium/low).
    """
    return await get_pareto_analysis(db, current_user.id, days=days)


@router.get("/forecast/{mlb_id}", response_model=ForecastResponse)
async def forecast(
    mlb_id: Annotated[str, Path(min_length=3, max_length=30, pattern=r"^MLB\d+$")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days_history: int = Query(
        default=60,
        ge=14,
        le=180,
        description="Dias de historico para calibrar a projecao (14-180)",
    ),
) -> ForecastResponse:
    """
    Projecao de vendas para os proximos 7 e 30 dias usando regressao linear.

    Usa o historico de snapshots diarios do anuncio para ajustar a reta de
    tendencia e projeta vendas futuras com intervalo de confianca (+/- erro padrao).

    O campo `confidence` e o R² da regressao (0.0-1.0).
    """
    return await get_sales_forecast(db, current_user.id, mlb_id=mlb_id, days_history=days_history)


@router.get("/distribution", response_model=DistributionResponse)
async def distribution(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=7, le=90, description="Periodo de analise em dias (7-90)"),
) -> DistributionResponse:
    """
    Distribuicao de receita e vendas entre todos os anuncios do usuario.

    Inclui o coeficiente de Gini como medida de desigualdade:
    - Gini proximo de 0 = receita bem distribuida entre anuncios
    - Gini proximo de 1 = receita concentrada em poucos anuncios
    """
    return await get_sales_distribution(db, current_user.id, days=days)


@router.get("/insights", response_model=InsightsResponse)
async def insights(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InsightsResponse:
    """
    Gera ate 5 insights priorizados sobre o portfolio do usuario.

    Analises realizadas:
    - Risco de concentracao de receita (Pareto)
    - Anuncios sem vendas nos ultimos 7 dias
    - Anuncios com queda de conversao (>20% em 7 dias)

    Os insights sao ordenados por prioridade (high > medium > low).
    """
    return await generate_insights(db, current_user.id)


@router.get("/comparison", response_model=ComparisonResponse)
async def comparison(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(default="30d", pattern="^(7d|15d|30d)$", description="Periodo: 7d, 15d ou 30d"),
) -> ComparisonResponse:
    """
    Comparacao temporal (Mes a Mes) de receita e vendas.

    Compara o periodo atual com o periodo anterior identico.
    Retorna para cada anuncio: receita atual vs anterior, delta %, vendas atual vs anterior.

    Periodos suportados: 7d, 15d, 30d
    """
    return await get_temporal_comparison(db, current_user.id, period=period)


@router.get("/abc", response_model=ABCResponse)
async def abc_classification(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(default="30d", pattern="^(7d|15d|30d)$", description="Periodo: 7d, 15d ou 30d"),
    metric: str = Query(default="revenue", pattern="^(revenue|units|margin)$", description="Metrica: revenue, units ou margin"),
) -> ABCResponse:
    """
    Classificacao ABC por giro de estoque e contribuicao.

    Classifica produtos em:
    - A: Top 20% = 80% da contribuicao
    - B: Proximo 30% = 15% da contribuicao
    - C: Bottom 50% = 5% da contribuicao

    Inclui turnover_rate (unidades vendidas / estoque atual).
    Metricas: revenue (padrao), units, margin.
    """
    return await get_abc_analysis(db, current_user.id, period=period, metric=metric)


@router.get("/inventory-health", response_model=InventoryHealthResponse)
async def inventory_health(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(default="30d", pattern="^(7d|15d|30d)$", description="Periodo: 7d, 15d ou 30d"),
) -> InventoryHealthResponse:
    """
    Analise de saude do estoque por anuncio.

    Calcula:
    - sell_through_rate: vendas / (vendas + estoque)
    - avg_daily_sales: media de vendas diarias
    - days_of_stock: quantos dias de estoque em mao

    Classifica como:
    - healthy: 30-90 dias de estoque
    - overstocked: > 90 dias (capital parado)
    - critical_low: < 7 dias (risco de falta)
    """
    return await get_inventory_health(db, current_user.id, period=period)
