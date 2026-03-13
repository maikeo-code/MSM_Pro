"""
Router do modulo financeiro (P&L).

Endpoints:
  GET /api/v1/financeiro/resumo      — resumo P&L agregado
  GET /api/v1/financeiro/detalhado   — breakdown por anuncio
  GET /api/v1/financeiro/timeline    — serie temporal para graficos
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.financeiro import service
from app.financeiro.schemas import (
    CashFlowOut,
    FinanceiroDetalhadoOut,
    FinanceiroResumoOut,
    FinanceiroTimeSeriesOut,
)

router = APIRouter(prefix="/financeiro", tags=["financeiro"])

PeriodParam = Literal["7d", "15d", "30d", "60d", "90d"]
TimelinePeriodParam = Literal["30d", "60d", "90d"]


@router.get("/resumo", response_model=FinanceiroResumoOut)
async def get_resumo(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodParam = Query(default="30d", description="Periodo de analise"),
):
    """
    Retorna o resumo P&L agregado para o periodo selecionado.

    Calcula: vendas brutas, taxas ML, frete, receita liquida,
    margem bruta e variacao vs periodo anterior.
    """
    data = await service.get_financeiro_resumo(db, current_user.id, period=period)
    return FinanceiroResumoOut(**data)


@router.get("/detalhado", response_model=FinanceiroDetalhadoOut)
async def get_detalhado(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodParam = Query(default="30d", description="Periodo de analise"),
):
    """
    Retorna o breakdown financeiro por anuncio (MLB) para o periodo.

    Inclui: vendas brutas, taxa ML real, frete, receita liquida,
    margem (quando SKU vinculado) e volumes de pedidos/cancelamentos/devoluções.
    """
    data = await service.get_financeiro_detalhado(db, current_user.id, period=period)
    return FinanceiroDetalhadoOut(**data)


@router.get("/timeline", response_model=FinanceiroTimeSeriesOut)
async def get_timeline(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: TimelinePeriodParam = Query(default="30d", description="Periodo para a serie temporal"),
):
    """
    Retorna a serie temporal diaria de metricas financeiras.

    Util para graficos de linha de receita, taxas e frete ao longo do tempo.
    """
    data = await service.get_financeiro_timeline(db, current_user.id, period=period)
    return FinanceiroTimeSeriesOut(**data)


@router.get("/cashflow", response_model=CashFlowOut)
async def get_cashflow(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Retorna o cash flow projetado para os proximos 30 dias.

    Calcula a data de liberacao de cada pedido aprovado usando logica D+8:
    - Se delivery_date preenchida: libera em delivery_date + 8 dias
    - Se shipping_status=shipped sem delivery_date: estima entrega em order_date + 5 dias
    - Agrupa em: proximos 7 dias, 8-14 dias, 15-30 dias

    Util para planejar o fluxo de caixa e compras de estoque.
    """
    data = await service.get_cashflow(db, current_user.id)
    return CashFlowOut(**data)
