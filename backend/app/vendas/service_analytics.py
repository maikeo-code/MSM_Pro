"""
Análise de anúncios, funil de conversão e heatmap de vendas.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

# Timezone BRT (UTC-3)
BRT = timezone(timedelta(hours=-3))

from fastapi import HTTPException, status
from sqlalchemy import cast, Date, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from app.vendas.service_calculations import (
    _calculate_price_bands,
    _calculate_stock_projection,
    _generate_alerts,
)
from app.vendas.service_mock import _generate_mock_analysis

_DAY_NAMES = [
    "Segunda-feira",
    "Terca-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sabado",
    "Domingo",
]


async def get_funnel_analytics(
    db: AsyncSession, user_id: UUID, period_days: int = 7, ml_account_id: UUID | None = None
) -> dict:
    """
    FEATURE 2: Funil de conversão — agrega visitas, vendas, conversão e receita
    de todos os anúncios do usuário no período selecionado.

    Se ml_account_id for fornecido, filtra apenas os dados dessa conta ML.
    """
    # Busca listing_ids do usuário (opcional: filtra por conta ML)
    query = select(Listing.id).where(Listing.user_id == user_id)
    if ml_account_id is not None:
        query = query.where(Listing.ml_account_id == ml_account_id)

    listings_result = await db.execute(query)
    listing_ids = [row[0] for row in listings_result.fetchall()]

    if not listing_ids:
        return {"visitas": 0, "vendas": 0, "conversao": 0.0, "receita": 0.0}

    today_dt = datetime.now(BRT).date()
    date_from = today_dt - timedelta(days=period_days - 1)

    # Subquery: último snapshot de cada listing em cada dia do intervalo
    latest_per_day = (
        select(
            ListingSnapshot.listing_id,
            cast(ListingSnapshot.captured_at, Date).label("snap_date"),
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            cast(ListingSnapshot.captured_at, Date) >= date_from,
            cast(ListingSnapshot.captured_at, Date) <= today_dt,
        )
        .group_by(ListingSnapshot.listing_id, cast(ListingSnapshot.captured_at, Date))
        .subquery()
    )

    # Use COALESCE(revenue, price * sales_today) para calcular receita
    # quando revenue é null (snapshots antigos sem dados de orders)
    receita_expr = func.coalesce(
        ListingSnapshot.revenue,
        ListingSnapshot.price * ListingSnapshot.sales_today,
    )

    result = await db.execute(
        select(
            func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visitas"),
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
            func.coalesce(func.sum(receita_expr), 0).label("receita"),
        )
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
    )
    row = result.fetchone()

    visitas = int(row.visitas) if row else 0
    vendas = int(row.vendas) if row else 0
    receita = float(row.receita) if row else 0.0
    conversao = round((vendas / visitas * 100), 2) if visitas > 0 else 0.0

    return {
        "visitas": visitas,
        "vendas": vendas,
        "conversao": conversao,
        "receita": receita,
    }


async def get_listing_snapshots(
    db: AsyncSession, mlb_id: str, user_id: UUID, dias: int = 30
) -> list[ListingSnapshot]:
    """Retorna histórico de snapshots de um anúncio."""
    from app.vendas.service import get_listing

    listing = await get_listing(db, mlb_id, user_id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=dias)
    result = await db.execute(
        select(ListingSnapshot)
        .where(
            ListingSnapshot.listing_id == listing.id,
            ListingSnapshot.captured_at >= cutoff,
        )
        .order_by(ListingSnapshot.captured_at.asc())
    )
    return list(result.scalars().all())


async def _fetch_ads_for_listing(db: AsyncSession, listing) -> dict:
    """
    Busca dados de publicidade do anúncio via ML API.
    Usa get_item_ads() do MLClient com o token da conta ML vinculada ao listing.
    Retorna {} graciosamente se não tiver token, permissão (403) ou dado.
    """
    try:
        from app.auth.models import MLAccount
        from app.mercadolivre.client import MLClient

        result = await db.execute(
            select(MLAccount).where(MLAccount.id == listing.ml_account_id)
        )
        ml_account = result.scalar_one_or_none()
        if not ml_account or not ml_account.access_token:
            return {}

        async with MLClient(ml_account.access_token) as ml_client:
            ads_data = await ml_client.get_item_ads(listing.mlb_id)
            return ads_data or {}
    except Exception:
        return {}


async def _fetch_promotions_for_listing(db: AsyncSession, listing) -> list[dict]:
    """
    Busca promoções ativas de um anúncio via ML API.
    Usa get_item_promotions() do MLClient com o token da conta ML vinculada.
    Retorna [] graciosamente se não tiver token, permissão (403) ou dado.
    """
    try:
        from app.auth.models import MLAccount
        from app.mercadolivre.client import MLClient

        result = await db.execute(
            select(MLAccount).where(MLAccount.id == listing.ml_account_id)
        )
        ml_account = result.scalar_one_or_none()
        if not ml_account or not ml_account.access_token:
            return []

        async with MLClient(ml_account.access_token) as ml_client:
            promo_data = await ml_client.get_item_promotions(listing.mlb_id)
            if not isinstance(promo_data, list):
                return []

            promotions = []
            for p in promo_data[:5]:  # max 5 promoções
                # Calcula desconto percentual quando preços estão disponíveis
                discount_pct = None
                orig = p.get("original_price") or p.get("price")
                promo_price = p.get("price")
                if orig and promo_price and float(orig) > 0:
                    discount_pct = round((1 - float(promo_price) / float(orig)) * 100, 1)

                promotions.append({
                    "id": p.get("id", ""),
                    "type": p.get("type", ""),
                    "status": p.get("status", ""),
                    "start_date": p.get("start_date"),
                    "end_date": p.get("finish_date"),
                    "discount_pct": discount_pct,
                })
            return promotions
    except Exception:
        return []


async def get_listing_analysis(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    days: int = 30,
) -> dict:
    """
    Retorna análise completa de um anúncio com:
    - Dados do listing e SKU
    - Snapshots históricos
    - Faixas de preço e margem ótima
    - Projeção de estoque
    - Promoções ativas
    - Dados de publicidade
    - Concorrente vinculado
    - Alertas inteligentes
    """
    from app.produtos.models import Product
    from app.vendas.service import get_listing

    # Tenta buscar listing — se não existir, retorna mock baseado no mlb_id
    try:
        listing = await get_listing(db, mlb_id, user_id)
    except HTTPException:
        # Listing ainda não cadastrado — retorna mock realista para preview
        from types import SimpleNamespace
        mock_listing = SimpleNamespace(
            mlb_id=mlb_id,
            title=f"Anúncio {mlb_id} (demonstração)",
            price=Decimal("409.00"),
            listing_type="full",
            status="active",
            thumbnail=None,
            permalink=f"https://www.mercadolivre.com.br/p/{mlb_id}",
            product_id=None,
        )
        return _generate_mock_analysis(mock_listing, None)

    # Corpo principal com fallback para mock em caso de erro inesperado
    try:
        return await _build_listing_analysis(db, listing, mlb_id, user_id, days)
    except HTTPException:
        raise  # Re-raise HTTP errors (404, 401, etc.)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            "Erro inesperado em get_listing_analysis(%s): %s", mlb_id, exc, exc_info=True
        )
        # Fallback gracioso: retorna mock em vez de 500
        return _generate_mock_analysis(listing, None)


async def _build_listing_analysis(
    db: AsyncSession,
    listing,
    mlb_id: str,
    user_id: UUID,
    days: int,
) -> dict:
    """Constroi a analise completa a partir de dados reais."""
    from app.produtos.models import Product

    # Busca SKU (pode ser None se product_id não está cadastrado)
    product = None
    if listing.product_id:
        product_result = await db.execute(
            select(Product).where(Product.id == listing.product_id)
        )
        product = product_result.scalar_one_or_none()

    # Determina se temos custo real — margem será estimada se não tiver
    sku_cost = Decimal(str(product.cost)) if product and product.cost else Decimal("0")
    is_mock = not product or not product.cost

    # Busca snapshots reais do banco
    snapshots_db = await get_listing_snapshots(db, mlb_id, user_id, days)

    if not snapshots_db:
        # Sem dados de snapshot ainda — retorna mock completo
        return _generate_mock_analysis(listing, product)

    # Converte para dicts — inclui todos os campos de analytics
    snapshots = [
        {
            "id": str(s.id),
            "listing_id": str(s.listing_id),
            "price": float(s.price),
            "visits": s.visits,
            "sales_today": s.sales_today,
            "questions": s.questions,
            "stock": s.stock,
            "conversion_rate": float(s.conversion_rate) if s.conversion_rate else 0,
            "captured_at": s.captured_at.isoformat() if s.captured_at else None,
            # Campos de analytics de pedidos (podem ser None em snapshots antigos)
            "orders_count": s.orders_count if s.orders_count is not None else 0,
            "revenue": float(s.revenue) if s.revenue is not None else None,
            "avg_selling_price": float(s.avg_selling_price) if s.avg_selling_price is not None else None,
            "cancelled_orders": s.cancelled_orders if s.cancelled_orders is not None else 0,
            # Campos novos (migration 0005) — None se snapshot antigo
            "cancelled_revenue": float(s.cancelled_revenue) if s.cancelled_revenue is not None else 0.0,
            "returns_count": s.returns_count if s.returns_count is not None else 0,
            "returns_revenue": float(s.returns_revenue) if s.returns_revenue is not None else 0.0,
        }
        for s in snapshots_db
    ]

    cost = sku_cost

    # Calcula faixas de preço
    price_bands = _calculate_price_bands(snapshots, cost, listing.listing_type)

    # Calcula projeção de estoque
    last_stock = snapshots[-1]["stock"] if snapshots else 0
    stock_projection = _calculate_stock_projection(last_stock, snapshots)

    # Busca concorrente vinculado (primeiro encontrado para este SKU)
    from app.concorrencia.models import Competitor, CompetitorSnapshot

    competitor = None
    if listing.product_id:
        competitor_result = await db.execute(
            select(Competitor)
            .join(Listing, Competitor.listing_id == Listing.id)
            .where(Listing.product_id == listing.product_id, Listing.user_id == user_id)
            .limit(1)
        )
        competitor = competitor_result.scalar_one_or_none()

    competitor_price = None
    comp_snapshot = None  # BUG 3 FIX: garantir que comp_snapshot existe antes do return
    if competitor:
        comp_snap_result = await db.execute(
            select(CompetitorSnapshot)
            .where(CompetitorSnapshot.competitor_id == competitor.id)
            .order_by(desc(CompetitorSnapshot.captured_at))
            .limit(1)
        )
        comp_snapshot = comp_snap_result.scalar_one_or_none()
        if comp_snapshot:
            competitor_price = comp_snapshot.price

    # Gera alertas
    alerts = _generate_alerts(
        snapshots,
        stock_projection,
        competitor_price,
        Decimal(str(snapshots[-1]["price"])) if snapshots else listing.price,
    )

    # Retorna análise completa (is_mock=True indica apenas que margem é estimada, dados são reais)
    return {
        "is_mock": is_mock,
        "listing": {
            "mlb_id": listing.mlb_id,
            "title": listing.title,
            "price": float(listing.price),
            "listing_type": listing.listing_type,
            "status": listing.status,
            "thumbnail": listing.thumbnail,
            "permalink": listing.permalink,
        },
        "sku": {
            "id": str(product.id) if product else None,
            "sku": product.sku if product else None,
            "cost": float(cost),
        },
        "snapshots": snapshots,
        "price_bands": price_bands,
        "full_stock": stock_projection,
        "promotions": await _fetch_promotions_for_listing(db, listing),
        "ads": await _fetch_ads_for_listing(db, listing),
        "competitor": {
            "mlb_id": competitor.mlb_id,
            "price": float(competitor_price),
            "last_updated": comp_snapshot.captured_at.isoformat() if comp_snapshot else None,
        } if competitor and competitor_price else None,
        "alerts": alerts,
    }


async def get_sales_heatmap(
    db: AsyncSession,
    user_id: UUID,
    period_days: int = 30,
    ml_account_id: UUID | None = None,
) -> dict:
    """
    Retorna heatmap de vendas nos ultimos N dias.

    Estrategia:
    1. Tenta usar tabela Order (granularidade dia+hora) via extract('dow') e extract('hour')
    2. Se nao houver Orders suficientes (< 3 registros), faz FALLBACK para ListingSnapshots por dia

    Se ml_account_id for fornecido, filtra apenas os dados dessa conta ML.

    Retorno: HeatmapOut com has_hourly_data indicando qual estrategia foi usada.
    Dia da semana padronizado: 0=segunda, 6=domingo (Python weekday()).
    """
    from app.auth.models import MLAccount  # noqa: F401
    from app.vendas.models import Order
    from app.vendas.schemas import HeatmapCell, HeatmapOut

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

    # ── 1. Tentar estrategia Orders (dia+hora) ───────────────────────────────
    # Agrupa por (dow_postgres, hour) usando extract. PostgreSQL DOW: 0=domingo, 6=sabado
    # Convertemos para Python weekday (0=segunda) logo apos.
    # BUG 1 FIX: converter para BRT antes de extrair hora e dia da semana
    order_date_brt = func.timezone(text("'America/Sao_Paulo'"), Order.order_date)
    query = (
        select(
            func.extract("dow", order_date_brt).label("pg_dow"),
            func.extract("hour", order_date_brt).label("hour"),
            func.count(Order.id).label("cnt"),
        )
        .join(MLAccount, Order.ml_account_id == MLAccount.id)
        .where(
            MLAccount.user_id == user_id,
            Order.order_date >= cutoff,
            Order.payment_status == "approved",
        )
    )

    # Filtro opcional por ml_account_id
    if ml_account_id is not None:
        query = query.where(Order.ml_account_id == ml_account_id)

    query = query.group_by("pg_dow", "hour")

    order_agg_result = await db.execute(query)
    order_rows = order_agg_result.fetchall()

    # BUG 3 FIX: aumentar threshold de 3 para 10 para garantir dados estatisticamente relevantes
    has_hourly_data = len(order_rows) >= 10

    if has_hourly_data:
        # ── Estrategia Orders (7×24 grid) ───────────────────────────────────
        # Converte PG DOW (0=dom) para Python weekday (0=seg)
        # pg_dow 0(dom)→6, 1(seg)→0, 2(ter)→1 ... 6(sab)→5
        grid: dict[tuple[int, int], int] = {}  # (py_weekday, hour) → count
        total_orders_hourly = 0

        for row in order_rows:
            pg_dow = int(row.pg_dow)
            hour = int(row.hour)
            # pg_dow 0=domingo → py_weekday 6; pg_dow 1=segunda → 0; etc
            py_weekday = (pg_dow - 1) % 7
            cnt = int(row.cnt)
            grid[(py_weekday, hour)] = grid.get((py_weekday, hour), 0) + cnt
            total_orders_hourly += cnt

        avg_daily_hourly = total_orders_hourly / period_days if period_days > 0 else 0.0

        # Encontra pico (dia, hora)
        if grid:
            peak_key = max(grid, key=lambda k: grid[k])
            peak_day_idx = peak_key[0]
            peak_hour_val = peak_key[1]
        else:
            peak_day_idx, peak_hour_val = 0, 0

        peak_hour_str = f"{peak_hour_val:02d}:00-{(peak_hour_val + 1):02d}:00"

        # Monta celulas — uma por combinacao (dia, hora) presente; inclui zeros
        cells = []
        for day_idx in range(7):
            for hour in range(24):
                cnt = grid.get((day_idx, hour), 0)
                cells.append(
                    HeatmapCell(
                        day_of_week=day_idx,
                        hour=hour,
                        day_name=_DAY_NAMES[day_idx],
                        count=cnt,
                        avg_per_week=0.0,
                    )
                )

        return HeatmapOut(
            period_days=period_days,
            total_sales=total_orders_hourly,
            avg_daily=round(avg_daily_hourly, 2),
            peak_day=_DAY_NAMES[peak_day_idx],
            peak_day_index=peak_day_idx,
            peak_hour=peak_hour_str,
            has_hourly_data=True,
            data=cells,
        ).model_dump()

    # ── 2. FALLBACK: ListingSnapshots por dia ────────────────────────────────
    snap_query = (
        select(ListingSnapshot)
        .join(Listing, ListingSnapshot.listing_id == Listing.id)
        .where(
            Listing.user_id == user_id,
            ListingSnapshot.captured_at >= cutoff,
        )
    )

    # Filtro opcional por ml_account_id
    if ml_account_id is not None:
        snap_query = snap_query.where(Listing.ml_account_id == ml_account_id)

    snaps_result = await db.execute(snap_query)
    snapshots = snaps_result.scalars().all()

    # BUG 2 FIX: remover duplicatas de snapshots do mesmo dia (pegar apenas o último)
    # Se há múltiplos snapshots no mesmo dia, pegar apenas o mais recente para não inflar números
    from collections import defaultdict
    last_snap_per_day: dict[tuple, any] = {}  # key=(listing_id, date_only) -> snapshot

    for snap in snapshots:
        dt = snap.captured_at
        if hasattr(dt, 'astimezone'):
            # Converter para BRT se não está já
            try:
                brt_tz = timezone(timedelta(hours=-3))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc).astimezone(brt_tz)
                else:
                    dt = dt.astimezone(brt_tz)
            except Exception:
                pass  # Se falhar a conversão, manter dt original

        key = (snap.listing_id, dt.date())
        if key not in last_snap_per_day or snap.captured_at > last_snap_per_day[key].captured_at:
            last_snap_per_day[key] = snap

    counts_by_day: dict[int, int] = {i: 0 for i in range(7)}

    for (listing_id, snap_date), snap in last_snap_per_day.items():
        day_idx = snap_date.weekday()  # 0=segunda, 6=domingo (já em BRT)
        sales = (
            (snap.orders_count or 0)
            if (snap.orders_count is not None and snap.orders_count > 0)
            else (snap.sales_today or 0)
        )
        counts_by_day[day_idx] += sales

    total_sales = sum(counts_by_day.values())
    avg_daily = total_sales / period_days if period_days > 0 else 0.0
    peak_day_idx = max(counts_by_day, key=lambda d: counts_by_day[d])
    num_weeks = max(1, period_days / 7)

    cells = []
    for day_idx in range(7):
        total_for_day = counts_by_day[day_idx]
        cells.append(
            HeatmapCell(
                day_of_week=day_idx,
                hour=0,
                day_name=_DAY_NAMES[day_idx],
                count=total_for_day,
                avg_per_week=round(total_for_day / num_weeks, 2),
            )
        )

    return HeatmapOut(
        period_days=period_days,
        total_sales=total_sales,
        avg_daily=round(avg_daily, 2),
        peak_day=_DAY_NAMES[peak_day_idx],
        peak_day_index=peak_day_idx,
        peak_hour="",
        has_hourly_data=False,
        data=cells,
    ).model_dump()


async def get_search_position(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    keyword: str,
) -> dict:
    """
    Busca a posicao de um anuncio nos resultados de busca do ML para uma keyword.

    Pagina ate 200 resultados (4 paginas x 50) usando a Search API publica.
    Retorna posicao 1-based se encontrado, ou found=False se nao aparecer.

    Verifica ownership: o listing deve pertencer ao usuario autenticado.
    O endpoint de busca do ML e publico — nao precisa de token ML.
    """
    from app.auth.models import MLAccount
    from app.mercadolivre.client import MLClient, MLClientError
    from app.vendas.service import get_listing

    # Verificar que o listing pertence ao usuario
    try:
        listing = await get_listing(db, mlb_id, user_id)
    except HTTPException:
        raise

    # Normalizar o mlb_id alvo para comparacao
    target_id = mlb_id.upper().replace("-", "")
    if not target_id.startswith("MLB"):
        target_id = f"MLB{target_id}"

    # Buscar conta ML do listing para usar o cliente (precisamos de token para o rate-limiter)
    # O endpoint /sites/MLB/search e publico, mas o MLClient exige token no construtor.
    # Buscamos qualquer conta ativa do usuario para construir o cliente.
    acc_result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == user_id,
            MLAccount.is_active == True,  # noqa: E712
        ).limit(1)
    )
    account = acc_result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhuma conta ML conectada. Conecte uma conta ML para usar esta funcionalidade.",
        )

    # Paginacao: ate 4 paginas de 50 = 200 resultados maximos
    MAX_PAGES = 4
    PAGE_SIZE = 50

    total_results: int | None = None
    searched_pages = 0

    async with MLClient(access_token=account.access_token) as client:
        for page_idx in range(MAX_PAGES):
            offset = page_idx * PAGE_SIZE
            try:
                data = await client.search_items(
                    query=keyword,
                    offset=offset,
                    limit=PAGE_SIZE,
                )
            except MLClientError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Erro ao consultar Search API do ML: {exc}",
                )

            searched_pages += 1

            paging = data.get("paging", {})
            if total_results is None:
                total_results = paging.get("total", 0)

            results = data.get("results", [])

            for idx, item in enumerate(results):
                item_id = str(item.get("id", "")).upper().replace("-", "")
                if item_id == target_id:
                    position = offset + idx + 1  # 1-based
                    return {
                        "mlb_id": target_id,
                        "keyword": keyword,
                        "found": True,
                        "position": position,
                        "page": page_idx + 1,
                        "total_results": total_results,
                        "searched_pages": searched_pages,
                    }

            # Se esta pagina retornou menos de PAGE_SIZE, nao ha mais resultados
            if len(results) < PAGE_SIZE:
                break

    # Nao encontrado nas paginas pesquisadas
    return {
        "mlb_id": target_id,
        "keyword": keyword,
        "found": False,
        "position": None,
        "page": None,
        "total_results": total_results,
        "searched_pages": searched_pages,
    }
