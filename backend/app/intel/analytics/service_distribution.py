from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from .schemas import DistributionItem, DistributionResponse


def _gini_coefficient(values: list[float]) -> float:
    """
    Compute the Gini coefficient for a list of non-negative values.

    Gini = 0  means perfect equality (every listing earns the same).
    Gini = 1  means total concentration (one listing earns everything).

    Uses the standard sorted-array formula:
        G = (2 * sum(rank_i * value_i)) / (n * sum(values)) - (n+1)/n
    """
    n = len(values)
    if n == 0:
        return 0.0

    total = sum(values)
    if total == 0:
        return 0.0

    sorted_vals = sorted(values)
    numerator = sum((i + 1) * v for i, v in enumerate(sorted_vals))
    gini = (2 * numerator) / (n * total) - (n + 1) / n
    return round(max(0.0, min(1.0, gini)), 4)


async def get_sales_distribution(
    db: AsyncSession,
    user_id: UUID,
    days: int = 30,
) -> DistributionResponse:
    """
    Return revenue and sales distribution across all listings for the period.

    Also computes the Gini coefficient as a single inequality metric:
    a high Gini (>0.7) indicates heavy concentration in a few listings.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(
            Listing.mlb_id,
            Listing.title,
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("revenue_30d"),
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("sales_count"),
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
        return DistributionResponse(
            items=[],
            total_revenue=0.0,
            total_sales=0,
            gini_coefficient=0.0,
        )

    total_revenue = sum(float(row.revenue_30d or 0) for row in rows)
    total_sales = sum(int(row.sales_count or 0) for row in rows)

    revenues = [float(row.revenue_30d or 0) for row in rows]
    gini = _gini_coefficient(revenues)

    items: list[DistributionItem] = []
    for row in rows:
        rev = float(row.revenue_30d or 0)
        pct = (rev / total_revenue * 100) if total_revenue > 0 else 0.0
        items.append(
            DistributionItem(
                mlb_id=row.mlb_id,
                title=row.title,
                revenue_30d=round(rev, 2),
                sales_count=int(row.sales_count or 0),
                pct_of_total=round(pct, 2),
            )
        )

    return DistributionResponse(
        items=items,
        total_revenue=round(total_revenue, 2),
        total_sales=total_sales,
        gini_coefficient=gini,
    )
