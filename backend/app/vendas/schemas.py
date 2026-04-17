from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ============== Schemas genéricos de resposta ==============


class SyncOut(BaseModel):
    created: int
    updated: int
    total: int
    errors: list[str] = []
    message: str | None = None


class UpdatePriceOut(BaseModel):
    mlb_id: str
    new_price: float
    updated_at: str


class PromotionOut(BaseModel):
    id: str
    type: str
    discount_pct: float
    original_price: float
    final_price: float
    start_date: str
    end_date: str
    status: str


class HealthCheckOut(BaseModel):
    mlb_id: str
    listing_title: str | None = None
    score: int
    max_score: int
    status: str
    label: str
    color: str
    checks: list[dict]


class PriceHistoryItemOut(BaseModel):
    id: str
    mlb_id: str
    old_price: float | None
    new_price: float | None
    source: str | None = None
    justification: str | None = None
    success: bool
    error_message: str | None = None
    changed_at: str | None = None


class DeleteRuleOut(BaseModel):
    id: str
    is_active: bool
    message: str


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
    # Média de visitas por dia do período
    avg_visits_per_day: float | None = None

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
    # ── Medias diarias (Tema 2) ─────────────────────────────────────────
    # Para periodos > 1 dia, expoe os valores como MEDIA/dia para que
    # o dashboard possa comparar contra valores diarios (hoje/ontem).
    # Para "hoje"/"ontem"/"anteontem" estes campos sao iguais aos totais.
    dias_no_periodo: int = 1
    vendas_media_dia: float = 0.0
    visitas_media_dia: float = 0.0
    pedidos_media_dia: float = 0.0
    receita_media_dia: float = 0.0


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
    start_date: datetime
    end_date: datetime
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


class SimulatePriceIn(BaseModel):
    target_price: float = Field(gt=0, description="Preco alvo para simular")


class MargemSimulada(BaseModel):
    taxa_ml_pct: float
    taxa_ml_valor: float
    frete: float
    margem_bruta: float
    margem_pct: float
    lucro: float


class SimulatePriceOut(BaseModel):
    target_price: float
    current_price: float
    estimated_sales_per_day: float
    current_sales_per_day: float
    estimated_monthly_revenue: float
    current_monthly_revenue: float
    estimated_margin: MargemSimulada | None
    current_margin: MargemSimulada | None
    recommendation: str
    is_estimated: bool
    data_points: int
    message: str | None = None


class KpiCompareOut(BaseModel):
    period_a: dict
    period_b: dict
    period_a_label: str
    period_b_label: str
    variacao: dict


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
    item_title: str | None = None
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


class SearchPositionOut(BaseModel):
    mlb_id: str
    keyword: str
    found: bool
    position: int | None = None  # 1-based; None quando nao encontrado
    page: int | None = None       # qual pagina de 50 resultados (1-based)
    total_results: int | None = None
    searched_pages: int           # quantas paginas foram buscadas (max 4 = 200 resultados)


# ============== Schemas para Reprecificação Automática ==============

VALID_RULE_TYPES = {"FIXED_MARKUP", "COMPETITOR_DELTA", "FLOOR_CEILING"}


class RepricingRuleCreate(BaseModel):
    listing_id: UUID
    rule_type: str = Field(
        description="Tipo da regra: FIXED_MARKUP | COMPETITOR_DELTA | FLOOR_CEILING"
    )
    # FIXED_MARKUP: multiplicador sobre custo (ex: 1.4 = 40% markup)
    # COMPETITOR_DELTA: delta em R$ (ex: -2.00 = R$2 abaixo do concorrente)
    # FLOOR_CEILING: nao usa value, usa min_price / max_price
    value: Decimal | None = Field(default=None, decimal_places=2)
    min_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    is_active: bool = True

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        if self.rule_type not in VALID_RULE_TYPES:
            raise ValueError(
                f"rule_type deve ser um de: {', '.join(sorted(VALID_RULE_TYPES))}"
            )
        if self.rule_type == "FIXED_MARKUP" and self.value is None:
            raise ValueError("FIXED_MARKUP requer o campo 'value' (multiplicador > 0)")
        if self.rule_type == "COMPETITOR_DELTA" and self.value is None:
            raise ValueError("COMPETITOR_DELTA requer o campo 'value' (delta em R$)")
        if self.rule_type == "FLOOR_CEILING":
            if self.min_price is None and self.max_price is None:
                raise ValueError(
                    "FLOOR_CEILING requer ao menos 'min_price' ou 'max_price'"
                )
            if (
                self.min_price is not None
                and self.max_price is not None
                and self.min_price >= self.max_price
            ):
                raise ValueError("min_price deve ser menor que max_price")


class RepricingRuleUpdate(BaseModel):
    rule_type: str | None = Field(default=None)
    value: Decimal | None = Field(default=None, decimal_places=2)
    min_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_rule_type_fields(self) -> "RepricingRuleUpdate":
        if self.rule_type is not None and self.rule_type not in VALID_RULE_TYPES:
            raise ValueError(
                f"rule_type deve ser um de: {', '.join(sorted(VALID_RULE_TYPES))}"
            )
        if self.rule_type in {"FIXED_MARKUP", "COMPETITOR_DELTA"} and self.value is None:
            raise ValueError(
                f"{self.rule_type} requer o campo 'value' ao alterar o tipo da regra"
            )
        if self.rule_type == "FLOOR_CEILING":
            if self.min_price is None and self.max_price is None:
                raise ValueError(
                    "FLOOR_CEILING requer ao menos 'min_price' ou 'max_price' "
                    "ao alterar o tipo da regra"
                )
            if (
                self.min_price is not None
                and self.max_price is not None
                and self.min_price >= self.max_price
            ):
                raise ValueError("min_price deve ser menor que max_price")
        elif (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price >= self.max_price
        ):
            raise ValueError("min_price deve ser menor que max_price")
        return self


class RepricingRuleOut(BaseModel):
    id: UUID
    user_id: UUID
    listing_id: UUID
    rule_type: str
    value: Decimal | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    is_active: bool
    last_applied_at: datetime | None = None
    last_applied_price: Decimal | None = None
    created_at: datetime
    # Campos denormalizados para facilitar o frontend
    mlb_id: str | None = None
    listing_title: str | None = None

    model_config = {"from_attributes": True}


# ============== Schema para Cobertura de Dados ==============


class DataCoverageItemOut(BaseModel):
    """Item de cobertura para um anúncio específico."""

    mlb_id: str
    title: str
    days_with_data: int
    expected_days: int
    coverage_pct: float


class DataCoverageOut(BaseModel):
    """Resposta de cobertura de dados dos últimos N dias."""

    period_days: int
    overall_coverage_pct: float
    listings: list[DataCoverageItemOut]
