"""
Schemas Pydantic para o modulo financeiro (P&L).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class FinanceiroResumoOut(BaseModel):
    """Resumo P&L agregado para o periodo selecionado."""
    periodo: str                            # ex: "7d", "15d", "30d", "60d"
    data_inicio: date
    data_fim: date
    # Valores financeiros principais
    vendas_brutas: Decimal = Decimal("0")       # SUM(revenue)
    taxas_ml_total: Decimal = Decimal("0")      # SUM(taxa_ml_pct * revenue / 100)
    frete_total: Decimal = Decimal("0")         # SUM(avg_shipping_cost * orders_count)
    receita_liquida: Decimal = Decimal("0")     # vendas_brutas - taxas_ml - frete
    custo_total: Decimal = Decimal("0")         # SUM(product.cost * unidades) — apenas SKUs vinculados
    margem_bruta: Decimal = Decimal("0")        # receita_liquida - custo_total
    margem_pct: Decimal = Decimal("0")          # margem_bruta / vendas_brutas * 100
    # Volumes
    total_pedidos: int = 0
    total_cancelamentos: int = 0
    total_devolucoes: int = 0
    # Comparacao com periodo anterior
    variacao_vendas_pct: Decimal | None = None  # % de variacao vs periodo anterior
    variacao_receita_pct: Decimal | None = None

    model_config = {"from_attributes": True}


class FinanceiroDetalhadoItemOut(BaseModel):
    """Breakdown financeiro por anuncio (MLB)."""
    mlb_id: str
    title: str
    listing_type: str
    thumbnail: str | None = None
    # Financeiro
    vendas_brutas: Decimal = Decimal("0")
    taxa_ml_pct: Decimal = Decimal("0")         # % da taxa ML
    taxa_ml_valor: Decimal = Decimal("0")       # R$ da taxa ML
    frete: Decimal = Decimal("0")
    receita_liquida: Decimal = Decimal("0")
    custo_unitario: Decimal | None = None       # custo do SKU vinculado
    custo_total: Decimal | None = None          # custo_unitario * unidades
    margem: Decimal | None = None               # receita_liquida - custo_total
    margem_pct: Decimal | None = None
    # Volumes
    unidades: int = 0
    cancelamentos: int = 0
    devolucoes: int = 0

    model_config = {"from_attributes": True}


class FinanceiroDetalhadoOut(BaseModel):
    """Lista de breakdown por anuncio para o periodo."""
    periodo: str
    data_inicio: date
    data_fim: date
    items: list[FinanceiroDetalhadoItemOut]


class FinanceiroTimeSeriesPointOut(BaseModel):
    """Ponto da serie temporal (1 dia)."""
    date: date
    vendas_brutas: Decimal = Decimal("0")
    receita_liquida: Decimal = Decimal("0")
    taxas: Decimal = Decimal("0")
    frete: Decimal = Decimal("0")
    pedidos: int = 0

    model_config = {"from_attributes": True}


class FinanceiroTimeSeriesOut(BaseModel):
    """Serie temporal de financeiro para graficos."""
    periodo: str
    data_inicio: date
    data_fim: date
    points: list[FinanceiroTimeSeriesPointOut]


# ─── Cash Flow Projetado D+8 ─────────────────────────────────────────────────

class CashFlowDayOut(BaseModel):
    """Um ponto da linha do tempo de liberacao de pagamentos."""
    date: date
    amount: Decimal = Decimal("0")      # Valor a ser liberado neste dia
    orders_count: int = 0               # Quantidade de pedidos


class CashFlowOut(BaseModel):
    """Cash flow projetado para os proximos 30 dias (liberacao D+8 apos entrega)."""
    proximos_7d: Decimal = Decimal("0")     # Total a liberar nos proximos 7 dias
    proximos_14d: Decimal = Decimal("0")   # Total a liberar em 8-14 dias
    proximos_30d: Decimal = Decimal("0")   # Total a liberar em 15-30 dias
    total_pendente: Decimal = Decimal("0") # Total de todos os periodos
    timeline: list[CashFlowDayOut]         # Detalhamento dia a dia
