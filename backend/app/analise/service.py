"""
Serviço de análise de anúncios.

Calcula métricas reais de vendas, visitas, conversão e ROAS
a partir dos snapshots históricos dos listings.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import (
    and_,
    case,
    func,
    literal,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ads.models import AdCampaign, AdSnapshot
from app.analise.schemas import AnuncioAnalise
from app.auth.models import MLAccount, User
from app.vendas.models import Listing, ListingSnapshot

# Timezone Brasil
BRT = ZoneInfo("America/Sao_Paulo")


async def get_analysis_listings(
    db: AsyncSession,
    user: User,
) -> list[AnuncioAnalise]:
    """
    Busca todos os listings do usuário com análise completa.

    Calcula métricas reais dos snapshots:
    - visitas_hoje/ontem
    - vendas_hoje/ontem/anteontem/7d
    - conversao_7d/15d/30d
    - roas_7d/15d/30d
    - estoque (último snapshot)

    Returns:
        Lista de AnuncioAnalise ordenada por título.
    """

    # Obter datas em BRT
    now_brt = datetime.now(BRT)
    today = now_brt.date()
    yesterday = today - timedelta(days=1)
    day_before_yesterday = today - timedelta(days=2)
    date_7d_ago = today - timedelta(days=7)
    date_15d_ago = today - timedelta(days=15)
    date_30d_ago = today - timedelta(days=30)

    # Converter para datetime UTC para query
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=BRT)
    yesterday_start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=BRT)
    day_before_yesterday_start = datetime.combine(day_before_yesterday, datetime.min.time()).replace(tzinfo=BRT)
    date_7d_start = datetime.combine(date_7d_ago, datetime.min.time()).replace(tzinfo=BRT)
    date_15d_start = datetime.combine(date_15d_ago, datetime.min.time()).replace(tzinfo=BRT)
    date_30d_start = datetime.combine(date_30d_ago, datetime.min.time()).replace(tzinfo=BRT)

    # Subqueries para snapshots por período
    snapshot_today = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
        func.sum(ListingSnapshot.sales_today).label("sales"),
    ).where(
        and_(
            ListingSnapshot.captured_at >= today_start,
            ListingSnapshot.captured_at < today_start + timedelta(days=1),
        )
    ).group_by(ListingSnapshot.listing_id).cte("snapshot_today")

    snapshot_yesterday = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
        func.sum(ListingSnapshot.sales_today).label("sales"),
    ).where(
        and_(
            ListingSnapshot.captured_at >= yesterday_start,
            ListingSnapshot.captured_at < yesterday_start + timedelta(days=1),
        )
    ).group_by(ListingSnapshot.listing_id).cte("snapshot_yesterday")

    snapshot_day_before = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.sales_today).label("sales"),
    ).where(
        and_(
            ListingSnapshot.captured_at >= day_before_yesterday_start,
            ListingSnapshot.captured_at < day_before_yesterday_start + timedelta(days=1),
        )
    ).group_by(ListingSnapshot.listing_id).cte("snapshot_day_before")

    snapshot_7d = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
        func.sum(ListingSnapshot.sales_today).label("sales"),
    ).where(ListingSnapshot.captured_at >= date_7d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("snapshot_7d")

    snapshot_15d = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
        func.sum(ListingSnapshot.sales_today).label("sales"),
    ).where(ListingSnapshot.captured_at >= date_15d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("snapshot_15d")

    snapshot_30d = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
        func.sum(ListingSnapshot.sales_today).label("sales"),
    ).where(ListingSnapshot.captured_at >= date_30d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("snapshot_30d")

    # Subquery para último snapshot (stock + price)
    latest_snapshot = select(
        ListingSnapshot.listing_id,
        ListingSnapshot.stock,
        ListingSnapshot.price,
    ).distinct(ListingSnapshot.listing_id).order_by(
        ListingSnapshot.listing_id, ListingSnapshot.captured_at.desc()
    ).cte("latest_snapshot")

    # Subquery para ROAS (ads)
    ad_roas_7d = select(
        Listing.id,
        func.avg(AdSnapshot.roas).label("roas"),
    ).join(
        AdCampaign,
        and_(
            AdCampaign.ml_account_id == Listing.ml_account_id,
            # Correlação ad-listing é fraca (ads API não expõe listing_id)
            # Portanto usar ml_account_id como aproximação
        ),
        isouter=True,
    ).join(
        AdSnapshot,
        and_(
            AdSnapshot.campaign_id == AdCampaign.id,
            AdSnapshot.date >= date_7d_ago,
        ),
        isouter=True,
    ).group_by(Listing.id).cte("ad_roas_7d")

    ad_roas_15d = select(
        Listing.id,
        func.avg(AdSnapshot.roas).label("roas"),
    ).join(
        AdCampaign,
        AdCampaign.ml_account_id == Listing.ml_account_id,
        isouter=True,
    ).join(
        AdSnapshot,
        and_(
            AdSnapshot.campaign_id == AdCampaign.id,
            AdSnapshot.date >= date_15d_ago,
        ),
        isouter=True,
    ).group_by(Listing.id).cte("ad_roas_15d")

    ad_roas_30d = select(
        Listing.id,
        func.avg(AdSnapshot.roas).label("roas"),
    ).join(
        AdCampaign,
        AdCampaign.ml_account_id == Listing.ml_account_id,
        isouter=True,
    ).join(
        AdSnapshot,
        and_(
            AdSnapshot.campaign_id == AdCampaign.id,
            AdSnapshot.date >= date_30d_ago,
        ),
        isouter=True,
    ).group_by(Listing.id).cte("ad_roas_30d")

    # Query principal: todos os listings do usuário com métricas calculadas
    stmt = select(
        Listing.mlb_id,
        Listing.title,
        Listing.listing_type,
        Listing.original_price,
        Listing.price,
        Listing.permalink,
        Listing.thumbnail,
        Listing.quality_score,
        # Visitas
        func.coalesce(snapshot_today.c.visits, literal(0)).label("visitas_hoje"),
        func.coalesce(snapshot_yesterday.c.visits, literal(0)).label("visitas_ontem"),
        # Conversão (%)
        case(
            (
                func.coalesce(snapshot_7d.c.visits, 0) > 0,
                (func.coalesce(snapshot_7d.c.sales, 0) / func.coalesce(snapshot_7d.c.visits, 1) * 100),
            ),
            else_=literal(None),
        ).label("conversao_7d"),
        case(
            (
                func.coalesce(snapshot_15d.c.visits, 0) > 0,
                (func.coalesce(snapshot_15d.c.sales, 0) / func.coalesce(snapshot_15d.c.visits, 1) * 100),
            ),
            else_=literal(None),
        ).label("conversao_15d"),
        case(
            (
                func.coalesce(snapshot_30d.c.visits, 0) > 0,
                (func.coalesce(snapshot_30d.c.sales, 0) / func.coalesce(snapshot_30d.c.visits, 1) * 100),
            ),
            else_=literal(None),
        ).label("conversao_30d"),
        # Vendas
        func.coalesce(snapshot_today.c.sales, literal(0)).label("vendas_hoje"),
        func.coalesce(snapshot_yesterday.c.sales, literal(0)).label("vendas_ontem"),
        func.coalesce(snapshot_day_before.c.sales, literal(0)).label("vendas_anteontem"),
        func.coalesce(snapshot_7d.c.sales, literal(0)).label("vendas_7d"),
        # Estoque (último snapshot)
        func.coalesce(latest_snapshot.c.stock, literal(0)).label("estoque"),
        # ROAS (%)
        func.coalesce(ad_roas_7d.c.roas, literal(None)).label("roas_7d"),
        func.coalesce(ad_roas_15d.c.roas, literal(None)).label("roas_15d"),
        func.coalesce(ad_roas_30d.c.roas, literal(None)).label("roas_30d"),
    ).where(Listing.user_id == user.id).join(
        snapshot_today,
        Listing.id == snapshot_today.c.listing_id,
        isouter=True,
    ).join(
        snapshot_yesterday,
        Listing.id == snapshot_yesterday.c.listing_id,
        isouter=True,
    ).join(
        snapshot_day_before,
        Listing.id == snapshot_day_before.c.listing_id,
        isouter=True,
    ).join(
        snapshot_7d,
        Listing.id == snapshot_7d.c.listing_id,
        isouter=True,
    ).join(
        snapshot_15d,
        Listing.id == snapshot_15d.c.listing_id,
        isouter=True,
    ).join(
        snapshot_30d,
        Listing.id == snapshot_30d.c.listing_id,
        isouter=True,
    ).join(
        latest_snapshot,
        Listing.id == latest_snapshot.c.listing_id,
        isouter=True,
    ).join(
        ad_roas_7d,
        Listing.id == ad_roas_7d.c.id,
        isouter=True,
    ).join(
        ad_roas_15d,
        Listing.id == ad_roas_15d.c.id,
        isouter=True,
    ).join(
        ad_roas_30d,
        Listing.id == ad_roas_30d.c.id,
        isouter=True,
    ).order_by(Listing.title)

    result = await db.execute(stmt)
    rows = result.all()

    # Converter rows em AnuncioAnalise
    anuncios = []
    for row in rows:
        # Conversão de valores (tratar Decimal)
        conversao_7d = float(row.conversao_7d) if row.conversao_7d is not None else None
        conversao_15d = float(row.conversao_15d) if row.conversao_15d is not None else None
        conversao_30d = float(row.conversao_30d) if row.conversao_30d is not None else None

        roas_7d = float(row.roas_7d) if row.roas_7d is not None else None
        roas_15d = float(row.roas_15d) if row.roas_15d is not None else None
        roas_30d = float(row.roas_30d) if row.roas_30d is not None else None

        preco = float(row.price) if row.price else 0.0
        preco_original = float(row.original_price) if row.original_price else None

        anuncio = AnuncioAnalise(
            mlb_id=row.mlb_id,
            titulo=row.title,
            descricao=None,  # Campo não está no Listing model, será None
            tipo=row.listing_type,
            preco=preco,
            preco_original=preco_original,
            visitas_hoje=row.visitas_hoje or 0,
            visitas_ontem=row.visitas_ontem or 0,
            conversao_7d=conversao_7d,
            conversao_15d=conversao_15d,
            conversao_30d=conversao_30d,
            vendas_hoje=row.vendas_hoje or 0,
            vendas_ontem=row.vendas_ontem or 0,
            vendas_anteontem=row.vendas_anteontem or 0,
            vendas_7d=row.vendas_7d or 0,
            estoque=row.estoque or 0,
            roas_7d=roas_7d,
            roas_15d=roas_15d,
            roas_30d=roas_30d,
            thumbnail=row.thumbnail,
            permalink=row.permalink,
            quality_score=row.quality_score,
        )
        anuncios.append(anuncio)

    return anuncios
