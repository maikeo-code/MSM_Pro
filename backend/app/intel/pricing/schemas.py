from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Score breakdown ────────────────────────────────────────────────────────


class ScoreBreakdown(BaseModel):
    conv_trend: float
    visit_trend: float
    comp_score: float
    stock_score: float
    margem_score: float


# ─── Period metrics (auxiliar) ──────────────────────────────────────────────


class PeriodMetrics(BaseModel):
    visits: int
    sales: int
    conversion: float
    avg_price: float


class PeriodsData(BaseModel):
    today: Optional[PeriodMetrics] = None
    yesterday: Optional[PeriodMetrics] = None
    last_7d: Optional[PeriodMetrics] = None
    last_15d: Optional[PeriodMetrics] = None


# ─── Recommendation ────────────────────────────────────────────────────────


class RecommendationOut(BaseModel):
    id: UUID
    listing_id: UUID
    mlb_id: str
    sku: Optional[str] = None
    title: str
    thumbnail: Optional[str] = None

    current_price: float
    suggested_price: float
    price_change_pct: float

    action: str  # increase, decrease, hold
    confidence: str  # high, medium, low
    risk_level: str  # low, medium, high
    urgency: str  # immediate, next_48h, monitor
    reasoning: str

    score: Optional[float] = None
    score_breakdown: Optional[ScoreBreakdown] = None

    # Metricas no momento da recomendacao
    conversion_today: Optional[float] = None
    conversion_7d: Optional[float] = None
    visits_today: Optional[int] = None
    visits_7d: Optional[int] = None
    sales_today: Optional[int] = None
    sales_7d: Optional[int] = None
    stock: Optional[int] = None
    stock_days_projection: Optional[float] = None
    estimated_daily_sales: Optional[float] = None
    estimated_daily_profit: Optional[float] = None
    health_score: Optional[int] = None

    # Concorrencia
    competitor_avg_price: Optional[float] = None
    competitor_min_price: Optional[float] = None

    # Periodos enriquecidos (today, yesterday, 7d, 15d)
    periods_data: Optional[PeriodsData] = None

    # Status
    status: str  # pending, applied, dismissed, expired
    applied_at: Optional[datetime] = None
    report_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Summary ────────────────────────────────────────────────────────────────


class RecommendationSummary(BaseModel):
    total: int
    increase_count: int
    decrease_count: int
    hold_count: int
    avg_confidence: str  # porcentagem de recomendacoes "high" confidence


# ─── List response ──────────────────────────────────────────────────────────


class RecommendationListResponse(BaseModel):
    items: list[RecommendationOut]
    total: int
    date: date
    summary: RecommendationSummary


# ─── Apply / Dismiss ───────────────────────────────────────────────────────


class ApplyRecommendationRequest(BaseModel):
    """Corpo vazio — a recomendacao ja tem o preco sugerido."""

    pass


class ApplyRecommendationResponse(BaseModel):
    recommendation_id: UUID
    mlb_id: str
    old_price: float
    new_price: float
    ml_api_success: bool
    message: str


class DismissRecommendationRequest(BaseModel):
    reason: Optional[str] = None


# ─── History ────────────────────────────────────────────────────────────────


class RecommendationHistoryOut(BaseModel):
    items: list[RecommendationOut]
    total: int


# ─── Generate (manual trigger) ─────────────────────────────────────────────


class GenerateResponse(BaseModel):
    status: str
    recommendations_count: int
    processing_time_ms: int
    message: str
