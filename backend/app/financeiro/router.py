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
    DREOut,
    FinanceiroDetalhadoOut,
    FinanceiroResumoOut,
    FinanceiroTimeSeriesOut,
    RentabilidadeSKUOut,
    TaxConfigIn,
    TaxConfigOut,
)

router = APIRouter(prefix="/financeiro", tags=["financeiro"])

PeriodParam = Literal["7d", "15d", "30d", "60d", "90d"]
TimelinePeriodParam = Literal["30d", "60d", "90d"]


@router.get("/resumo", response_model=FinanceiroResumoOut)
async def get_resumo(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodParam = Query(default="30d", description="Periodo de analise"),
    ml_account_id: str | None = Query(default=None, description="Filtrar por conta ML especifica (opcional)"),
):
    """
    Retorna o resumo P&L agregado para o periodo selecionado.

    Calcula: vendas brutas, taxas ML, frete, receita liquida,
    margem bruta e variacao vs periodo anterior.

    Se ml_account_id for fornecido, filtra apenas os dados dessa conta ML.
    """
    data = await service.get_financeiro_resumo(db, current_user.id, period=period, ml_account_id=ml_account_id)
    return FinanceiroResumoOut(**data)


@router.get("/detalhado", response_model=FinanceiroDetalhadoOut)
async def get_detalhado(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodParam = Query(default="30d", description="Periodo de analise"),
    ml_account_id: str | None = Query(default=None, description="Filtrar por conta ML especifica (opcional)"),
):
    """
    Retorna o breakdown financeiro por anuncio (MLB) para o periodo.

    Inclui: vendas brutas, taxa ML real, frete, receita liquida,
    margem (quando SKU vinculado) e volumes de pedidos/cancelamentos/devoluções.

    Se ml_account_id for fornecido, filtra apenas os dados dessa conta ML.
    """
    data = await service.get_financeiro_detalhado(db, current_user.id, period=period, ml_account_id=ml_account_id)
    return FinanceiroDetalhadoOut(**data)


@router.get("/timeline", response_model=FinanceiroTimeSeriesOut)
async def get_timeline(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: TimelinePeriodParam = Query(default="30d", description="Periodo para a serie temporal"),
    ml_account_id: str | None = Query(default=None, description="Filtrar por conta ML especifica (opcional)"),
):
    """
    Retorna a serie temporal diaria de metricas financeiras.

    Util para graficos de linha de receita, taxas e frete ao longo do tempo.

    Se ml_account_id for fornecido, filtra apenas os dados dessa conta ML.
    """
    data = await service.get_financeiro_timeline(db, current_user.id, period=period, ml_account_id=ml_account_id)
    return FinanceiroTimeSeriesOut(**data)


@router.get("/cashflow", response_model=CashFlowOut)
async def get_cashflow(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: str | None = Query(default=None, description="Filtrar por conta ML especifica (opcional)"),
):
    """
    Retorna o cash flow projetado para os proximos 30 dias.

    Calcula a data de liberacao de cada pedido aprovado usando logica D+8:
    - Se delivery_date preenchida: libera em delivery_date + 8 dias
    - Se shipping_status=shipped sem delivery_date: estima entrega em order_date + 5 dias
    - Agrupa em: proximos 7 dias, 8-14 dias, 15-30 dias

    Util para planejar o fluxo de caixa e compras de estoque.

    Se ml_account_id for fornecido, filtra apenas os dados dessa conta ML.
    """
    data = await service.get_cashflow(db, current_user.id, ml_account_id=ml_account_id)
    return CashFlowOut(**data)


@router.get("/dre", response_model=DREOut)
async def get_dre(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodParam = Query(default="30d", description="Periodo de analise"),
):
    """
    Retorna DRE Gerencial Simplificado (Income Statement) para o periodo.

    Estrutura:
    - Receita Bruta (soma das vendas)
    - (-) Taxas ML
    - (-) Frete
    - (-) Cancelamentos/Devoluções
    = Receita Líquida
    - (-) CMV (Custo dos Produtos Vendidos)
    = Lucro Bruto
    - (-) Impostos Estimados (baseado em tax_config)
    = Lucro Operacional

    Inclui percentuais e comparação com período anterior.
    """
    data = await service.get_dre(db, current_user.id, period=period)
    return DREOut(**data)


@router.get("/tax-config", response_model=TaxConfigOut | None)
async def get_tax_config(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Retorna a configuração de regime tributário do usuário.

    Se não configurado, retorna None. Use PUT /tax-config para configurar.
    """
    data = await service.get_tax_config(db, current_user.id)
    if data:
        return TaxConfigOut(**data)
    return None


@router.put("/tax-config", response_model=TaxConfigOut)
async def set_tax_config(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TaxConfigIn,
):
    """
    Criar ou atualizar configuração de regime tributário.

    Tabelas de referência Simples Nacional Anexo I (Comércio):
    - Até R$180k: 4%
    - R$180k-360k: 7.3%
    - R$360k-720k: 9.5%
    - R$720k-1.8M: 10.7%
    - R$1.8M-3.6M: 14.3%
    - R$3.6M-4.8M: 19%

    Exemplo de body:
    ```json
    {
      "regime": "simples_nacional",
      "faixa_anual": 360000,
      "aliquota_efetiva": 0.073
    }
    ```
    """
    data = await service.set_tax_config(
        db,
        current_user.id,
        regime=body.regime,
        faixa_anual=body.faixa_anual,
        aliquota_efetiva=body.aliquota_efetiva,
    )
    return TaxConfigOut(**data)


@router.get("/rentabilidade-sku", response_model=RentabilidadeSKUOut)
async def get_rentabilidade_sku(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodParam = Query(default="30d", description="Periodo de analise"),
):
    """
    Retorna rentabilidade agregada por SKU (Product) para o periodo.

    Para cada SKU vinculado a listings:
    - Receita total
    - Custo total
    - Margem total e %
    - Número de listings vinculados
    - Número de vendas
    - Melhor e pior listing por margem

    Útil para identificar quais produtos são mais lucrativos e onde há oportunidades.
    """
    data = await service.get_rentabilidade_por_sku(db, current_user.id, period=period)
    return RentabilidadeSKUOut(**data)
