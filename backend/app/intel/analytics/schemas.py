from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


# ─── Pareto 80/20 ────────────────────────────────────────────────────────────

class ParetoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mlb_id: str
    title: str
    revenue_30d: float
    revenue_pct: float        # % of total revenue this listing represents
    cumulative_pct: float     # running cumulative % (used to classify tier)
    classification: Literal["core", "productive", "long_tail"]


class ParetoResponse(BaseModel):
    items: list[ParetoItem]
    total_revenue: float
    core_count: int           # number of listings that make up 80% of revenue
    core_revenue_pct: float   # actual % captured by core listings
    concentration_risk: Literal["high", "medium", "low"]
    # high   → ≤2 listings make 80% of revenue
    # medium → 3-5 listings make 80%
    # low    → >5 listings make 80%


# ─── Sales Forecast ──────────────────────────────────────────────────────────

class ForecastPoint(BaseModel):
    date: date
    predicted_sales: float
    lower_bound: float
    upper_bound: float


class ForecastResponse(BaseModel):
    listing_mlb_id: str
    forecast_7d: list[ForecastPoint]
    forecast_30d: list[ForecastPoint]
    trend: Literal["up", "down", "stable"]
    confidence: float         # 0.0–1.0; based on R² of the linear regression


# ─── Sales Distribution ──────────────────────────────────────────────────────

class DistributionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mlb_id: str
    title: str
    revenue_30d: float
    sales_count: int
    pct_of_total: float       # % of total revenue


class DistributionResponse(BaseModel):
    items: list[DistributionItem]
    total_revenue: float
    total_sales: int
    gini_coefficient: float   # 0 = perfect equality, 1 = total concentration


# ─── Insights ────────────────────────────────────────────────────────────────

class InsightItem(BaseModel):
    id: str
    type: str                 # e.g. "concentration_risk", "zero_sales", "declining_conversion"
    title: str
    description: str
    priority: Literal["high", "medium", "low"]
    created_at: datetime


class InsightsResponse(BaseModel):
    insights: list[InsightItem]
    generated_at: datetime
