"""
Serviço de análise de anúncios.

Calcula métricas reais de vendas, visitas, conversão e ROAS
a partir dos snapshots históricos dos listings e da tabela Order.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import (
    and_,
    case,
    func,
    literal,
    select,
    Float,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.analise.schemas import AnuncioAnalise
from app.auth.models import User, MLAccount
from app.mercadolivre.client import MLClient
from app.vendas.models import Listing, ListingSnapshot, Order

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

    # CTE para ml_account_ids do usuário
    user_accounts = select(MLAccount.id).where(MLAccount.user_id == user.id).cte("user_accounts")

    # === VISITAS (via ListingSnapshot) ===
    snapshot_today = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
    ).where(
        and_(
            ListingSnapshot.captured_at >= today_start,
            ListingSnapshot.captured_at < today_start + timedelta(days=1),
        )
    ).group_by(ListingSnapshot.listing_id).cte("snapshot_today")

    snapshot_yesterday = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
    ).where(
        and_(
            ListingSnapshot.captured_at >= yesterday_start,
            ListingSnapshot.captured_at < yesterday_start + timedelta(days=1),
        )
    ).group_by(ListingSnapshot.listing_id).cte("snapshot_yesterday")

    snapshot_7d = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
    ).where(ListingSnapshot.captured_at >= date_7d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("snapshot_7d")

    snapshot_15d = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
    ).where(ListingSnapshot.captured_at >= date_15d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("snapshot_15d")

    snapshot_30d = select(
        ListingSnapshot.listing_id,
        func.sum(ListingSnapshot.visits).label("visits"),
    ).where(ListingSnapshot.captured_at >= date_30d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("snapshot_30d")

    # === VENDAS (via Order table) ===
    # Vendas de hoje (approved orders)
    orders_today = select(
        Order.listing_id,
        func.coalesce(func.sum(Order.quantity), 0).label("sales"),
    ).where(
        and_(
            Order.ml_account_id.in_(select(user_accounts.c.id)),
            Order.order_date >= today_start,
            Order.order_date < today_start + timedelta(days=1),
            Order.payment_status == "approved",
        )
    ).group_by(Order.listing_id).cte("orders_today")

    # Vendas de ontem (approved orders)
    orders_yesterday = select(
        Order.listing_id,
        func.coalesce(func.sum(Order.quantity), 0).label("sales"),
    ).where(
        and_(
            Order.ml_account_id.in_(select(user_accounts.c.id)),
            Order.order_date >= yesterday_start,
            Order.order_date < yesterday_start + timedelta(days=1),
            Order.payment_status == "approved",
        )
    ).group_by(Order.listing_id).cte("orders_yesterday")

    # Vendas de anteontem (approved orders)
    orders_day_before = select(
        Order.listing_id,
        func.coalesce(func.sum(Order.quantity), 0).label("sales"),
    ).where(
        and_(
            Order.ml_account_id.in_(select(user_accounts.c.id)),
            Order.order_date >= day_before_yesterday_start,
            Order.order_date < day_before_yesterday_start + timedelta(days=1),
            Order.payment_status == "approved",
        )
    ).group_by(Order.listing_id).cte("orders_day_before")

    # Vendas 7d (approved orders)
    orders_7d = select(
        Order.listing_id,
        func.coalesce(func.sum(Order.quantity), 0).label("sales"),
    ).where(
        and_(
            Order.ml_account_id.in_(select(user_accounts.c.id)),
            Order.order_date >= date_7d_start,
            Order.payment_status == "approved",
        )
    ).group_by(Order.listing_id).cte("orders_7d")

    # Vendas 15d (approved orders)
    orders_15d = select(
        Order.listing_id,
        func.coalesce(func.sum(Order.quantity), 0).label("sales"),
    ).where(
        and_(
            Order.ml_account_id.in_(select(user_accounts.c.id)),
            Order.order_date >= date_15d_start,
            Order.payment_status == "approved",
        )
    ).group_by(Order.listing_id).cte("orders_15d")

    # Vendas 30d (approved orders)
    orders_30d = select(
        Order.listing_id,
        func.coalesce(func.sum(Order.quantity), 0).label("sales"),
    ).where(
        and_(
            Order.ml_account_id.in_(select(user_accounts.c.id)),
            Order.order_date >= date_30d_start,
            Order.payment_status == "approved",
        )
    ).group_by(Order.listing_id).cte("orders_30d")

    # Contagem de dias com dados (para validar conversão)
    days_with_data_7d = select(
        ListingSnapshot.listing_id,
        func.count(func.distinct(func.date_trunc('day', ListingSnapshot.captured_at))).label("days_count"),
    ).where(ListingSnapshot.captured_at >= date_7d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("days_with_data_7d")

    days_with_data_15d = select(
        ListingSnapshot.listing_id,
        func.count(func.distinct(func.date_trunc('day', ListingSnapshot.captured_at))).label("days_count"),
    ).where(ListingSnapshot.captured_at >= date_15d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("days_with_data_15d")

    days_with_data_30d = select(
        ListingSnapshot.listing_id,
        func.count(func.distinct(func.date_trunc('day', ListingSnapshot.captured_at))).label("days_count"),
    ).where(ListingSnapshot.captured_at >= date_30d_start).group_by(
        ListingSnapshot.listing_id
    ).cte("days_with_data_30d")

    # Subquery para último snapshot (stock + price)
    latest_snapshot = select(
        ListingSnapshot.listing_id,
        ListingSnapshot.stock,
        ListingSnapshot.price,
    ).distinct(ListingSnapshot.listing_id).order_by(
        ListingSnapshot.listing_id, ListingSnapshot.captured_at.desc()
    ).cte("latest_snapshot")

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
        # Conversão (%) — usa visitas dos snapshots e vendas do Order
        case(
            (
                and_(
                    func.coalesce(snapshot_7d.c.visits, 0) >= 50,
                    func.coalesce(orders_7d.c.sales, 0) > 0,
                ),
                (func.cast(orders_7d.c.sales, Float) / func.cast(snapshot_7d.c.visits, Float) * 100),
            ),
            else_=literal(None),
        ).label("conversao_7d"),
        case(
            (
                and_(
                    func.coalesce(snapshot_15d.c.visits, 0) >= 50,
                    func.coalesce(orders_15d.c.sales, 0) > 0,
                ),
                (func.cast(orders_15d.c.sales, Float) / func.cast(snapshot_15d.c.visits, Float) * 100),
            ),
            else_=literal(None),
        ).label("conversao_15d"),
        case(
            (
                and_(
                    func.coalesce(snapshot_30d.c.visits, 0) >= 50,
                    func.coalesce(orders_30d.c.sales, 0) > 0,
                ),
                (func.cast(orders_30d.c.sales, Float) / func.cast(snapshot_30d.c.visits, Float) * 100),
            ),
            else_=literal(None),
        ).label("conversao_30d"),
        # Vendas (via Order table)
        func.coalesce(orders_today.c.sales, literal(0)).label("vendas_hoje"),
        func.coalesce(orders_yesterday.c.sales, literal(0)).label("vendas_ontem"),
        func.coalesce(orders_day_before.c.sales, literal(0)).label("vendas_anteontem"),
        func.coalesce(orders_7d.c.sales, literal(0)).label("vendas_7d"),
        # Dias com dados (para validação de conversão)
        func.coalesce(days_with_data_7d.c.days_count, literal(0)).label("dias_dados_7d"),
        func.coalesce(days_with_data_15d.c.days_count, literal(0)).label("dias_dados_15d"),
        func.coalesce(days_with_data_30d.c.days_count, literal(0)).label("dias_dados_30d"),
        # Estoque (último snapshot)
        func.coalesce(latest_snapshot.c.stock, literal(0)).label("estoque"),
    ).where(Listing.user_id == user.id).join(
        snapshot_today,
        Listing.id == snapshot_today.c.listing_id,
        isouter=True,
    ).join(
        snapshot_yesterday,
        Listing.id == snapshot_yesterday.c.listing_id,
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
        orders_today,
        Listing.id == orders_today.c.listing_id,
        isouter=True,
    ).join(
        orders_yesterday,
        Listing.id == orders_yesterday.c.listing_id,
        isouter=True,
    ).join(
        orders_day_before,
        Listing.id == orders_day_before.c.listing_id,
        isouter=True,
    ).join(
        orders_7d,
        Listing.id == orders_7d.c.listing_id,
        isouter=True,
    ).join(
        orders_15d,
        Listing.id == orders_15d.c.listing_id,
        isouter=True,
    ).join(
        orders_30d,
        Listing.id == orders_30d.c.listing_id,
        isouter=True,
    ).join(
        days_with_data_7d,
        Listing.id == days_with_data_7d.c.listing_id,
        isouter=True,
    ).join(
        days_with_data_15d,
        Listing.id == days_with_data_15d.c.listing_id,
        isouter=True,
    ).join(
        days_with_data_30d,
        Listing.id == days_with_data_30d.c.listing_id,
        isouter=True,
    ).join(
        latest_snapshot,
        Listing.id == latest_snapshot.c.listing_id,
        isouter=True,
    ).order_by(Listing.title)

    result = await db.execute(stmt)
    rows = result.all()

    # Buscar dados de ads via API ML (ROAS/ACOS por item)
    # Montar dicionário: mlb_id -> {roas_7d, roas_15d, roas_30d, acos_7d, acos_15d, acos_30d}
    ads_by_item = {}

    # Pegar contas ML ativas do usuário
    accounts_stmt = select(MLAccount).where(
        and_(MLAccount.user_id == user.id, MLAccount.is_active == True)
    )
    accounts_result = await db.execute(accounts_stmt)
    ml_accounts = accounts_result.scalars().all()

    # Para cada conta, buscar advertiser_id e métricas
    for account in ml_accounts:
        async with MLClient(account.access_token) as client:
            advertiser_id = await client.get_advertiser_id()

            if not advertiser_id:
                # Conta não tem acesso a Product Ads — skip
                continue

            # Buscar métricas para 7d, 15d, 30d
            for period_name, date_start in [
                ("7d", date_7d_ago),
                ("15d", date_15d_ago),
                ("30d", date_30d_ago),
            ]:
                try:
                    items = await client.get_product_ads_items(
                        advertiser_id,
                        date_from=date_start.isoformat(),
                        date_to=today.isoformat(),
                    )

                    for item in items:
                        # Normalizar item_id (remover hífens, maiúsculas)
                        item_id_raw = item.get("item_id", "").upper().replace("-", "")
                        if not item_id_raw:
                            continue

                        # Garantir que começa com MLB
                        if not item_id_raw.startswith("MLB"):
                            item_id_raw = f"MLB{item_id_raw}"

                        if item_id_raw not in ads_by_item:
                            ads_by_item[item_id_raw] = {}

                        # Armazenar ROAS e ACOS (já em %)
                        ads_by_item[item_id_raw][f"roas_{period_name}"] = item.get("roas")
                        ads_by_item[item_id_raw][f"acos_{period_name}"] = item.get("acos")
                except Exception:
                    # Erro ao buscar métricas de uma conta — continua com outras contas
                    continue

    # Converter rows em AnuncioAnalise
    anuncios = []
    for row in rows:
        # Conversão de valores (tratar Decimal)
        conversao_7d = float(row.conversao_7d) if row.conversao_7d is not None else None
        conversao_15d = float(row.conversao_15d) if row.conversao_15d is not None else None
        conversao_30d = float(row.conversao_30d) if row.conversao_30d is not None else None

        preco = float(row.price) if row.price else 0.0
        preco_original = float(row.original_price) if row.original_price else None

        # Normalizar MLB ID para lookup em ads_by_item
        mlb_id_normalized = row.mlb_id.upper().replace("-", "")
        if not mlb_id_normalized.startswith("MLB"):
            mlb_id_normalized = f"MLB{mlb_id_normalized}"

        # Buscar ROAS/ACOS de ads_by_item
        ads_data = ads_by_item.get(mlb_id_normalized, {})
        roas_7d = ads_data.get("roas_7d")
        roas_15d = ads_data.get("roas_15d")
        roas_30d = ads_data.get("roas_30d")
        acos_7d = ads_data.get("acos_7d")
        acos_15d = ads_data.get("acos_15d")
        acos_30d = ads_data.get("acos_30d")

        # Converter para float se não None
        if roas_7d is not None:
            roas_7d = float(roas_7d)
        if roas_15d is not None:
            roas_15d = float(roas_15d)
        if roas_30d is not None:
            roas_30d = float(roas_30d)
        if acos_7d is not None:
            acos_7d = float(acos_7d)
        if acos_15d is not None:
            acos_15d = float(acos_15d)
        if acos_30d is not None:
            acos_30d = float(acos_30d)

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
            dias_dados_7d=row.dias_dados_7d or 0,
            dias_dados_15d=row.dias_dados_15d or 0,
            dias_dados_30d=row.dias_dados_30d or 0,
            estoque=row.estoque or 0,
            roas_7d=roas_7d,
            roas_15d=roas_15d,
            roas_30d=roas_30d,
            acos_7d=acos_7d,
            acos_15d=acos_15d,
            acos_30d=acos_30d,
            thumbnail=row.thumbnail,
            permalink=row.permalink,
            quality_score=row.quality_score,
        )
        anuncios.append(anuncio)

    return anuncios
