import math
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from .schemas import ForecastPoint, ForecastResponse

# Timezone BRT (UTC-3)
BRT = timezone(timedelta(hours=-3))


# ─── Pure-Python linear regression (avoids numpy dependency) ────────────────

def _linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """
    Ordinary least-squares linear regression.

    Returns (slope, intercept, r_squared).
    r_squared is clamped to [0, 1].
    """
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0, 0.0

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(xi * xi for xi in x)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))

    denom = n * sum_xx - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R²
    y_mean = sum_y / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))

    if ss_tot == 0:
        r_squared = 1.0 if ss_res == 0 else 0.0
    else:
        r_squared = max(0.0, min(1.0, 1.0 - ss_res / ss_tot))

    return slope, intercept, r_squared


def _standard_error(x: list[float], y: list[float], slope: float, intercept: float) -> float:
    """Residual standard error of the regression."""
    n = len(x)
    if n < 3:
        return 0.0
    residuals = [(yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y)]
    return math.sqrt(sum(residuals) / (n - 2))


# ─── Service ────────────────────────────────────────────────────────────────

async def get_sales_forecast(
    db: AsyncSession,
    user_id: UUID,
    mlb_id: str,
    days_history: int = 60,
) -> ForecastResponse:
    """
    Project daily sales for a listing using simple linear regression.

    History: daily sum of sales_today from ListingSnapshot.
    Output: 7-day and 30-day forecast with ±1 SE confidence bands.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_history)

    # Verify listing exists and belongs to user
    listing_check = await db.execute(
        select(Listing.id).where(
            and_(Listing.user_id == user_id, Listing.mlb_id == mlb_id)
        )
    )
    if not listing_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Anuncio {mlb_id} nao encontrado")

    day_col = cast(ListingSnapshot.captured_at, Date)

    stmt = (
        select(
            day_col.label("day"),
            func.sum(ListingSnapshot.sales_today).label("daily_sales"),
        )
        .join(Listing, Listing.id == ListingSnapshot.listing_id)
        .where(
            and_(
                Listing.user_id == user_id,
                Listing.mlb_id == mlb_id,
                ListingSnapshot.captured_at >= cutoff,
            )
        )
        .group_by(day_col)
        .order_by(day_col)
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    # Build time series indexed at 0..n-1
    history_dates: list[date] = []
    history_sales: list[float] = []
    for row in rows:
        history_dates.append(row.day)
        history_sales.append(float(row.daily_sales or 0))

    # Minimal viable data: at least 2 points required
    if len(history_dates) < 2:
        today = datetime.now(BRT).date()
        flat_value = history_sales[0] if history_sales else 0.0
        return _flat_forecast(mlb_id, today, flat_value)

    x = list(range(len(history_sales)))
    y = history_sales

    slope, intercept, r_squared = _linear_regression(x, y)
    se = _standard_error(x, y, slope, intercept)

    # Trend direction: slope threshold of 0.05 units/day (noise tolerance)
    if slope > 0.05:
        trend = "up"
    elif slope < -0.05:
        trend = "down"
    else:
        trend = "stable"

    last_x = len(history_sales) - 1
    today = date.today()

    def _make_points(horizon_days: int) -> list[ForecastPoint]:
        points = []
        for delta in range(1, horizon_days + 1):
            future_x = last_x + delta
            predicted = max(0.0, slope * future_x + intercept)
            lower = max(0.0, predicted - se)
            upper = predicted + se
            points.append(
                ForecastPoint(
                    date=today + timedelta(days=delta),
                    predicted_sales=round(predicted, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                )
            )
        return points

    return ForecastResponse(
        listing_mlb_id=mlb_id,
        forecast_7d=_make_points(7),
        forecast_30d=_make_points(30),
        trend=trend,
        confidence=round(r_squared, 4),
    )


def _flat_forecast(mlb_id: str, today: date, value: float) -> ForecastResponse:
    """Return a flat (zero-slope) forecast when history is insufficient."""
    def _points(days: int) -> list[ForecastPoint]:
        return [
            ForecastPoint(
                date=today + timedelta(days=d),
                predicted_sales=round(value, 2),
                lower_bound=0.0,
                upper_bound=round(value * 2, 2),
            )
            for d in range(1, days + 1)
        ]

    return ForecastResponse(
        listing_mlb_id=mlb_id,
        forecast_7d=_points(7),
        forecast_30d=_points(30),
        trend="stable",
        confidence=0.0,
    )
