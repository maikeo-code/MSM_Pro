from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from .schemas import InventoryHealthItem, InventoryHealthResponse


async def get_inventory_health(
    db: AsyncSession,
    user_id: UUID,
    period: str = "30d",
) -> InventoryHealthResponse:
    """
    Analyze inventory health per listing.

    Calculates:
    - sell_through_rate = sales / (sales + stock)
    - avg_daily_sales = total_sales / period_days
    - days_of_stock = current_stock / avg_daily_sales
    - health_status:
        * healthy: 30-90 days of stock
        * overstocked: > 90 days
        * critical_low: < 7 days
    """
    # Parse period into days
    period_days_map = {
        "7d": 7,
        "15d": 15,
        "30d": 30,
    }
    period_days = period_days_map.get(period, 30)

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

    # ─ Subquery to get latest stock per listing ────────────────────────────────────
    latest_stock_subq = (
        select(
            ListingSnapshot.listing_id,
            ListingSnapshot.stock,
        )
        .order_by(ListingSnapshot.listing_id, desc(ListingSnapshot.captured_at))
        .distinct(ListingSnapshot.listing_id)
    ).subquery()

    # ─ Fetch aggregated data per listing ────────────────────────────────────────
    stmt = (
        select(
            Listing.mlb_id,
            Listing.title,
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("total_sales"),
            # Get latest stock
            func.coalesce(latest_stock_subq.c.stock, 0).label("current_stock"),
        )
        .outerjoin(
            ListingSnapshot,
            and_(
                ListingSnapshot.listing_id == Listing.id,
                ListingSnapshot.captured_at >= cutoff,
            ),
        )
        .outerjoin(
            latest_stock_subq,
            latest_stock_subq.c.listing_id == Listing.id,
        )
        .where(Listing.user_id == user_id)
        .group_by(Listing.mlb_id, Listing.title, Listing.id, latest_stock_subq.c.stock)
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    if not rows:
        return InventoryHealthResponse(
            items=[],
            period_days=period_days,
            total_items=0,
            healthy_count=0,
            overstocked_count=0,
            critical_low_count=0,
            avg_days_of_stock=0.0,
        )

    # ─ Process each listing and compute health metrics ──────────────────────────
    items: list[InventoryHealthItem] = []
    total_days_of_stock = 0.0
    healthy_count = 0
    overstocked_count = 0
    critical_low_count = 0

    for row in rows:
        total_sales = int(row.total_sales or 0)
        current_stock = int(row.current_stock or 0)

        # Avoid division by zero
        if period_days == 0:
            avg_daily_sales = 0.0
        else:
            avg_daily_sales = total_sales / period_days

        # Calculate sell-through rate: sales / (sales + stock)
        sell_through_rate = (
            (total_sales / (total_sales + current_stock))
            if (total_sales + current_stock) > 0
            else 0.0
        )

        # Calculate days of stock
        days_of_stock = (
            current_stock / avg_daily_sales if avg_daily_sales > 0 else float("inf")
        )

        # Classify health status
        if days_of_stock == float("inf"):
            # No sales in period: either new product or overstocked with no demand
            health_status = "no_sales"
            overstocked_count += 1
        elif days_of_stock < 7:
            health_status = "critical_low"
            critical_low_count += 1
        elif days_of_stock > 90:
            health_status = "overstocked"
            overstocked_count += 1
        else:
            health_status = "healthy"
            healthy_count += 1

        # Skip infinite days_of_stock in calculations
        if days_of_stock != float("inf"):
            total_days_of_stock += days_of_stock

        items.append(
            InventoryHealthItem(
                mlb_id=row.mlb_id,
                title=row.title,
                current_stock=current_stock,
                avg_daily_sales=round(avg_daily_sales, 2),
                sell_through_rate=round(sell_through_rate, 4),
                days_of_stock=round(days_of_stock, 2) if days_of_stock != float("inf") else 999.0,
                health_status=health_status,
            )
        )

    # Calculate average days of stock (excluding infinite values)
    finite_count = sum(1 for i in items if i.days_of_stock != 999.0)
    avg_days = total_days_of_stock / finite_count if finite_count > 0 else 0.0

    return InventoryHealthResponse(
        items=items,
        period_days=period_days,
        total_items=len(items),
        healthy_count=healthy_count,
        overstocked_count=overstocked_count,
        critical_low_count=critical_low_count,
        avg_days_of_stock=round(avg_days, 2),
    )
