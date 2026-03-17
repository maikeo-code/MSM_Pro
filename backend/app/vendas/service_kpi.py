"""
KPI por período e listagem de anúncios com snapshots.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ML_FEES_FLOAT
from app.vendas.models import Listing, ListingSnapshot


async def list_listings(db: AsyncSession, user_id: UUID, period: str = "today") -> list[dict]:
    """Lista anúncios com o último snapshot ou dados agregados por período.

    period: "today" (padrão) | "7d" | "15d" | "30d" | "60d"
    Quando period != "today", agrega snapshots do período (soma de vendas,
    receita, visitas; média de conversão; último estoque) e compara com o
    período anterior equivalente para calcular variação.
    """
    result = await db.execute(
        select(Listing)
        .where(Listing.user_id == user_id)
        .order_by(Listing.created_at.desc())
    )
    listings = result.scalars().all()

    if not listings:
        return []

    listing_ids = [l.id for l in listings]
    today_date = date.today()

    # ── Busca snapshots conforme o período ─────────────────────────────────────
    period_days_map = {"7d": 7, "15d": 15, "30d": 30, "60d": 60}
    is_period_mode = period in period_days_map
    period_days = period_days_map.get(period, 0)

    if is_period_mode:
        # Período atual: [today - N+1 .. today]
        date_from = today_date - timedelta(days=period_days - 1)

        # BUG FIX: Deduplicar por dia — pegar apenas o ÚLTIMO snapshot de cada listing
        # por cada dia, evitando somar N snapshots do mesmo dia (inflava dados 10x)
        latest_per_day_subq = (
            select(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, Date).label("snap_date"),
                func.max(ListingSnapshot.captured_at).label("max_captured_at"),
            )
            .where(
                ListingSnapshot.listing_id.in_(listing_ids),
                cast(ListingSnapshot.captured_at, Date) >= date_from,
                cast(ListingSnapshot.captured_at, Date) <= today_date,
            )
            .group_by(ListingSnapshot.listing_id, cast(ListingSnapshot.captured_at, Date))
            .subquery()
        )
        period_snaps_result = await db.execute(
            select(ListingSnapshot)
            .join(
                latest_per_day_subq,
                (ListingSnapshot.listing_id == latest_per_day_subq.c.listing_id)
                & (ListingSnapshot.captured_at == latest_per_day_subq.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
            .order_by(ListingSnapshot.listing_id, ListingSnapshot.captured_at.desc())
        )
        period_snaps_all = period_snaps_result.scalars().all()

        # Agrupa snapshots do período atual por listing_id
        period_snaps_by_listing: dict = {}
        for snap in period_snaps_all:
            lid = snap.listing_id
            if lid not in period_snaps_by_listing:
                period_snaps_by_listing[lid] = []
            period_snaps_by_listing[lid].append(snap)

        # Período anterior equivalente para variação (também deduplicado por dia)
        prev_date_from = date_from - timedelta(days=period_days)
        prev_date_to = date_from - timedelta(days=1)
        prev_latest_subq = (
            select(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, Date).label("snap_date"),
                func.max(ListingSnapshot.captured_at).label("max_captured_at"),
            )
            .where(
                ListingSnapshot.listing_id.in_(listing_ids),
                cast(ListingSnapshot.captured_at, Date) >= prev_date_from,
                cast(ListingSnapshot.captured_at, Date) <= prev_date_to,
            )
            .group_by(ListingSnapshot.listing_id, cast(ListingSnapshot.captured_at, Date))
            .subquery()
        )
        prev_snaps_result = await db.execute(
            select(ListingSnapshot)
            .join(
                prev_latest_subq,
                (ListingSnapshot.listing_id == prev_latest_subq.c.listing_id)
                & (ListingSnapshot.captured_at == prev_latest_subq.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
            .order_by(ListingSnapshot.listing_id)
        )
        prev_snaps_all = prev_snaps_result.scalars().all()
        prev_snaps_by_listing: dict = {}
        for snap in prev_snaps_all:
            lid = snap.listing_id
            if lid not in prev_snaps_by_listing:
                prev_snaps_by_listing[lid] = []
            prev_snaps_by_listing[lid].append(snap)
    else:
        # "today" — usa último snapshot de cada listing
        period_snaps_by_listing = {}
        prev_snaps_by_listing = {}

    # ── Último snapshot (sempre necessário para estoque atual, dias_para_zerar) ──
    latest_snap_subq = (
        select(
            ListingSnapshot.listing_id,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .group_by(ListingSnapshot.listing_id)
        .subquery()
    )
    snaps_result = await db.execute(
        select(ListingSnapshot)
        .join(
            latest_snap_subq,
            (ListingSnapshot.listing_id == latest_snap_subq.c.listing_id)
            & (ListingSnapshot.captured_at == latest_snap_subq.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
    )
    snaps_by_listing = {
        snap.listing_id: snap for snap in snaps_result.scalars().all()
    }

    # ── Últimos 7 snapshots para velocidade de vendas / dias_para_zerar ──────
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
    snaps_7d_result = await db.execute(
        select(ListingSnapshot)
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            ListingSnapshot.captured_at >= cutoff_7d,
        )
        .order_by(ListingSnapshot.listing_id, ListingSnapshot.captured_at.desc())
    )
    snaps_7d_by_listing: dict = {}
    for snap in snaps_7d_result.scalars().all():
        lid = snap.listing_id
        if lid not in snaps_7d_by_listing:
            snaps_7d_by_listing[lid] = []
        if len(snaps_7d_by_listing[lid]) < 7:
            snaps_7d_by_listing[lid].append(snap)

    # ── Snapshots de ontem (variação hoje vs ontem, modo "today") ─────────────
    yesterday_date = today_date - timedelta(days=1)
    yesterday_snap_subq = (
        select(
            ListingSnapshot.listing_id,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            cast(ListingSnapshot.captured_at, Date) == yesterday_date,
        )
        .group_by(ListingSnapshot.listing_id)
        .subquery()
    )
    yesterday_result = await db.execute(
        select(ListingSnapshot)
        .join(
            yesterday_snap_subq,
            (ListingSnapshot.listing_id == yesterday_snap_subq.c.listing_id)
            & (ListingSnapshot.captured_at == yesterday_snap_subq.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
    )
    yesterday_snaps_by_listing = {
        snap.listing_id: snap for snap in yesterday_result.scalars().all()
    }

    # ── Função auxiliar para agregar uma lista de snapshots ─────────────────
    def _aggregate_snaps(snaps: list) -> dict:
        """Retorna dict com campos agregados de uma lista de snapshots."""
        total_sales = sum(s.sales_today or 0 for s in snaps)
        total_visits = sum(s.visits or 0 for s in snaps)
        total_revenue = sum(
            float(s.revenue or 0) or (float(s.price or 0) * (s.sales_today or 0))
            for s in snaps
        )
        total_orders = sum(s.orders_count or 0 for s in snaps)
        total_cancelled = sum(s.cancelled_orders or 0 for s in snaps)
        total_cancelled_rev = sum(float(s.cancelled_revenue or 0) for s in snaps)
        total_returns = sum(s.returns_count or 0 for s in snaps)
        total_returns_rev = sum(float(s.returns_revenue or 0) for s in snaps)
        avg_conversion = round((total_sales / total_visits * 100), 2) if total_visits > 0 else 0.0
        avg_selling_price = round(total_revenue / total_sales, 2) if total_sales > 0 else 0.0
        # Último estoque (snapshot mais recente)
        latest = max(snaps, key=lambda s: s.captured_at)
        return {
            "sales_today": total_sales,
            "visits": total_visits,
            "revenue": total_revenue,
            "orders_count": total_orders,
            "stock": latest.stock,
            "price": latest.price,
            "questions": sum(s.questions or 0 for s in snaps),
            "conversion_rate": Decimal(str(avg_conversion)),
            "avg_selling_price": avg_selling_price,
            "cancelled_orders": total_cancelled,
            "cancelled_revenue": total_cancelled_rev,
            "returns_count": total_returns,
            "returns_revenue": total_returns_rev,
            "captured_at": latest.captured_at,
            "id": latest.id,
            "listing_id": latest.listing_id,
        }

    # ── Proxy leve para expor dict como atributos (compatível com Pydantic from_attributes) ──
    class _SnapProxy:
        def __init__(self, d: dict):
            self.__dict__.update(d)

    # ── Monta output ─────────────────────────────────────────────────────────
    output = []
    for listing in listings:
        last_snap = snaps_by_listing.get(listing.id)
        recent_snaps = snaps_7d_by_listing.get(listing.id, [])

        # Determina snapshot efetivo baseado no modo
        if is_period_mode:
            p_snaps = period_snaps_by_listing.get(listing.id, [])
            if p_snaps:
                effective_snap_dict = _aggregate_snaps(p_snaps)
            else:
                effective_snap_dict = None
            # Período anterior para variação
            prev_snaps = prev_snaps_by_listing.get(listing.id, [])
            if prev_snaps:
                prev_agg = _aggregate_snaps(prev_snaps)
            else:
                prev_agg = None
        else:
            effective_snap_dict = None  # usa last_snap diretamente
            prev_agg = None

        # O snapshot a usar para cálculos da tabela
        if is_period_mode and effective_snap_dict:
            eff_snap = _SnapProxy(effective_snap_dict)
        else:
            eff_snap = last_snap

        # Calcula dias_para_zerar (sempre baseado em últimos 7 dias reais)
        dias_para_zerar: int | None = None
        if recent_snaps and last_snap and last_snap.stock and last_snap.stock > 0:
            avg_sales = sum(s.sales_today or 0 for s in recent_snaps) / len(recent_snaps)
            if avg_sales > 0:
                dias_para_zerar = int(last_snap.stock / avg_sales)

        # rpv
        rpv: float | None = None
        if eff_snap and getattr(eff_snap, "visits", 0) and getattr(eff_snap, "visits", 0) > 0:
            receita_snap = float(getattr(eff_snap, "revenue", 0) or 0) or (
                float(getattr(eff_snap, "price", 0)) * (getattr(eff_snap, "sales_today", 0) or 0)
            )
            if receita_snap > 0:
                rpv = round(receita_snap / getattr(eff_snap, "visits", 1), 4)

        # taxa_cancelamento
        taxa_cancelamento: float | None = None
        if eff_snap:
            pedidos = getattr(eff_snap, "orders_count", 0) or 0
            cancelados = getattr(eff_snap, "cancelled_orders", 0) or 0
            total = pedidos + cancelados
            if total > 0:
                taxa_cancelamento = round(cancelados / total * 100, 2)

        # avg_price_per_sale
        avg_price_per_sale: float | None = None
        if eff_snap and (getattr(eff_snap, "orders_count", 0) or 0) > 0:
            snap_revenue = float(getattr(eff_snap, "revenue", 0) or 0)
            if snap_revenue > 0:
                avg_price_per_sale = round(snap_revenue / getattr(eff_snap, "orders_count", 1), 2)

        # vendas_concluidas
        vendas_concluidas: float | None = None
        if eff_snap and getattr(eff_snap, "revenue", None) is not None:
            cancelled_rev = float(getattr(eff_snap, "cancelled_revenue", 0) or 0)
            returns_rev = float(getattr(eff_snap, "returns_revenue", 0) or 0)
            vendas_concluidas = round(float(getattr(eff_snap, "revenue", 0)) - cancelled_rev - returns_rev, 2)

        # voce_recebe
        voce_recebe: float | None = None
        if listing.price and float(listing.price) > 0:
            preco = float(listing.sale_price or listing.price)
            if listing.sale_fee_pct and float(listing.sale_fee_pct) > 0:
                taxa_pct = float(listing.sale_fee_pct)
            else:
                taxa_pct = ML_FEES_FLOAT.get(listing.listing_type, 0.17)
            taxa_valor = preco * taxa_pct
            frete = float(listing.avg_shipping_cost or 0)
            voce_recebe = round(preco - taxa_valor - frete, 2)

        # Variação
        vendas_var: float | None = None
        receita_var: float | None = None
        if is_period_mode and effective_snap_dict and prev_agg:
            curr_sales = effective_snap_dict["sales_today"]
            prev_sales = prev_agg["sales_today"]
            if prev_sales > 0:
                vendas_var = round(((curr_sales - prev_sales) / prev_sales) * 100, 1)
            curr_rev = effective_snap_dict["revenue"]
            prev_rev = prev_agg["revenue"]
            if prev_rev > 0:
                receita_var = round(((curr_rev - prev_rev) / prev_rev) * 100, 1)
        elif not is_period_mode and last_snap:
            yesterday_snap = yesterday_snaps_by_listing.get(listing.id)
            if yesterday_snap:
                today_sales = last_snap.sales_today or 0
                yest_sales = yesterday_snap.sales_today or 0
                if yest_sales > 0:
                    vendas_var = round(((today_sales - yest_sales) / yest_sales) * 100, 1)
                today_rev = float(last_snap.revenue or 0)
                yest_rev = float(yesterday_snap.revenue or 0)
                if yest_rev > 0:
                    receita_var = round(((today_rev - yest_rev) / yest_rev) * 100, 1)

        # Monta o snapshot que será serializado
        snap_for_output = eff_snap if (is_period_mode and effective_snap_dict) else last_snap

        listing_dict = {
            "id": listing.id,
            "user_id": listing.user_id,
            "product_id": listing.product_id,
            "ml_account_id": listing.ml_account_id,
            "mlb_id": listing.mlb_id,
            "title": listing.title,
            "listing_type": listing.listing_type,
            "price": listing.price,
            "original_price": listing.original_price,
            "sale_price": listing.sale_price,
            "status": listing.status,
            "category_id": listing.category_id,
            "seller_sku": listing.seller_sku,
            "sale_fee_amount": float(listing.sale_fee_amount) if listing.sale_fee_amount else None,
            "sale_fee_pct": float(listing.sale_fee_pct) if listing.sale_fee_pct else None,
            "avg_shipping_cost": float(listing.avg_shipping_cost) if listing.avg_shipping_cost else None,
            "permalink": listing.permalink,
            "thumbnail": listing.thumbnail,
            "quality_score": listing.quality_score,
            "created_at": listing.created_at,
            "updated_at": listing.updated_at,
            "last_snapshot": snap_for_output,
            "dias_para_zerar": dias_para_zerar,
            "rpv": rpv,
            "taxa_cancelamento": taxa_cancelamento,
            "avg_price_per_sale": avg_price_per_sale,
            "participacao_pct": None,
            "vendas_concluidas": vendas_concluidas,
            "voce_recebe": voce_recebe,
            "vendas_variacao": vendas_var,
            "receita_variacao": receita_var,
        }
        output.append(listing_dict)

    # participacao_pct — calculado após montar output completo
    def _get_revenue(item: dict) -> float:
        snap = item["last_snapshot"]
        if snap is None:
            return 0.0
        rev = getattr(snap, "revenue", None)
        if rev is None and isinstance(snap, dict):
            rev = snap.get("revenue")
        if rev and float(rev) > 0:
            return float(rev)
        # Fallback: estimate revenue from price * sales_today
        price = getattr(snap, "price", None)
        if price is None and isinstance(snap, dict):
            price = snap.get("price")
        sales = getattr(snap, "sales_today", None)
        if sales is None and isinstance(snap, dict):
            sales = snap.get("sales_today")
        if price and sales:
            return float(price) * int(sales)
        return 0.0

    total_revenue_all = sum(_get_revenue(item) for item in output)
    for item in output:
        rev = _get_revenue(item)
        if rev > 0 and total_revenue_all > 0:
            item["participacao_pct"] = round(rev / total_revenue_all * 100, 2)
        else:
            item["participacao_pct"] = None

    return output


async def _kpi_single_day(db: AsyncSession, listing_ids: list, dt) -> dict:
    """KPI para um único dia (último snapshot por listing)."""
    latest_snap_subq = (
        select(
            ListingSnapshot.listing_id,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            cast(ListingSnapshot.captured_at, Date) == dt,
        )
        .group_by(ListingSnapshot.listing_id)
        .subquery()
    )

    result = await db.execute(
        select(
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
            func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visitas"),
            func.count(func.distinct(ListingSnapshot.listing_id)).label("anuncios"),
            func.coalesce(func.sum(ListingSnapshot.price * ListingSnapshot.stock), 0).label("valor_estoque"),
            func.coalesce(func.sum(ListingSnapshot.price * ListingSnapshot.sales_today), 0).label("receita"),
            func.coalesce(func.sum(ListingSnapshot.orders_count), 0).label("pedidos"),
            func.coalesce(func.sum(func.coalesce(ListingSnapshot.revenue, ListingSnapshot.price * ListingSnapshot.sales_today)), 0).label("receita_total"),
            func.coalesce(func.sum(ListingSnapshot.cancelled_orders), 0).label("cancelados"),
            func.coalesce(func.sum(ListingSnapshot.cancelled_revenue), 0).label("cancelados_valor"),
            func.coalesce(func.sum(ListingSnapshot.returns_count), 0).label("devolucoes_qtd"),
            func.coalesce(func.sum(ListingSnapshot.returns_revenue), 0).label("devolucoes_valor"),
        )
        .join(
            latest_snap_subq,
            (ListingSnapshot.listing_id == latest_snap_subq.c.listing_id)
            & (ListingSnapshot.captured_at == latest_snap_subq.c.max_captured_at),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            cast(ListingSnapshot.captured_at, Date) == dt,
        )
    )
    row = result.fetchone()
    vendas = int(row.vendas) if row else 0
    visitas = int(row.visitas) if row else 0
    conversao = round((vendas / visitas * 100), 2) if visitas > 0 else 0.0
    pedidos = int(row.pedidos) if row else 0
    receita_total = float(row.receita_total) if row else 0.0
    cancelados = int(row.cancelados) if row else 0
    cancelados_valor = float(row.cancelados_valor) if row else 0.0
    devolucoes_qtd = int(row.devolucoes_qtd) if row else 0
    devolucoes_valor = float(row.devolucoes_valor) if row else 0.0
    preco_medio = round(receita_total / vendas, 2) if vendas > 0 else 0.0
    preco_medio_por_venda = round(receita_total / pedidos, 2) if pedidos > 0 else 0.0
    total_pedidos_com_cancelados = pedidos + cancelados
    taxa_cancelamento = round(cancelados / total_pedidos_com_cancelados * 100, 2) if total_pedidos_com_cancelados > 0 else 0.0
    vendas_concluidas = round(receita_total - cancelados_valor - devolucoes_valor, 2)

    return {
        "vendas": vendas,
        "visitas": visitas,
        "conversao": conversao,
        "anuncios": int(row.anuncios) if row else 0,
        "valor_estoque": float(row.valor_estoque) if row else 0.0,
        "receita": float(row.receita) if row else 0.0,
        "pedidos": pedidos,
        "receita_total": receita_total,
        "preco_medio": preco_medio,
        "taxa_cancelamento": taxa_cancelamento,
        "preco_medio_por_venda": preco_medio_por_venda,
        "vendas_concluidas": vendas_concluidas,
        "cancelamentos_valor": cancelados_valor,
        "devolucoes_valor": devolucoes_valor,
        "devolucoes_qtd": devolucoes_qtd,
    }


async def _kpi_date_range(db: AsyncSession, listing_ids: list, date_from, date_to) -> dict:
    """KPI para um intervalo de dias (último snapshot por listing por dia, somados)."""
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
            cast(ListingSnapshot.captured_at, Date) <= date_to,
        )
        .group_by(ListingSnapshot.listing_id, cast(ListingSnapshot.captured_at, Date))
        .subquery()
    )

    result = await db.execute(
        select(
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
            func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visitas"),
            func.count(func.distinct(ListingSnapshot.listing_id)).label("anuncios"),
            func.coalesce(func.sum(ListingSnapshot.price * ListingSnapshot.sales_today), 0).label("receita"),
            func.coalesce(func.sum(ListingSnapshot.orders_count), 0).label("pedidos"),
            func.coalesce(func.sum(func.coalesce(ListingSnapshot.revenue, ListingSnapshot.price * ListingSnapshot.sales_today)), 0).label("receita_total"),
            func.coalesce(func.sum(ListingSnapshot.cancelled_orders), 0).label("cancelados"),
            func.coalesce(func.sum(ListingSnapshot.cancelled_revenue), 0).label("cancelados_valor"),
            func.coalesce(func.sum(ListingSnapshot.returns_count), 0).label("devolucoes_qtd"),
            func.coalesce(func.sum(ListingSnapshot.returns_revenue), 0).label("devolucoes_valor"),
        )
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
        )
    )
    row = result.fetchone()
    vendas = int(row.vendas) if row else 0
    visitas = int(row.visitas) if row else 0
    conversao = round((vendas / visitas * 100), 2) if visitas > 0 else 0.0
    pedidos = int(row.pedidos) if row else 0
    receita_total = float(row.receita_total) if row else 0.0
    cancelados = int(row.cancelados) if row else 0
    cancelados_valor = float(row.cancelados_valor) if row else 0.0
    devolucoes_qtd = int(row.devolucoes_qtd) if row else 0
    devolucoes_valor = float(row.devolucoes_valor) if row else 0.0
    preco_medio = round(receita_total / vendas, 2) if vendas > 0 else 0.0
    preco_medio_por_venda = round(receita_total / pedidos, 2) if pedidos > 0 else 0.0
    total_pedidos_com_cancelados = pedidos + cancelados
    taxa_cancelamento = round(cancelados / total_pedidos_com_cancelados * 100, 2) if total_pedidos_com_cancelados > 0 else 0.0
    vendas_concluidas = round(receita_total - cancelados_valor - devolucoes_valor, 2)

    # Valor estoque = snapshot mais recente disponível no intervalo (ponto no tempo, não acumulado)
    # BUG 4 FIX: usar a data mais recente com snapshot, não date_to que pode estar sem dados
    latest_date_result = await db.execute(
        select(func.max(cast(ListingSnapshot.captured_at, Date)))
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            cast(ListingSnapshot.captured_at, Date) >= date_from,
            cast(ListingSnapshot.captured_at, Date) <= date_to,
        )
    )
    latest_date = latest_date_result.scalar()
    if latest_date:
        today_kpi = await _kpi_single_day(db, listing_ids, latest_date)
        valor_estoque = today_kpi["valor_estoque"]
    else:
        valor_estoque = 0.0

    return {
        "vendas": vendas,
        "visitas": visitas,
        "conversao": conversao,
        "anuncios": int(row.anuncios) if row else 0,
        "valor_estoque": valor_estoque,
        "receita": float(row.receita) if row else 0.0,
        "pedidos": pedidos,
        "receita_total": receita_total,
        "preco_medio": preco_medio,
        "taxa_cancelamento": taxa_cancelamento,
        "preco_medio_por_venda": preco_medio_por_venda,
        "vendas_concluidas": vendas_concluidas,
        "cancelamentos_valor": cancelados_valor,
        "devolucoes_valor": devolucoes_valor,
        "devolucoes_qtd": devolucoes_qtd,
    }


async def get_kpi_by_period(db: AsyncSession, user_id: UUID) -> dict:
    """Retorna KPIs agregados para hoje, ontem, anteontem, 7 dias e 30 dias."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    anteontem = today - timedelta(days=2)

    # Busca todos os listings do usuário
    listings_result = await db.execute(
        select(Listing.id).where(Listing.user_id == user_id)
    )
    listing_ids = [row[0] for row in listings_result.fetchall()]

    empty = {
        "vendas": 0, "visitas": 0, "conversao": 0.0, "anuncios": 0,
        "valor_estoque": 0.0, "receita": 0.0,
        "pedidos": 0, "receita_total": 0.0, "preco_medio": 0.0, "taxa_cancelamento": 0.0,
        "preco_medio_por_venda": 0.0, "vendas_concluidas": 0.0,
        "cancelamentos_valor": 0.0, "devolucoes_valor": 0.0, "devolucoes_qtd": 0,
        "vendas_variacao": None, "receita_variacao": None,
        "visitas_variacao": None, "conversao_variacao": None,
    }
    if not listing_ids:
        return {"hoje": empty, "ontem": empty, "anteontem": empty, "7dias": empty, "30dias": empty}

    periods = {}

    # Períodos de dia único
    for label, dt in [("hoje", today), ("ontem", yesterday), ("anteontem", anteontem)]:
        periods[label] = await _kpi_single_day(db, listing_ids, dt)

    # Períodos de intervalo (dados acumulados do histórico de snapshots)
    periods["7dias"] = await _kpi_date_range(
        db, listing_ids, today - timedelta(days=6), today
    )
    periods["30dias"] = await _kpi_date_range(
        db, listing_ids, today - timedelta(days=29), today
    )

    # Calcular variações entre períodos (hoje vs ontem, ontem vs anteontem)
    def _calc_variacao(current: float, previous: float) -> float | None:
        """Calcula variação percentual entre dois valores. None se anterior for 0."""
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 2)

    hoje = periods["hoje"]
    ontem = periods["ontem"]
    anteontem_kpi = periods["anteontem"]

    hoje["vendas_variacao"] = _calc_variacao(hoje["vendas"], ontem["vendas"])
    hoje["receita_variacao"] = _calc_variacao(hoje["receita_total"], ontem["receita_total"])
    hoje["visitas_variacao"] = _calc_variacao(hoje["visitas"], ontem["visitas"])
    hoje["conversao_variacao"] = _calc_variacao(hoje["conversao"], ontem["conversao"])

    ontem["vendas_variacao"] = _calc_variacao(ontem["vendas"], anteontem_kpi["vendas"])
    ontem["receita_variacao"] = _calc_variacao(ontem["receita_total"], anteontem_kpi["receita_total"])
    ontem["visitas_variacao"] = _calc_variacao(ontem["visitas"], anteontem_kpi["visitas"])
    ontem["conversao_variacao"] = _calc_variacao(ontem["conversao"], anteontem_kpi["conversao"])

    # anteontem não tem variação (sem período anterior disponível neste endpoint)
    anteontem_kpi["vendas_variacao"] = None
    anteontem_kpi["receita_variacao"] = None
    anteontem_kpi["visitas_variacao"] = None
    anteontem_kpi["conversao_variacao"] = None

    # 7dias vs 30dias não possuem variação (períodos diferentes de tamanho)
    for label in ["7dias", "30dias"]:
        periods[label]["vendas_variacao"] = None
        periods[label]["receita_variacao"] = None
        periods[label]["visitas_variacao"] = None
        periods[label]["conversao_variacao"] = None

    return periods
