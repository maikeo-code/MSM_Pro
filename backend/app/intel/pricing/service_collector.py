"""
Collector Service para o Daily Intel Report.

Coleta dados de TODOS os anuncios ativos de um usuario e monta um dict
enriquecido por anuncio com metricas de periodos, concorrentes e estoque.

100% SQL/Python — sem IA.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import cast, func, select
from sqlalchemy import Date as SADate
from sqlalchemy.ext.asyncio import AsyncSession

from app.concorrencia.models import Competitor, CompetitorSnapshot
from app.core.database import AsyncSessionLocal
from app.produtos.models import Product
from app.vendas.models import Listing, ListingSnapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _safe_float(val) -> float:
    """Converte Decimal/int/None para float seguro."""
    if val is None:
        return 0.0
    return float(val)


def _build_latest_per_day_subquery(listing_ids: list[UUID], date_from: date, date_to: date):
    """Subquery: snapshot mais recente por listing por dia (deduplicacao)."""
    return (
        select(
            ListingSnapshot.listing_id,
            cast(ListingSnapshot.captured_at, SADate).label("snap_date"),
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            cast(ListingSnapshot.captured_at, SADate) >= date_from,
            cast(ListingSnapshot.captured_at, SADate) <= date_to,
        )
        .group_by(
            ListingSnapshot.listing_id,
            cast(ListingSnapshot.captured_at, SADate),
        )
        .subquery()
    )


async def _aggregate_period(
    db: AsyncSession,
    listing_ids: list[UUID],
    date_from: date,
    date_to: date,
) -> dict[UUID, dict]:
    """
    Agrega metricas de snapshots por listing no intervalo [date_from, date_to].

    Usa latest-per-day deduplication (mesmo padrao do tasks_digest.py).

    Retorna: {listing_id: {visits, sales, revenue}} para cada listing
    que tenha pelo menos um snapshot no periodo.
    """
    if not listing_ids:
        return {}

    latest_per_day = _build_latest_per_day_subquery(listing_ids, date_from, date_to)

    # Receita: usa coluna revenue quando disponivel, senao price * sales_today
    revenue_expr = func.coalesce(
        ListingSnapshot.revenue,
        ListingSnapshot.price * ListingSnapshot.sales_today,
    )

    result = await db.execute(
        select(
            ListingSnapshot.listing_id,
            func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visits"),
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("sales"),
            func.coalesce(func.sum(revenue_expr), 0).label("revenue"),
        )
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
        .group_by(ListingSnapshot.listing_id)
    )

    out: dict[UUID, dict] = {}
    for row in result.fetchall():
        visits = int(row.visits)
        sales = int(row.sales)
        revenue = _safe_float(row.revenue)
        conversion = round((sales / visits * 100), 4) if visits > 0 else 0.0
        avg_price = round(revenue / sales, 2) if sales > 0 else 0.0

        out[row.listing_id] = {
            "visits": visits,
            "sales": sales,
            "conversion": conversion,
            "avg_price": avg_price,
            "revenue": revenue,
        }
    return out


async def _get_latest_competitor_prices(
    db: AsyncSession,
    listing_ids: list[UUID],
) -> dict[UUID, list[float]]:
    """
    Busca o preco mais recente de cada concorrente ativo vinculado
    aos listings fornecidos.

    Retorna: {listing_id: [preco1, preco2, ...]}
    """
    if not listing_ids:
        return {}

    # Busca concorrentes ativos dos listings
    comp_result = await db.execute(
        select(Competitor.id, Competitor.listing_id).where(
            Competitor.listing_id.in_(listing_ids),
            Competitor.is_active == True,  # noqa: E712
        )
    )
    competitors = comp_result.fetchall()
    if not competitors:
        return {}

    comp_ids = [c.id for c in competitors]
    comp_to_listing = {c.id: c.listing_id for c in competitors}

    # Snapshot mais recente de cada concorrente
    latest_comp_subq = (
        select(
            CompetitorSnapshot.competitor_id,
            func.max(CompetitorSnapshot.captured_at).label("max_at"),
        )
        .where(CompetitorSnapshot.competitor_id.in_(comp_ids))
        .group_by(CompetitorSnapshot.competitor_id)
        .subquery()
    )

    prices_result = await db.execute(
        select(
            CompetitorSnapshot.competitor_id,
            CompetitorSnapshot.price,
        ).join(
            latest_comp_subq,
            (CompetitorSnapshot.competitor_id == latest_comp_subq.c.competitor_id)
            & (CompetitorSnapshot.captured_at == latest_comp_subq.c.max_at),
        )
    )

    out: dict[UUID, list[float]] = {}
    for row in prices_result.fetchall():
        listing_id = comp_to_listing.get(row.competitor_id)
        if listing_id is None:
            continue
        price = _safe_float(row.price)
        if price > 0:
            if listing_id not in out:
                out[listing_id] = []
            out[listing_id].append(price)

    return out


async def _get_latest_snapshot_per_listing(
    db: AsyncSession,
    listing_ids: list[UUID],
) -> dict[UUID, object]:
    """Busca o snapshot mais recente de cada listing."""
    if not listing_ids:
        return {}

    latest_snap_subq = (
        select(
            ListingSnapshot.listing_id,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
        .group_by(ListingSnapshot.listing_id)
        .subquery()
    )

    result = await db.execute(
        select(ListingSnapshot)
        .join(
            latest_snap_subq,
            (ListingSnapshot.listing_id == latest_snap_subq.c.listing_id)
            & (ListingSnapshot.captured_at == latest_snap_subq.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
    )

    return {snap.listing_id: snap for snap in result.scalars().all()}


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------


async def collect_daily_data(user_id: UUID, db: AsyncSession | None = None) -> list[dict]:
    """
    Coleta dados enriquecidos de TODOS os anuncios ativos do usuario.

    Se `db` nao for fornecido, cria uma sessao propria via AsyncSessionLocal.

    Retorna lista de dicts prontos para o Score Calculator (service_score.py).
    """
    should_close = db is None
    if db is None:
        session = AsyncSessionLocal()
    else:
        session = db

    try:
        return await _collect_daily_data_impl(session, user_id)
    finally:
        if should_close:
            await session.close()


async def _collect_daily_data_impl(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Implementacao interna do collector."""

    # 1. Buscar anuncios ativos do usuario
    listings_result = await db.execute(
        select(Listing).where(
            Listing.user_id == user_id,
            Listing.status == "active",
        )
    )
    listings = listings_result.scalars().all()
    if not listings:
        return []

    listing_ids = [l.id for l in listings]
    listing_by_id = {l.id: l for l in listings}

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    date_7d_ago = today - timedelta(days=6)  # inclusive
    date_15d_ago = today - timedelta(days=14)  # inclusive

    # 2. Buscar custos dos SKUs vinculados
    product_ids = [l.product_id for l in listings if l.product_id]
    product_costs: dict[UUID, Decimal] = {}
    product_skus: dict[UUID, str] = {}
    if product_ids:
        prod_result = await db.execute(
            select(Product.id, Product.cost, Product.sku).where(
                Product.id.in_(product_ids)
            )
        )
        for p in prod_result.fetchall():
            product_costs[p.id] = p.cost
            product_skus[p.id] = p.sku

    # 3. Agregar metricas por periodo (em paralelo logico — queries sequenciais)
    period_today = await _aggregate_period(db, listing_ids, today, today)
    period_yesterday = await _aggregate_period(db, listing_ids, yesterday, yesterday)
    period_7d = await _aggregate_period(db, listing_ids, date_7d_ago, today)
    period_15d = await _aggregate_period(db, listing_ids, date_15d_ago, today)

    # 4. Buscar precos dos concorrentes
    competitor_prices_by_listing = await _get_latest_competitor_prices(db, listing_ids)

    # 5. Buscar snapshot mais recente (para estoque atual)
    latest_snaps = await _get_latest_snapshot_per_listing(db, listing_ids)

    # 6. Montar output enriquecido por anuncio
    empty_period = {"visits": 0, "sales": 0, "conversion": 0.0, "avg_price": 0.0, "revenue": 0.0}
    output: list[dict] = []

    for listing in listings:
        lid = listing.id
        latest_snap = latest_snaps.get(lid)

        # Preco atual — usa snapshot mais recente se disponivel, senao listing.price
        current_price = _safe_float(
            latest_snap.price if latest_snap else listing.price
        )
        stock = int(latest_snap.stock) if latest_snap else 0

        # Custo do SKU vinculado
        cost = 0.0
        sku = listing.seller_sku
        if listing.product_id:
            cost = _safe_float(product_costs.get(listing.product_id, Decimal("0")))
            sku = product_skus.get(listing.product_id, sku)

        # Metricas por periodo
        p_today = period_today.get(lid, empty_period)
        p_yesterday = period_yesterday.get(lid, empty_period)
        p_7d = period_7d.get(lid, empty_period)
        p_15d = period_15d.get(lid, empty_period)

        # avg_price: se nao tem venda no periodo, usa current_price
        for p in [p_today, p_yesterday, p_7d, p_15d]:
            if p["avg_price"] == 0.0:
                p["avg_price"] = current_price

        # Projecao de dias de estoque
        avg_sales_7d_per_day = p_7d["sales"] / 7 if p_7d["sales"] > 0 else 0
        stock_days_projection = None
        if avg_sales_7d_per_day > 0 and stock > 0:
            stock_days_projection = round(stock / avg_sales_7d_per_day, 1)

        # Concorrentes
        comp_prices = competitor_prices_by_listing.get(lid, [])
        comp_min = min(comp_prices) if comp_prices else None
        comp_avg = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else None

        output.append({
            "listing_id": lid,
            "mlb_id": listing.mlb_id,
            "sku": sku,
            "title": listing.title,
            "thumbnail": listing.thumbnail,
            "current_price": current_price,
            "original_price": _safe_float(listing.original_price) or None,
            "stock": stock,
            "cost": cost,
            "listing_type": listing.listing_type,
            "sale_fee_pct": _safe_float(listing.sale_fee_pct) or None,
            "avg_shipping_cost": _safe_float(listing.avg_shipping_cost) or None,
            "periods": {
                "today": p_today,
                "yesterday": p_yesterday,
                "last_7d": p_7d,
                "last_15d": p_15d,
            },
            "stock_days_projection": stock_days_projection,
            "competitor_prices": comp_prices,
            "competitor_min_price": comp_min,
            "competitor_avg_price": comp_avg,
        })

    logger.info(
        "Collector: coletou dados de %d anuncios para user_id=%s",
        len(output),
        user_id,
    )
    return output
