from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from .schemas import ComparisonItem, ComparisonResponse


async def get_temporal_comparison(
    db: AsyncSession,
    user_id: UUID,
    period: str = "30d",
) -> ComparisonResponse:
    """
    Compare revenue and sales between current period and previous identical period.

    Periods supported: 7d, 15d, 30d
    Returns comparison metrics for each listing plus totals.
    """
    # Parse period into days
    period_days_map = {
        "7d": 7,
        "15d": 15,
        "30d": 30,
    }
    period_days = period_days_map.get(period, 30)

    now = datetime.now(timezone.utc)

    # Current period: last N days
    current_start = now - timedelta(days=period_days)
    current_end = now

    # Previous period: N days before that
    previous_end = current_start
    previous_start = current_start - timedelta(days=period_days)

    # ─ Query current period ──────────────────────────────────────────────────────
    stmt_current = (
        select(
            Listing.mlb_id,
            Listing.title,
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("revenue"),
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("sales"),
        )
        .outerjoin(
            ListingSnapshot,
            and_(
                ListingSnapshot.listing_id == Listing.id,
                ListingSnapshot.captured_at >= current_start,
                ListingSnapshot.captured_at < current_end,
            ),
        )
        .where(Listing.user_id == user_id)
        .group_by(Listing.mlb_id, Listing.title)
    )

    result_current = await db.execute(stmt_current)
    current_data = {
        (row.mlb_id, row.title): {
            "revenue": float(row.revenue or 0),
            "sales": int(row.sales or 0),
        }
        for row in result_current.fetchall()
    }

    # ─ Query previous period ─────────────────────────────────────────────────────
    stmt_previous = (
        select(
            Listing.mlb_id,
            Listing.title,
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("revenue"),
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("sales"),
        )
        .outerjoin(
            ListingSnapshot,
            and_(
                ListingSnapshot.listing_id == Listing.id,
                ListingSnapshot.captured_at >= previous_start,
                ListingSnapshot.captured_at < previous_end,
            ),
        )
        .where(Listing.user_id == user_id)
        .group_by(Listing.mlb_id, Listing.title)
    )

    result_previous = await db.execute(stmt_previous)
    previous_data = {
        (row.mlb_id, row.title): {
            "revenue": float(row.revenue or 0),
            "sales": int(row.sales or 0),
        }
        for row in result_previous.fetchall()
    }

    # ─ Build items and compute deltas ────────────────────────────────────────────
    items: list[ComparisonItem] = []
    total_revenue_current = 0.0
    total_revenue_previous = 0.0
    total_sales_current = 0
    total_sales_previous = 0

    # Merge keys from both periods to include all listings
    all_mlb_ids = set(current_data.keys()) | set(previous_data.keys())

    for mlb_id, title in sorted(all_mlb_ids):
        current = current_data.get((mlb_id, title), {"revenue": 0.0, "sales": 0})
        previous = previous_data.get((mlb_id, title), {"revenue": 0.0, "sales": 0})

        rev_curr = current["revenue"]
        rev_prev = previous["revenue"]
        sales_curr = current["sales"]
        sales_prev = previous["sales"]

        # Calculate delta percentages
        rev_delta_pct = (
            ((rev_curr - rev_prev) / rev_prev * 100)
            if rev_prev > 0
            else (100.0 if rev_curr > 0 else 0.0)
        )

        sales_delta_pct = (
            ((sales_curr - sales_prev) / sales_prev * 100)
            if sales_prev > 0
            else (100.0 if sales_curr > 0 else 0.0)
        )

        items.append(
            ComparisonItem(
                mlb_id=mlb_id,
                title=title,
                revenue_current=round(rev_curr, 2),
                revenue_previous=round(rev_prev, 2),
                revenue_delta_pct=round(rev_delta_pct, 2),
                sales_current=sales_curr,
                sales_previous=sales_prev,
                sales_delta_pct=round(sales_delta_pct, 2),
            )
        )

        total_revenue_current += rev_curr
        total_revenue_previous += rev_prev
        total_sales_current += sales_curr
        total_sales_previous += sales_prev

    # Calculate total deltas
    total_rev_delta_pct = (
        ((total_revenue_current - total_revenue_previous) / total_revenue_previous * 100)
        if total_revenue_previous > 0
        else (100.0 if total_revenue_current > 0 else 0.0)
    )

    total_sales_delta_pct = (
        ((total_sales_current - total_sales_previous) / total_sales_previous * 100)
        if total_sales_previous > 0
        else (100.0 if total_sales_current > 0 else 0.0)
    )

    return ComparisonResponse(
        items=items,
        period_days=period_days,
        total_revenue_current=round(total_revenue_current, 2),
        total_revenue_previous=round(total_revenue_previous, 2),
        total_revenue_delta_pct=round(total_rev_delta_pct, 2),
        total_sales_current=total_sales_current,
        total_sales_previous=total_sales_previous,
        total_sales_delta_pct=round(total_sales_delta_pct, 2),
    )
