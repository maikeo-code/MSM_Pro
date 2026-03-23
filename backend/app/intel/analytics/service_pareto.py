from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from .schemas import ParetoItem, ParetoResponse


async def get_pareto_analysis(
    db: AsyncSession,
    user_id: UUID,
    days: int = 30,
) -> ParetoResponse:
    """
    Run Pareto 80/20 analysis on the user's listings.

    Aggregates revenue per listing over the requested period, sorts
    descending, computes cumulative percentages, and classifies each
    listing into one of three tiers:

    - core        : listings that together make up 0-80% of revenue
    - productive  : listings that push cumulative to 80-95%
    - long_tail   : listings in the bottom 5% of revenue contribution

    The listing that crosses the 80% boundary is included in "core"
    because it is the marginal asset that achieves the 80/20 threshold.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(
            Listing.mlb_id,
            Listing.title,
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("revenue_30d"),
        )
        .outerjoin(
            ListingSnapshot,
            and_(
                ListingSnapshot.listing_id == Listing.id,
                ListingSnapshot.captured_at >= cutoff,
            ),
        )
        .where(Listing.user_id == user_id)
        .group_by(Listing.mlb_id, Listing.title)
        .order_by(func.sum(ListingSnapshot.revenue).desc().nullslast())
        .limit(500)
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    if not rows:
        return ParetoResponse(
            items=[],
            total_revenue=0.0,
            core_count=0,
            core_revenue_pct=0.0,
            concentration_risk="low",
        )

    total_revenue = sum(float(row.revenue_30d or 0) for row in rows)

    items: list[ParetoItem] = []
    cumulative = 0.0

    for row in rows:
        rev = float(row.revenue_30d or 0)
        revenue_pct = (rev / total_revenue * 100) if total_revenue > 0 else 0.0
        prev_cumulative = cumulative
        cumulative += revenue_pct

        # The listing that brings cumulative from below 80 to >= 80 is "core".
        # All listings fully within 0-80 are also "core".
        if prev_cumulative < 80.0:
            classification = "core"
        elif cumulative <= 95.0:
            classification = "productive"
        else:
            classification = "long_tail"

        items.append(
            ParetoItem(
                mlb_id=row.mlb_id,
                title=row.title,
                revenue_30d=round(rev, 2),
                revenue_pct=round(revenue_pct, 2),
                cumulative_pct=round(min(cumulative, 100.0), 2),
                classification=classification,
            )
        )

    # Derive summary metrics from the classified list
    core_items = [i for i in items if i.classification == "core"]
    core_count = len(core_items)
    core_revenue_sum = sum(i.revenue_30d for i in core_items)
    core_revenue_pct = (core_revenue_sum / total_revenue * 100) if total_revenue > 0 else 0.0

    if core_count <= 2:
        concentration_risk = "high"
    elif core_count <= 5:
        concentration_risk = "medium"
    else:
        concentration_risk = "low"

    return ParetoResponse(
        items=items,
        total_revenue=round(total_revenue, 2),
        core_count=core_count,
        core_revenue_pct=round(core_revenue_pct, 2),
        concentration_risk=concentration_risk,
    )
