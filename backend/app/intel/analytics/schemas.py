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


# ─── Temporal Comparison (MoM) ────────────────────────────────────────────────────

class ComparisonItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mlb_id: str
    title: str
    revenue_current: float        # receita do período atual
    revenue_previous: float       # receita do período anterior
    revenue_delta_pct: float      # % de variação
    sales_current: int            # vendas do período atual
    sales_previous: int           # vendas do período anterior
    sales_delta_pct: float        # % de variação em vendas


class ComparisonResponse(BaseModel):
    items: list[ComparisonItem]
    period_days: int
    total_revenue_current: float
    total_revenue_previous: float
    total_revenue_delta_pct: float
    total_sales_current: int
    total_sales_previous: int
    total_sales_delta_pct: float


# ─── ABC Classification (Stock Turnover) ──────────────────────────────────────────

class ABCItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mlb_id: str
    title: str
    classification: Literal["A", "B", "C"]
    revenue_30d: float
    revenue_pct: float
    cumulative_pct: float
    units_sold: int
    current_stock: int
    turnover_rate: float          # units_sold / current_stock (annual equivalent)
    metric: str                    # "revenue", "units", or "margin"


class ABCResponse(BaseModel):
    items: list[ABCItem]
    period_days: int
    metric_used: str
    total_revenue: float
    class_a_revenue_pct: float    # % da receita classe A
    class_b_revenue_pct: float
    class_c_revenue_pct: float


# ─── Inventory Health ──────────────────────────────────────────────────────────────

class InventoryHealthItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mlb_id: str
    title: str
    current_stock: int
    avg_daily_sales: float
    sell_through_rate: float      # sales / (sales + stock)
    days_of_stock: float          # stock / avg_daily_sales
    health_status: Literal["healthy", "overstocked", "critical_low", "no_sales"]


class InventoryHealthResponse(BaseModel):
    items: list[InventoryHealthItem]
    period_days: int
    total_items: int
    healthy_count: int
    overstocked_count: int
    critical_low_count: int
    avg_days_of_stock: float
