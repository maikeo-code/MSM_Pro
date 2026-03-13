from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ListingCreate(BaseModel):
    product_id: UUID | None = None
    ml_account_id: UUID
    mlb_id: str = Field(min_length=3, max_length=50, pattern=r"^MLB-?\d+$")
    title: str = Field(min_length=1, max_length=500)
    listing_type: str = Field(default="classico", pattern=r"^(classico|premium|full)$")
    price: Decimal = Field(ge=0, decimal_places=2)
    original_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    sale_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    category_id: str | None = None
    seller_sku: str | None = None
    permalink: str | None = None
    thumbnail: str | None = None


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    listing_type: str | None = Field(default=None, pattern=r"^(classico|premium|full)$")
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    original_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    sale_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    status: str | None = None
    category_id: str | None = None
    seller_sku: str | None = None
    permalink: str | None = None
    thumbnail: str | None = None


class SnapshotOut(BaseModel):
    id: UUID
    listing_id: UUID
    price: Decimal
    visits: int
    sales_today: int
    questions: int
    stock: int
    conversion_rate: Decimal | None
    orders_count: int | None = 0
    revenue: float | None = None
    avg_selling_price: float | None = None
    cancelled_orders: int | None = 0
    cancelled_revenue: float | None = 0
    returns_count: int | None = 0
    returns_revenue: float | None = 0
    captured_at: datetime

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID | None
    ml_account_id: UUID
    mlb_id: str
    title: str
    listing_type: str
    price: Decimal
    original_price: Decimal | None = None
    sale_price: Decimal | None = None
    status: str
    category_id: str | None = None
    seller_sku: str | None = None
    sale_fee_amount: float | None = None  # taxa real ML em R$
    sale_fee_pct: float | None = None  # taxa real ML em %
    avg_shipping_cost: float | None = None  # frete medio real
    permalink: str | None
    thumbnail: str | None
    created_at: datetime
    updated_at: datetime
    last_snapshot: SnapshotOut | None = None
    # Campos calculados
    dias_para_zerar: int | None = None
    rpv: float | None = None  # receita por visita
    taxa_cancelamento: float | None = None
    avg_price_per_sale: float | None = None  # revenue / orders_count
    participacao_pct: float | None = None  # % do total de receita
    vendas_concluidas: float | None = None  # revenue - cancelled_revenue - returns_revenue
    voce_recebe: float | None = None  # preco - taxa ML real - frete real
    quality_score: int | None = None  # score de qualidade 0-100
    # Variação por anúncio (hoje vs ontem)
    vendas_variacao: float | None = None
    receita_variacao: float | None = None

    model_config = {"from_attributes": True}


class KpiPeriodOut(BaseModel):
    vendas: int = 0
    visitas: int = 0
    conversao: float = 0.0
    anuncios: int = 0
    valor_estoque: float = 0.0
    receita: float = 0.0
    # Métricas de pedidos
    pedidos: int = 0
    receita_total: float = 0.0
    preco_medio: float = 0.0
    taxa_cancelamento: float = 0.0
    # Novas métricas
    preco_medio_por_venda: float = 0.0  # receita / pedidos (não por unidade)
    vendas_concluidas: float = 0.0  # receita - cancelamentos - devoluções
    cancelamentos_valor: float = 0.0  # soma de cancelled_revenue no período
    devolucoes_valor: float = 0.0  # soma de returns_revenue no período
    devolucoes_qtd: int = 0  # soma de returns_count no período
    # Variações vs período anterior
    vendas_variacao: float | None = None
    receita_variacao: float | None = None
    visitas_variacao: float | None = None
    conversao_variacao: float | None = None


class MargemResult(BaseModel):
    preco: Decimal
    custo_sku: Decimal
    taxa_ml_pct: Decimal
    taxa_ml_valor: Decimal
    frete: Decimal
    margem_bruta: Decimal
    margem_pct: Decimal
    lucro: Decimal
    listing_type: str


# ============== Schemas para Análise de Preço ==============


class PriceBand(BaseModel):
    price_range_label: str
    avg_sales_per_day: float
    avg_conversion: float
    total_revenue: float
    avg_margin: float
    days_count: int
    is_optimal: bool


class SKUInfo(BaseModel):
    id: str | None = None
    sku: str | None = None
    cost: float


class FullStock(BaseModel):
    available: int
    in_transit: int
    days_until_stockout_7d: float | None
    days_until_stockout_30d: float | None
    velocity_7d: float
    velocity_30d: float
    status: str  # "critical" | "warning" | "excess" | "ok"


class Promotion(BaseModel):
    id: str
    type: str
    discount_pct: float
    original_price: float
    final_price: float
    start_date: str
    end_date: str
    status: str


class Ads(BaseModel):
    roas: float | None = None
    impressions: int | None = None
    clicks: int | None = None
    cpc: float | None = None
    ctr: float | None = None
    spend: float | None = None
    attributed_sales: float | None = None


class CompetitorPrice(BaseModel):
    mlb_id: str
    price: float
    last_updated: str


class Alert(BaseModel):
    type: str
    message: str
    severity: str  # "critical" | "warning" | "info"


class ListingInfo(BaseModel):
    mlb_id: str
    title: str
    price: float
    listing_type: str
    status: str
    thumbnail: str | None
    permalink: str | None


class ListingAnalysisOut(BaseModel):
    is_mock: bool
    listing: ListingInfo
    sku: SKUInfo
    snapshots: list[dict]  # SnapshotOut serializado
    price_bands: list[PriceBand]
    full_stock: FullStock
    promotions: list[Promotion]
    ads: dict
    competitor: CompetitorPrice | None
    alerts: list[Alert]


class UpdatePriceIn(BaseModel):
    price: float = Field(gt=0)


class LinkSkuIn(BaseModel):
    product_id: UUID | None = None


class FunnelOut(BaseModel):
    visitas: int = 0
    vendas: int = 0
    conversao: float = 0.0
    receita: float = 0.0


class CreatePromotionIn(BaseModel):
    discount_pct: float = Field(ge=5, le=60)
    start_date: str
    end_date: str
    promotion_id: str | None = None


# ============== Schemas para Heatmap de Vendas ==============


class HeatmapCell(BaseModel):
    day_of_week: int  # 0=segunda ... 6=domingo
    hour: int  # 0-23 (0 quando fallback por dia)
    day_name: str
    count: int  # numero de vendas nessa celula (dia+hora ou so dia no fallback)
    avg_per_week: float  # media semanal para esse dia (fallback) ou 0 no hourly


class HeatmapOut(BaseModel):
    period_days: int
    total_sales: int
    avg_daily: float
    peak_day: str  # ex: "Quarta-feira"
    peak_day_index: int  # 0-6
    peak_hour: str  # ex: "14:00-15:00" (vazio no fallback)
    has_hourly_data: bool  # True se usou Orders, False se fallback snapshots
    data: list[HeatmapCell]


# ============== Schemas para Orders ==============


class SuggestionApplyIn(BaseModel):
    new_price: float = Field(gt=0, description="Novo preco a aplicar no anuncio")
    justification: str = Field(
        default="", max_length=1000, description="Motivo da alteracao de preco"
    )


class SuggestionApplyOut(BaseModel):
    mlb_id: str
    old_price: float
    new_price: float
    justification: str
    ml_api_success: bool
    ml_api_price_returned: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    log_id: UUID
    applied_at: datetime

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: UUID
    ml_order_id: str
    ml_account_id: UUID
    listing_id: UUID | None = None
    mlb_id: str
    buyer_nickname: str
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    sale_fee: Decimal
    shipping_cost: Decimal
    net_amount: Decimal
    payment_status: str
    shipping_status: str
    order_date: datetime
    payment_date: datetime | None = None
    delivery_date: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
