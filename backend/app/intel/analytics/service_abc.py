from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from .schemas import ABCItem, ABCResponse


async def get_abc_analysis(
    db: AsyncSession,
    user_id: UUID,
    period: str = "30d",
    metric: str = "revenue",
) -> ABCResponse:
    """
    ABC Classification by stock turnover and contribution.

    Classifies products into:
    - A: Top 20% of selected metric = 80% of contribution
    - B: Next 30% of selected metric = 15% of contribution
    - C: Bottom 50% of selected metric = 5% of contribution

    Metric can be: "revenue", "units", "margin" (margin uses estimated margin)
    Includes turnover_rate = units_sold / current_stock
    """
    # Parse period into days
    period_days_map = {
        "7d": 7,
        "15d": 15,
        "30d": 30,
    }
    period_days = period_days_map.get(period, 30)

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

    # ─ Fetch data from snapshots and current stock ────────────────────────────────
    stmt = (
        select(
            Listing.id.label("listing_id"),
            Listing.mlb_id,
            Listing.title,
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("revenue_sum"),
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("units_sum"),
            # Get the latest snapshot to extract current stock
            func.array_agg(ListingSnapshot.stock, ordering_by=ListingSnapshot.captured_at.desc()).label("stocks"),
        )
        .outerjoin(
            ListingSnapshot,
            and_(
                ListingSnapshot.listing_id == Listing.id,
                ListingSnapshot.captured_at >= cutoff,
            ),
        )
        .where(Listing.user_id == user_id)
        .group_by(Listing.id, Listing.mlb_id, Listing.title)
        .order_by(func.sum(ListingSnapshot.revenue).desc().nullslast())
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    if not rows:
        return ABCResponse(
            items=[],
            period_days=period_days,
            metric_used=metric,
            total_revenue=0.0,
            class_a_revenue_pct=0.0,
            class_b_revenue_pct=0.0,
            class_c_revenue_pct=0.0,
        )

    # ─ Extract data and compute metrics ──────────────────────────────────────────
    items_data = []
    for row in rows:
        revenue = float(row.revenue_sum or 0)
        units = int(row.units_sum or 0)
        # Get latest stock from array (first element due to DESC ordering)
        current_stock = row.stocks[0] if row.stocks else 0

        # Compute turnover: units_sold / current_stock
        turnover = units / current_stock if current_stock > 0 else 0.0

        # Placeholder for margin calculation (requires cost data, not available here)
        # For now, use revenue as the base metric
        metric_value = {
            "revenue": revenue,
            "units": units,
            "margin": revenue * 0.2,  # Placeholder: assume 20% margin
        }.get(metric, revenue)

        items_data.append(
            {
                "mlb_id": row.mlb_id,
                "title": row.title,
                "revenue": revenue,
                "units": units,
                "current_stock": current_stock,
                "turnover": turnover,
                "metric_value": metric_value,
            }
        )

    # ─ Classify into A/B/C based on cumulative % ────────────────────────────────
    total_metric = sum(item["metric_value"] for item in items_data)

    items: list[ABCItem] = []
    cumulative = 0.0

    for item in sorted(items_data, key=lambda x: x["metric_value"], reverse=True):
        metric_val = item["metric_value"]
        metric_pct = (metric_val / total_metric * 100) if total_metric > 0 else 0.0
        prev_cumulative = cumulative
        cumulative += metric_pct

        # Classify: A (0-80%), B (80-95%), C (95-100%)
        if prev_cumulative < 80.0:
            classification = "A"
        elif cumulative <= 95.0:
            classification = "B"
        else:
            classification = "C"

        items.append(
            ABCItem(
                mlb_id=item["mlb_id"],
                title=item["title"],
                classification=classification,
                revenue_30d=round(item["revenue"], 2),
                revenue_pct=round(metric_pct, 2),
                cumulative_pct=round(min(cumulative, 100.0), 2),
                units_sold=item["units"],
                current_stock=item["current_stock"],
                turnover_rate=round(item["turnover"], 4),
                metric=metric,
            )
        )

    # ─ Summary statistics ────────────────────────────────────────────────────────
    class_a_items = [i for i in items if i.classification == "A"]
    class_b_items = [i for i in items if i.classification == "B"]
    class_c_items = [i for i in items if i.classification == "C"]

    class_a_revenue = sum(i.revenue_30d for i in class_a_items)
    class_b_revenue = sum(i.revenue_30d for i in class_b_items)
    class_c_revenue = sum(i.revenue_30d for i in class_c_items)
    total_revenue = class_a_revenue + class_b_revenue + class_c_revenue

    class_a_pct = (class_a_revenue / total_revenue * 100) if total_revenue > 0 else 0.0
    class_b_pct = (class_b_revenue / total_revenue * 100) if total_revenue > 0 else 0.0
    class_c_pct = (class_c_revenue / total_revenue * 100) if total_revenue > 0 else 0.0

    return ABCResponse(
        items=items,
        period_days=period_days,
        metric_used=metric,
        total_revenue=round(total_revenue, 2),
        class_a_revenue_pct=round(class_a_pct, 2),
        class_b_revenue_pct=round(class_b_pct, 2),
        class_c_revenue_pct=round(class_c_pct, 2),
    )
