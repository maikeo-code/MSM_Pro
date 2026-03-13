from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select, cast, Date, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # noqa: F401 (available for future use)

from app.core.constants import ML_FEES_FLOAT
from app.financeiro.service import calcular_margem, calcular_taxa_ml
from app.produtos.models import Product
from app.vendas.models import Listing, ListingSnapshot
from app.vendas.schemas import (
    ListingCreate,
    MargemResult,
)


# ============== MOCK DATA PARA QUANDO NÃO TIVER TOKEN ML ==============


def _generate_mock_snapshots(days: int = 30) -> list[dict]:
    """Gera 30 dias de snapshots mock realistas para testes."""
    snapshots = []
    now = datetime.now(timezone.utc)

    # Prices oscilam entre 239 e 499
    base_price = 409.0
    price_trend = [
        239.0, 239.0, 245.0, 249.0, 259.0, 269.0, 299.0, 349.0, 409.0, 459.0,
        499.0, 489.0, 479.0, 459.0, 429.0, 399.0, 369.0, 349.0, 319.0, 299.0,
        279.0, 259.0, 249.0, 269.0, 289.0, 309.0, 329.0, 349.0, 369.0, 389.0,
    ]

    for i in range(days):
        date = now - timedelta(days=days - i - 1)
        price = Decimal(str(price_trend[i % len(price_trend)]))
        visits = 400 + (i % 400)  # 400-799 visitas
        sales = max(1, int(visits * (0.01 + (i % 8) * 0.01)))  # 1-8% conversão
        conversion = Decimal(str(round((sales / max(1, visits)) * 100, 2)))

        revenue_mock = float(price) * sales
        snapshots.append({
            "id": str(UUID(int=i)),
            "listing_id": str(UUID(int=0)),
            "price": price,
            "visits": visits,
            "sales_today": sales,
            "questions": i % 5,
            "stock": 100 + (i % 50),
            "conversion_rate": conversion,
            "captured_at": date,
            # Campos de analytics — simulados no mock
            "orders_count": max(1, sales - (i % 2)),  # pedidos ligeiramente abaixo de unidades
            "revenue": revenue_mock,
            "avg_selling_price": float(price),
            "cancelled_orders": 1 if i % 7 == 0 else 0,
            "cancelled_revenue": float(price) if i % 7 == 0 else 0.0,
            "returns_count": 1 if i % 15 == 0 else 0,
            "returns_revenue": float(price) if i % 15 == 0 else 0.0,
        })

    return snapshots


def _generate_mock_analysis(listing: Listing, product: Product | None) -> dict:
    """Gera análise completa mock para testes."""
    custo = Decimal(str(product.cost)) if product else Decimal("100.00")
    listing_type = listing.listing_type or "classico"

    snapshots = _generate_mock_snapshots(30)
    price_bands = _calculate_price_bands(snapshots, custo, listing_type)

    return {
        "is_mock": True,
        "listing": {
            "mlb_id": listing.mlb_id,
            "title": listing.title,
            "price": float(listing.price),
            "listing_type": listing_type,
            "status": listing.status,
            "thumbnail": listing.thumbnail,
            "permalink": listing.permalink,
        },
        "sku": {
            "id": str(product.id) if product else None,
            "sku": product.sku if product else "N/A",
            "cost": float(custo),
        },
        "snapshots": snapshots,
        "price_bands": price_bands,
        "full_stock": {
            "available": 121,
            "in_transit": 0,
            "days_until_stockout_7d": 12,
            "days_until_stockout_30d": 19,
            "status": "warning",
            "velocity_7d": 3.8,
            "velocity_30d": 2.1,
        },
        "promotions": [
            {
                "id": "promo_001",
                "type": "desconto_direto",
                "discount_pct": 39.0,
                "original_price": 409.0,
                "final_price": 249.0,
                "start_date": "2026-03-08",
                "end_date": "2026-03-12",
                "status": "active",
            }
        ],
        "ads": {
            "roas": 5.19,
            "impressions": 442390,
            "clicks": 1131,
            "cpc": 1.41,
            "ctr": 0.26,
            "spend": 1595.31,
            "attributed_sales": 8279.89,
        },
        "competitor": None,
        "alerts": [
            {
                "type": "promotion_expiring",
                "message": "Promoção 'Desconto 39%' vence em 2 dias",
                "severity": "warning",
            }
        ],
    }


# ============== CÁLCULOS DE ANÁLISE ==============


def _calculate_price_bands(
    snapshots: list[dict], cost: Decimal, listing_type: str
) -> list[dict]:
    """
    Agrupa snapshots por faixa de preço e calcula métricas.
    Faixas de R$5 a R$10 dependendo do valor.
    """
    if not snapshots:
        return []

    price_bands = {}

    for snap in snapshots:
        price = Decimal(str(snap["price"]))

        # Define tamanho da faixa baseado no valor
        if price < 50:
            band_size = Decimal("5")
        elif price < 200:
            band_size = Decimal("10")
        elif price < 500:
            band_size = Decimal("15")
        else:
            band_size = Decimal("25")

        # Calcula o início da faixa
        band_start = (price // band_size) * band_size

        band_key = str(band_start)

        if band_key not in price_bands:
            price_bands[band_key] = {
                "price_start": band_start,
                "price_end": band_start + band_size,
                "prices": [],
                "sales_list": [],
                "visits_list": [],
                "revenue": Decimal("0"),
                "days_count": 0,
            }

        price_bands[band_key]["prices"].append(price)
        price_bands[band_key]["sales_list"].append(snap["sales_today"])
        price_bands[band_key]["visits_list"].append(snap["visits"])
        # Usa revenue real se disponível; caso contrário estima price * qty
        snap_revenue = snap.get("revenue")
        if snap_revenue is not None and snap_revenue > 0:
            price_bands[band_key]["revenue"] += Decimal(str(snap_revenue))
        else:
            price_bands[band_key]["revenue"] += price * snap["sales_today"]
        price_bands[band_key]["days_count"] += 1

    # Calcula médias e margens
    result = []
    max_margin = Decimal("-999999")
    optimal_band_key = None

    for band_key, band_data in sorted(price_bands.items()):
        avg_price = sum(band_data["prices"]) / len(band_data["prices"])
        avg_sales = sum(band_data["sales_list"]) / len(band_data["sales_list"])
        total_visits = sum(band_data["visits_list"])
        avg_conversion = (
            (sum(band_data["sales_list"]) / max(1, total_visits)) * 100
            if total_visits > 0
            else 0
        )

        margem_info = calcular_margem(avg_price, cost, listing_type)
        avg_margin = margem_info["margem_bruta"]
        total_margin = avg_margin * Decimal(str(sum(band_data["sales_list"])))

        band_entry = {
            "price_range_label": f"R$ {band_data['price_start']:.0f}-{band_data['price_end']:.0f}",
            "avg_sales_per_day": float(avg_sales),
            "avg_conversion": float(avg_conversion),
            "total_revenue": float(band_data["revenue"]),
            "avg_margin": float(avg_margin),
            "days_count": band_data["days_count"],
            "is_optimal": False,
        }

        if total_margin > max_margin:
            if optimal_band_key is not None:
                # Remove optimal da banda anterior
                for item in result:
                    if item.get("is_optimal"):
                        item["is_optimal"] = False
                        break
            max_margin = total_margin
            optimal_band_key = band_key
            band_entry["is_optimal"] = True

        result.append(band_entry)

    return sorted(result, key=lambda x: float(x["price_range_label"].split("R$ ")[1].split("-")[0]))


def _calculate_stock_projection(stock_qty: int, snapshots: list[dict]) -> dict:
    """
    Calcula projeção de estoque baseado em velocidade de venda.
    """
    if not snapshots or stock_qty <= 0:
        return {
            "available": stock_qty,
            "in_transit": 0,
            "days_until_stockout_7d": None,
            "days_until_stockout_30d": None,
            "velocity_7d": 0,
            "velocity_30d": 0,
            "status": "ok",
        }

    # Últimos 7 dias
    recent_7 = snapshots[-7:] if len(snapshots) >= 7 else snapshots
    velocity_7d = sum(s["sales_today"] for s in recent_7) / len(recent_7)

    # Últimos 30 dias
    velocity_30d = sum(s["sales_today"] for s in snapshots) / len(snapshots)

    days_until_stockout_7d = stock_qty / velocity_7d if velocity_7d > 0 else None
    days_until_stockout_30d = stock_qty / velocity_30d if velocity_30d > 0 else None

    # Determina status
    if days_until_stockout_7d and days_until_stockout_7d < 7:
        status = "critical"
    elif days_until_stockout_7d and days_until_stockout_7d < 14:
        status = "warning"
    elif days_until_stockout_7d and days_until_stockout_7d > 60:
        status = "excess"
    else:
        status = "ok"

    return {
        "available": stock_qty,
        "in_transit": 0,
        "days_until_stockout_7d": round(days_until_stockout_7d, 1) if days_until_stockout_7d else None,
        "days_until_stockout_30d": round(days_until_stockout_30d, 1) if days_until_stockout_30d else None,
        "velocity_7d": round(velocity_7d, 2),
        "velocity_30d": round(velocity_30d, 2),
        "status": status,
    }


def _generate_alerts(
    snapshots: list[dict],
    stock_projection: dict,
    competitor_price: Decimal | None,
    current_price: Decimal,
) -> list[dict]:
    """
    Gera alertas inteligentes baseado em regras de negócio.
    """
    alerts = []

    if not snapshots:
        return alerts

    # Alert: Ruptura crítica
    days_until_stockout = stock_projection.get("days_until_stockout_7d")
    if days_until_stockout and days_until_stockout < 7:
        alerts.append({
            "type": "stock_critical",
            "message": f"Estoque acaba em {days_until_stockout:.0f} dias",
            "severity": "critical",
        })

    # Alert: Excesso de estoque
    if days_until_stockout and days_until_stockout > 60:
        alerts.append({
            "type": "stock_excess",
            "message": f"Mais de 60 dias de estoque ({days_until_stockout:.0f} dias)",
            "severity": "info",
        })

    # Alert: Conversão baixa
    recent_3_days = snapshots[-3:] if len(snapshots) >= 3 else snapshots
    recent_visits = sum(s["visits"] for s in recent_3_days)
    recent_sales = sum(s["sales_today"] for s in recent_3_days)

    if recent_visits > 10 and recent_sales > 0:
        recent_conversion = (recent_sales / recent_visits) * 100
        if recent_conversion < 1:
            alerts.append({
                "type": "low_conversion",
                "message": f"Conversão baixa: {recent_conversion:.2f}%",
                "severity": "warning",
            })

    # Alert: Zero vendas
    if recent_sales == 0 and recent_visits > 0:
        alerts.append({
            "type": "zero_sales",
            "message": "0 vendas nos últimos 3 dias com tráfego",
            "severity": "warning",
        })

    # Alert: Concorrente mais barato
    if competitor_price and current_price > competitor_price:
        diff_pct = ((current_price - competitor_price) / current_price) * 100
        alerts.append({
            "type": "competitor_cheaper",
            "message": f"Concorrente {diff_pct:.1f}% mais barato",
            "severity": "info",
        })

    return alerts


# ============== FUNÇÕES PRINCIPAIS ==============


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
        period_snaps_result = await db.execute(
            select(ListingSnapshot)
            .where(
                ListingSnapshot.listing_id.in_(listing_ids),
                cast(ListingSnapshot.captured_at, Date) >= date_from,
            )
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

        # Período anterior equivalente para variação
        prev_date_from = date_from - timedelta(days=period_days)
        prev_date_to = date_from - timedelta(days=1)
        prev_snaps_result = await db.execute(
            select(ListingSnapshot)
            .where(
                ListingSnapshot.listing_id.in_(listing_ids),
                cast(ListingSnapshot.captured_at, Date) >= prev_date_from,
                cast(ListingSnapshot.captured_at, Date) <= prev_date_to,
            )
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
        total_revenue = sum(float(s.revenue or 0) for s in snaps)
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
            avg_sales = sum(s.sales_today for s in recent_snaps) / len(recent_snaps)
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
        return float(rev) if rev else 0.0

    total_revenue_all = sum(_get_revenue(item) for item in output)
    for item in output:
        rev = _get_revenue(item)
        if rev > 0 and total_revenue_all > 0:
            item["participacao_pct"] = round(rev / total_revenue_all * 100, 2)
        else:
            item["participacao_pct"] = None

    return output


async def get_funnel_analytics(db: AsyncSession, user_id: UUID, period_days: int = 7) -> dict:
    """
    FEATURE 2: Funil de conversão — agrega visitas, vendas, conversão e receita
    de todos os anúncios do usuário no período selecionado.
    """
    # Busca listing_ids do usuário
    listings_result = await db.execute(
        select(Listing.id).where(Listing.user_id == user_id)
    )
    listing_ids = [row[0] for row in listings_result.fetchall()]

    if not listing_ids:
        return {"visitas": 0, "vendas": 0, "conversao": 0.0, "receita": 0.0}

    today_dt = date.today()
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

    result = await db.execute(
        select(
            func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visitas"),
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("receita"),
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


async def get_listing(db: AsyncSession, mlb_id: str, user_id: UUID) -> Listing:
    """Busca listing por MLB ID validando propriedade."""
    result = await db.execute(
        select(Listing).where(
            Listing.mlb_id == mlb_id,
            Listing.user_id == user_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anúncio não encontrado")
    return listing


async def get_listing_snapshots(
    db: AsyncSession, mlb_id: str, user_id: UUID, dias: int = 30
) -> list[ListingSnapshot]:
    """Retorna histórico de snapshots de um anúncio."""
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


async def create_listing(db: AsyncSession, user_id: UUID, data: ListingCreate) -> Listing:
    """Cadastra novo anúncio MLB."""
    # Verifica duplicidade de MLB ID
    result = await db.execute(select(Listing).where(Listing.mlb_id == data.mlb_id))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Anúncio '{data.mlb_id}' já cadastrado",
        )

    # FIX 5: Verifica ownership da conta ML (IDOR protection)
    if data.ml_account_id:
        from app.auth.models import MLAccount
        acct_result = await db.execute(
            select(MLAccount).where(
                MLAccount.id == data.ml_account_id,
                MLAccount.user_id == user_id,
            )
        )
        if not acct_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conta ML não pertence ao usuário",
            )

    listing = Listing(user_id=user_id, **data.model_dump())
    db.add(listing)
    await db.flush()
    await db.refresh(listing)
    return listing


async def get_margem(
    db: AsyncSession, mlb_id: str, user_id: UUID, preco: Decimal
) -> MargemResult:
    """Calcula margem para um anúncio com preço informado."""
    listing = await get_listing(db, mlb_id, user_id)

    # Busca custo do produto
    prod_result = await db.execute(
        select(Product).where(Product.id == listing.product_id)
    )
    product = prod_result.scalar_one_or_none()
    custo = product.cost if product else Decimal("0")

    resultado = calcular_margem(
        preco=preco,
        custo=custo,
        listing_type=listing.listing_type,
    )

    return MargemResult(
        preco=preco,
        custo_sku=custo,
        listing_type=listing.listing_type,
        **resultado,
    )


async def link_sku_to_listing(
    db: AsyncSession, mlb_id: str, user_id: UUID, product_id: UUID | None
) -> dict:
    """Vincula ou desvincula um produto/SKU a um anúncio."""
    listing = await get_listing(db, mlb_id, user_id)

    # Verifica se o produto existe e pertence ao usuário
    if product_id is not None:
        prod_result = await db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.user_id == user_id,
            )
        )
        if not prod_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado ou não pertence ao usuário",
            )

    listing.product_id = product_id
    await db.flush()
    await db.refresh(listing)

    return {
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
        "permalink": listing.permalink,
        "thumbnail": listing.thumbnail,
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
        "last_snapshot": None,
    }


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
        "promotions": [],  # TODO: integrar com ML API quando tiver token
        "ads": await _fetch_ads_for_listing(db, listing),
        "competitor": {
            "mlb_id": competitor.mlb_id,
            "price": float(competitor_price),
            "last_updated": comp_snapshot.captured_at.isoformat() if comp_snapshot else None,
        } if competitor and competitor_price else None,
        "alerts": alerts,
    }


async def update_listing_price(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    new_price: Decimal,
) -> dict:
    """Altera preço de um anúncio (será integrado com ML API)."""
    listing = await get_listing(db, mlb_id, user_id)

    listing.price = new_price
    await db.flush()
    await db.refresh(listing)

    return {
        "mlb_id": listing.mlb_id,
        "new_price": float(new_price),
        "updated_at": listing.updated_at.isoformat(),
    }


async def apply_price_suggestion(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    new_price: float,
    justification: str,
) -> dict:
    """
    Aplica sugestão de preço: altera na API do ML e salva log no banco.
    Respeita regra original_price/sale_price:
    - PUT /items/{id} com {"price": new_price} altera o preço base.
    - Se houver promoção ativa (original_price != null), alterar preço pode desativar a promoção.
    - O response da API retorna o item atualizado com price, original_price e sale_price.
    """
    import json

    from app.auth.models import MLAccount
    from app.mercadolivre.client import MLClient, MLClientError
    from app.vendas.models import PriceChangeLog

    listing = await get_listing(db, mlb_id, user_id)
    old_price = float(listing.price)

    # Buscar token ML da conta associada ao listing
    acc_result = await db.execute(
        select(MLAccount).where(MLAccount.id == listing.ml_account_id)
    )
    ml_account = acc_result.scalar_one_or_none()
    if not ml_account or not ml_account.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta ML não encontrada ou sem token válido",
        )

    # Chamar API ML para alterar preço
    ml_api_success = False
    ml_api_response_raw = None
    ml_price_returned = None
    ml_original_price = None
    ml_sale_price = None
    error_msg = None

    try:
        async with MLClient(ml_account.access_token) as client:
            ml_response = await client.update_item_price(listing.mlb_id, new_price)
            ml_api_response_raw = json.dumps(ml_response, default=str)[:5000]
            ml_api_success = True

            # Extrair preços retornados pela API
            ml_price_returned = ml_response.get("price")
            ml_original_price = ml_response.get("original_price")
            # sale_price pode ser objeto ou null
            sp = ml_response.get("sale_price")
            if isinstance(sp, dict):
                ml_sale_price = sp.get("amount")
            elif isinstance(sp, (int, float)):
                ml_sale_price = sp

    except MLClientError as e:
        error_msg = str(e)
        ml_api_response_raw = error_msg[:5000]

    # Atualizar listing local se API respondeu OK
    if ml_api_success:
        listing.price = Decimal(str(new_price))
        if ml_original_price is not None:
            listing.original_price = Decimal(str(ml_original_price))
        else:
            listing.original_price = None
        if ml_sale_price is not None:
            listing.sale_price = Decimal(str(ml_sale_price))
        else:
            listing.sale_price = None

    # Salvar log de ação no PostgreSQL
    log = PriceChangeLog(
        listing_id=listing.id,
        user_id=user_id,
        mlb_id=listing.mlb_id,
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(new_price)),
        justification=justification,
        source="suggestion_apply",
        ml_api_response=ml_api_response_raw,
        success=ml_api_success,
        error_message=error_msg,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)

    if not ml_api_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"API ML rejeitou alteração: {error_msg}",
        )

    return {
        "mlb_id": listing.mlb_id,
        "old_price": old_price,
        "new_price": new_price,
        "justification": justification,
        "ml_api_success": ml_api_success,
        "ml_api_price_returned": ml_price_returned,
        "original_price": ml_original_price,
        "sale_price": ml_sale_price,
        "log_id": str(log.id),
        "applied_at": log.created_at.isoformat(),
    }


async def create_or_update_promotion(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    discount_pct: float,
    start_date: str,
    end_date: str,
    promotion_id: str | None = None,
) -> dict:
    """Cria ou renova promoção (será integrado com ML API)."""
    listing = await get_listing(db, mlb_id, user_id)

    # Calcula preço final
    original_price = float(listing.price)
    final_price = original_price * (1 - discount_pct / 100)

    return {
        "id": promotion_id or "new_promo",
        "type": "desconto_direto",
        "discount_pct": discount_pct,
        "original_price": original_price,
        "final_price": final_price,
        "start_date": start_date,
        "end_date": end_date,
        "status": "active" if promotion_id else "pending",
    }


# ============== KPI POR PERÍODO ==============


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
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("receita_total"),
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
            func.coalesce(func.sum(ListingSnapshot.revenue), 0).label("receita_total"),
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


# ============== HEALTH SCORE ==============


def _calculate_health_score(
    listing,
    snapshots: list[dict],
    product=None,
    competitor_price: float | None = None,
) -> dict:
    """
    Calcula score de qualidade do anúncio (0-100) baseado na Missão 3 do ML.

    Critérios (total = 100 pts):
    - Título: comprimento >60 chars = +10pts
    - Imagens: tem thumbnail = +15pts (proxy para >5 fotos)
    - Preço competitivo (vs concorrente se disponível) = +10pts
    - Frete grátis (premium ou full) = +10pts
    - Fulfillment (Full) = +10pts
    - Conversão >3% = +10pts
    - Estoque >10 = +10pts
    - Vendas recentes (últimos 3 dias >0) = +10pts
    - Anúncio ativo = +5pts
    - Custo do SKU cadastrado = +10pts
    """
    score = 0
    checks = []

    # 1. Título: comprimento >60 chars = +10pts
    title = getattr(listing, 'title', '') or ''
    title_len = len(title)
    if title_len > 60:
        score += 10
        checks.append({"item": "Título otimizado", "ok": True, "points": 10, "max": 10, "detail": f"{title_len} caracteres"})
    else:
        checks.append({"item": "Título otimizado", "ok": False, "points": 0, "max": 10, "action": f"Título com {title_len} chars. Ideal: >60 chars com palavras-chave", "detail": f"{title_len} caracteres"})

    # 2. Imagens: tem thumbnail = +15pts
    has_thumb = bool(getattr(listing, 'thumbnail', None))
    if has_thumb:
        score += 15
        checks.append({"item": "Imagens do anúncio", "ok": True, "points": 15, "max": 15})
    else:
        checks.append({"item": "Imagens do anúncio", "ok": False, "points": 0, "max": 15, "action": "Adicione fotos de qualidade ao anúncio (ideal: >5 fotos)"})

    # 3. Preço competitivo (vs concorrente) = +10pts
    current_price = float(getattr(listing, 'sale_price', None) or getattr(listing, 'price', 0) or 0)
    if competitor_price and current_price > 0:
        if current_price <= competitor_price * 1.05:
            score += 10
            checks.append({"item": "Preço competitivo", "ok": True, "points": 10, "max": 10, "detail": f"R$ {current_price:.0f} vs concorrente R$ {competitor_price:.0f}"})
        else:
            diff_pct = ((current_price - competitor_price) / competitor_price) * 100
            checks.append({"item": "Preço competitivo", "ok": False, "points": 0, "max": 10, "action": f"Preço {diff_pct:.0f}% acima do concorrente", "detail": f"R$ {current_price:.0f} vs R$ {competitor_price:.0f}"})
    elif current_price > 0:
        score += 5
        checks.append({"item": "Preço competitivo", "ok": True, "points": 5, "max": 10, "detail": "Sem concorrente vinculado para comparar"})
    else:
        checks.append({"item": "Preço competitivo", "ok": False, "points": 0, "max": 10, "action": "Vincule um concorrente para comparar preços"})

    # 4. Frete grátis (premium ou full) = +10pts
    listing_type = getattr(listing, 'listing_type', 'classico') or 'classico'
    if listing_type in ('premium', 'full'):
        score += 10
        checks.append({"item": "Frete grátis", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Frete grátis", "ok": False, "points": 0, "max": 10, "action": "Migre para Premium ou Full para oferecer frete grátis"})

    # 5. Fulfillment (Full) = +10pts
    if listing_type == 'full':
        score += 10
        checks.append({"item": "Fulfillment (Full)", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Fulfillment (Full)", "ok": False, "points": 0, "max": 10, "action": "Envie estoque ao Full para entregas mais rápidas"})

    # 6. Conversão >3% nos últimos 7 dias = +10pts
    if snapshots and len(snapshots) >= 3:
        recent = snapshots[-7:] if len(snapshots) >= 7 else snapshots
        total_visits = sum(s.get("visits", 0) for s in recent)
        total_sales = sum(s.get("sales_today", 0) for s in recent)
        conversion = (total_sales / max(1, total_visits)) * 100
        if conversion >= 3:
            score += 10
            checks.append({"item": "Conversão (>3%)", "ok": True, "points": 10, "max": 10, "detail": f"{conversion:.1f}%"})
        elif conversion >= 1:
            score += 5
            checks.append({"item": "Conversão (>3%)", "ok": True, "points": 5, "max": 10, "detail": f"{conversion:.1f}% (ideal: 3%+)"})
        else:
            checks.append({"item": "Conversão (>3%)", "ok": False, "points": 0, "max": 10, "action": f"Conversão de {conversion:.1f}%. Revise título, fotos e preço.", "detail": f"{conversion:.1f}%"})
    else:
        checks.append({"item": "Conversão (>3%)", "ok": False, "points": 0, "max": 10, "action": "Sem dados suficientes de vendas"})

    # 7. Estoque >10 unidades = +10pts
    if snapshots:
        last_snap = snapshots[-1]
        stock = last_snap.get("stock", 0)
        if stock > 10:
            score += 10
            checks.append({"item": "Estoque (>10 un.)", "ok": True, "points": 10, "max": 10, "detail": f"{stock} unidades"})
        else:
            checks.append({"item": "Estoque (>10 un.)", "ok": False, "points": 0, "max": 10, "action": f"Apenas {stock} unidades. Reabasteça!", "detail": f"{stock} unidades"})
    else:
        checks.append({"item": "Estoque (>10 un.)", "ok": False, "points": 0, "max": 10, "action": "Sem dados de estoque ainda"})

    # 8. Vendas recentes (últimos 3 dias >0) = +10pts
    if snapshots and len(snapshots) >= 3:
        last_3 = snapshots[-3:]
        total_recent = sum(s.get("sales_today", 0) for s in last_3)
        if total_recent > 0:
            score += 10
            checks.append({"item": "Vendas recentes", "ok": True, "points": 10, "max": 10, "detail": f"{total_recent} vendas nos últimos 3 dias"})
        else:
            checks.append({"item": "Vendas recentes", "ok": False, "points": 0, "max": 10, "action": "0 vendas nos últimos 3 dias. Verifique preço e visibilidade."})
    else:
        checks.append({"item": "Vendas recentes", "ok": False, "points": 0, "max": 10, "action": "Sem dados de vendas ainda"})

    # 9. Anúncio ativo = +5pts
    is_active = getattr(listing, 'status', 'active') == 'active'
    if is_active:
        score += 5
        checks.append({"item": "Status ativo", "ok": True, "points": 5, "max": 5})
    else:
        checks.append({"item": "Status ativo", "ok": False, "points": 0, "max": 5, "action": "Anúncio pausado ou inativo"})

    # 10. Custo do SKU cadastrado = +10pts
    has_cost = product is not None and product.cost and float(product.cost) > 0
    if has_cost:
        score += 10
        checks.append({"item": "Custo do SKU", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Custo do SKU", "ok": False, "points": 0, "max": 10, "action": "Cadastre o custo para calcular margens reais"})

    # Classifica o score
    if score >= 80:
        health_status = "excellent"
        label = "Excelente"
        color = "green"
    elif score >= 60:
        health_status = "good"
        label = "Bom"
        color = "yellow"
    elif score >= 40:
        health_status = "warning"
        label = "Atenção"
        color = "orange"
    else:
        health_status = "critical"
        label = "Crítico"
        color = "red"

    return {
        "score": score,
        "max_score": 100,
        "status": health_status,
        "label": label,
        "color": color,
        "checks": checks,
    }


def calculate_quality_score_quick(listing) -> int:
    """
    Calcula quality_score rápido sem snapshots (para usar durante sync).
    Baseado apenas nos atributos do listing.
    """
    score = 0
    title = getattr(listing, 'title', '') or ''
    if len(title) > 60:
        score += 10
    if getattr(listing, 'thumbnail', None):
        score += 15
    listing_type = getattr(listing, 'listing_type', 'classico') or 'classico'
    if listing_type in ('premium', 'full'):
        score += 10  # frete grátis
    if listing_type == 'full':
        score += 10  # fulfillment
    if getattr(listing, 'status', 'active') == 'active':
        score += 5
    if float(getattr(listing, 'price', 0) or 0) > 0:
        score += 5  # preço parcial (sem concorrente)
    return min(100, score)


async def sync_listings_from_ml(db: AsyncSession, user_id: UUID) -> dict:
    """
    Busca todos os anúncios ativos das contas ML do usuário e salva no banco.
    Retorna contagem de novos e atualizados.
    """
    from app.auth.models import MLAccount
    from app.mercadolivre.client import MLClient, MLClientError

    # Busca todas as contas ML ativas do usuário
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == user_id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma conta ML conectada. Conecte uma conta primeiro.",
        )

    created = 0
    updated = 0
    errors = []

    for account in accounts:
        if not account.access_token:
            continue

        try:
            async with MLClient(account.access_token) as client:
                # Busca IDs dos anúncios ativos
                offset = 0
                all_item_ids = []
                while True:
                    resp = await client.get_user_listings(
                        account.ml_user_id, offset=offset, limit=50
                    )
                    item_ids = resp.get("results", [])
                    all_item_ids.extend(item_ids)
                    if len(item_ids) < 50:
                        break
                    offset += 50

                # Busca detalhes de cada anúncio
                for mlb_id in all_item_ids:
                    try:
                        item = await client.get_item(mlb_id)

                        listing_type_raw = item.get("listing_type_id", "gold_special")
                        shipping = item.get("shipping", {})
                        is_fulfillment = shipping.get("logistic_type") == "fulfillment"
                        if "gold_pro" in listing_type_raw and is_fulfillment:
                            listing_type = "full"
                        elif "gold_pro" in listing_type_raw:
                            listing_type = "premium"
                        else:
                            listing_type = "classico"

                        price = Decimal(str(item.get("price", 0)))
                        stock = item.get("available_quantity", 0)

                        # Extrai original_price e sale_price
                        original_price_raw = item.get("original_price")
                        original_price = Decimal(str(original_price_raw)) if original_price_raw else None

                        sale_price_data = item.get("sale_price")
                        sale_price_val = None
                        if sale_price_data and isinstance(sale_price_data, dict):
                            sp_amount = sale_price_data.get("amount")
                            if sp_amount is not None:
                                sale_price_val = Decimal(str(sp_amount))

                        # Se temos sale_price menor que price, então price é o preço original
                        if sale_price_val is not None and original_price is None and price > sale_price_val:
                            original_price = price

                        # Se ainda não tem original_price, buscar via seller-promotions
                        if original_price is None:
                            try:
                                promotions = await client.get_item_promotions(mlb_id)
                                for promo in promotions:
                                    if promo.get("status") == "started" and promo.get("original_price"):
                                        original_price = Decimal(str(promo["original_price"]))
                                        promo_price = promo.get("price")
                                        if promo_price is not None:
                                            price = Decimal(str(promo_price))
                                        break
                            except Exception:
                                pass

                        # Verifica se listing já existe
                        existing = await db.execute(
                            select(Listing).where(Listing.mlb_id == mlb_id)
                        )
                        listing = existing.scalar_one_or_none()

                        # Extrai category_id e seller_sku
                        category_id = item.get("category_id")
                        seller_sku = item.get("seller_custom_field")
                        if not seller_sku and item.get("attributes"):
                            for attr in item["attributes"]:
                                if attr.get("id") == "SELLER_SKU":
                                    seller_sku = attr.get("value_name") or attr.get("value_id")
                                    break
                        # Usar secure_thumbnail (HTTPS) quando disponível
                        thumbnail = item.get("secure_thumbnail") or item.get("thumbnail")

                        # Busca taxa real via API listing_prices
                        sale_fee_amount = None
                        sale_fee_pct = None
                        if category_id and listing_type_raw:
                            try:
                                fees_data = await client.get_listing_fees(
                                    price=float(price),
                                    category_id=category_id,
                                    listing_type_id=listing_type_raw,
                                )
                                if fees_data.get("sale_fee_amount"):
                                    sale_fee_amount = Decimal(str(fees_data["sale_fee_amount"]))
                                pct_fee = fees_data.get("percentage_fee")
                                if pct_fee and pct_fee > 0:
                                    sale_fee_pct = Decimal(str(pct_fee / 100))
                            except Exception:
                                pass  # fallback para taxa fixa

                        if listing:
                            listing.title = item.get("title", listing.title)
                            listing.price = price
                            listing.original_price = original_price
                            listing.sale_price = sale_price_val
                            listing.status = item.get("status", "active")
                            listing.thumbnail = thumbnail
                            listing.permalink = item.get("permalink")
                            listing.category_id = category_id
                            listing.seller_sku = seller_sku
                            if sale_fee_amount is not None:
                                listing.sale_fee_amount = sale_fee_amount
                            if sale_fee_pct is not None:
                                listing.sale_fee_pct = sale_fee_pct
                            # Calcula quality_score durante sync
                            listing.quality_score = calculate_quality_score_quick(listing)
                            await db.flush()
                            updated += 1
                        else:
                            listing = Listing(
                                user_id=user_id,
                                ml_account_id=account.id,
                                mlb_id=mlb_id,
                                title=item.get("title", mlb_id),
                                listing_type=listing_type,
                                price=price,
                                original_price=original_price,
                                sale_price=sale_price_val,
                                status=item.get("status", "active"),
                                thumbnail=thumbnail,
                                permalink=item.get("permalink"),
                                category_id=category_id,
                                seller_sku=seller_sku,
                                sale_fee_amount=sale_fee_amount,
                                sale_fee_pct=sale_fee_pct,
                            )
                            # Calcula quality_score para novo listing
                            listing.quality_score = calculate_quality_score_quick(listing)
                            db.add(listing)
                            await db.flush()
                            created += 1

                        # Busca visitas de hoje via time_window (endpoint que funciona por dia)
                        visits_today = 0
                        try:
                            today_str = date.today().isoformat()
                            visits_resp = await client._request(
                                "GET",
                                f"/items/{mlb_id}/visits/time_window",
                                params={"last": 1, "unit": "day"},
                            )
                            for day_data in visits_resp.get("results", []):
                                if day_data.get("date", "").startswith(today_str):
                                    visits_today = day_data.get("total", 0)
                                    break
                            # Se não achou hoje especificamente, pega o mais recente
                            if visits_today == 0 and visits_resp.get("results"):
                                visits_today = visits_resp["results"][0].get("total", 0)
                        except Exception:
                            pass

                        # BUG 1 FIX: verificar se já existe snapshot do mesmo dia antes de inserir
                        # Usa .first() em vez de scalar_one_or_none() porque pode haver
                        # múltiplos snapshots do mesmo dia (duplicatas antigas)
                        existing_snap_result = await db.execute(
                            select(ListingSnapshot).where(
                                ListingSnapshot.listing_id == listing.id,
                                cast(ListingSnapshot.captured_at, Date) == date.today(),
                            ).order_by(ListingSnapshot.captured_at.desc()).limit(1)
                        )
                        existing_snap = existing_snap_result.scalar_one_or_none()
                        if existing_snap:
                            existing_snap.price = price
                            existing_snap.visits = visits_today
                            existing_snap.stock = stock
                            existing_snap.captured_at = datetime.utcnow()
                            await db.flush()
                        else:
                            snapshot = ListingSnapshot(
                                listing_id=listing.id,
                                price=price,
                                visits=visits_today,
                                sales_today=0,  # será preenchido abaixo via orders
                                questions=0,
                                stock=stock,
                                conversion_rate=None,
                            )
                            db.add(snapshot)

                    except MLClientError as e:
                        errors.append(f"{mlb_id}: {e}")
                        continue

                # Busca vendas de hoje via orders API e atualiza snapshots
                try:
                    today = date.today()
                    today_start = f"{today.isoformat()}T00:00:00.000-03:00"

                    orders_resp = await client._request(
                        "GET",
                        "/orders/search",
                        params={
                            "seller": account.ml_user_id,
                            "order.date_created.from": today_start,
                            "sort": "date_desc",
                            "limit": 50,
                        },
                    )

                    # Conta vendas por MLB ID
                    sales_by_mlb: dict[str, int] = {}
                    for order in orders_resp.get("results", []):
                        for oi in order.get("order_items", []):
                            oi_mlb = oi.get("item", {}).get("id", "")
                            qty = oi.get("quantity", 1)
                            sales_by_mlb[oi_mlb] = sales_by_mlb.get(oi_mlb, 0) + qty

                    # Atualiza snapshots com vendas reais
                    for mlb_id_raw, sales_count in sales_by_mlb.items():
                        if sales_count > 0:
                            lst_result = await db.execute(
                                select(Listing).where(Listing.mlb_id == mlb_id_raw)
                            )
                            lst = lst_result.scalar_one_or_none()
                            if lst:
                                snap_result = await db.execute(
                                    select(ListingSnapshot)
                                    .where(ListingSnapshot.listing_id == lst.id)
                                    .order_by(ListingSnapshot.captured_at.desc())
                                    .limit(1)
                                )
                                snap = snap_result.scalar_one_or_none()
                                if snap:
                                    snap.sales_today = sales_count
                                    if snap.visits > 0:
                                        snap.conversion_rate = Decimal(
                                            str(round((sales_count / snap.visits) * 100, 2))
                                        )
                                    await db.flush()
                except Exception:
                    # Não bloquear sync se orders falharem
                    pass

        except MLClientError as e:
            errors.append(f"Conta {account.nickname}: {e}")
            continue

    await db.commit()

    return {
        "created": created,
        "updated": updated,
        "total": created + updated,
        "errors": errors,
        "message": f"Sync concluído: {created} novos, {updated} atualizados.",
    }


# ============== Heatmap de Vendas ==============

_DAY_NAMES = [
    "Segunda-feira",
    "Terca-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sabado",
    "Domingo",
]


async def get_sales_heatmap(
    db: AsyncSession,
    user_id: UUID,
    period_days: int = 30,
) -> dict:
    """
    Retorna heatmap de vendas nos ultimos N dias.

    Estrategia:
    1. Tenta usar tabela Order (granularidade dia+hora) via extract('dow') e extract('hour')
    2. Se nao houver Orders suficientes (< 3 registros), faz FALLBACK para ListingSnapshots por dia

    Retorno: HeatmapOut com has_hourly_data indicando qual estrategia foi usada.
    Dia da semana padronizado: 0=segunda, 6=domingo (Python weekday()).
    """
    from app.vendas.models import Order
    from app.vendas.schemas import HeatmapCell, HeatmapOut
    from app.auth.models import MLAccount  # noqa: F401

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

    # ── 1. Tentar estrategia Orders (dia+hora) ───────────────────────────────
    # Agrupa por (dow_postgres, hour) usando extract. PostgreSQL DOW: 0=domingo, 6=sabado
    # Convertemos para Python weekday (0=segunda) logo apos.
    order_agg_result = await db.execute(
        select(
            func.extract("dow", Order.order_date).label("pg_dow"),
            func.extract("hour", Order.order_date).label("hour"),
            func.count(Order.id).label("cnt"),
        )
        .join(MLAccount, Order.ml_account_id == MLAccount.id)
        .where(
            MLAccount.user_id == user_id,
            Order.order_date >= cutoff,
            Order.payment_status == "approved",
        )
        .group_by("pg_dow", "hour")
    )
    order_rows = order_agg_result.fetchall()

    has_hourly_data = len(order_rows) >= 3

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
    snaps_result = await db.execute(
        select(ListingSnapshot)
        .join(Listing, ListingSnapshot.listing_id == Listing.id)
        .where(
            Listing.user_id == user_id,
            ListingSnapshot.captured_at >= cutoff,
        )
    )
    snapshots = snaps_result.scalars().all()

    counts_by_day: dict[int, int] = {i: 0 for i in range(7)}

    for snap in snapshots:
        dt = snap.captured_at
        day_idx = dt.weekday()  # 0=segunda, 6=domingo
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
