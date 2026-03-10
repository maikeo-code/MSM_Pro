from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ListingCreate(BaseModel):
    product_id: UUID
    ml_account_id: UUID
    mlb_id: str = Field(min_length=3, max_length=50, pattern=r"^MLB-?\d+$")
    title: str = Field(min_length=1, max_length=500)
    listing_type: str = Field(default="classico", pattern=r"^(classico|premium|full)$")
    price: Decimal = Field(ge=0, decimal_places=2)
    permalink: str | None = None
    thumbnail: str | None = None


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    listing_type: str | None = Field(default=None, pattern=r"^(classico|premium|full)$")
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    status: str | None = None
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
    captured_at: datetime

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    ml_account_id: UUID
    mlb_id: str
    title: str
    listing_type: str
    price: Decimal
    status: str
    permalink: str | None
    thumbnail: str | None
    created_at: datetime
    updated_at: datetime
    last_snapshot: SnapshotOut | None = None

    model_config = {"from_attributes": True}


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
    id: str
    sku: str
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


class CreatePromotionIn(BaseModel):
    discount_pct: float = Field(ge=5, le=60)
    start_date: str
    end_date: str
    promotion_id: str | None = None
