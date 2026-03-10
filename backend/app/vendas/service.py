from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.financeiro.service import calcular_margem, calcular_taxa_ml
from app.produtos.models import Product
from app.vendas.models import Listing, ListingSnapshot
from app.vendas.schemas import (
    ListingCreate,
    ListingOut,
    ListingUpdate,
    MargemResult,
    SnapshotOut,
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
        visits = 500 + (i % 300)
        sales = max(0, int((500 - visits) / 100) + (i % 20))
        conversion = Decimal(str(round((sales / max(1, visits)) * 100, 2)))

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

    return sorted(result, key=lambda x: x["days_count"], reverse=True)


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


async def list_listings(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Lista anúncios com o último snapshot de cada um."""
    result = await db.execute(
        select(Listing)
        .where(Listing.user_id == user_id)
        .order_by(Listing.created_at.desc())
    )
    listings = result.scalars().all()

    output = []
    for listing in listings:
        # Busca último snapshot
        snap_result = await db.execute(
            select(ListingSnapshot)
            .where(ListingSnapshot.listing_id == listing.id)
            .order_by(desc(ListingSnapshot.captured_at))
            .limit(1)
        )
        last_snapshot = snap_result.scalar_one_or_none()

        listing_dict = {
            "id": listing.id,
            "user_id": listing.user_id,
            "product_id": listing.product_id,
            "ml_account_id": listing.ml_account_id,
            "mlb_id": listing.mlb_id,
            "title": listing.title,
            "listing_type": listing.listing_type,
            "price": listing.price,
            "status": listing.status,
            "permalink": listing.permalink,
            "thumbnail": listing.thumbnail,
            "created_at": listing.created_at,
            "updated_at": listing.updated_at,
            "last_snapshot": last_snapshot,
        }
        output.append(listing_dict)

    return output


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

    # Busca SKU
    product_result = await db.execute(
        select(Product).where(Product.id == listing.product_id)
    )
    product = product_result.scalar_one_or_none()

    # Se não houver dados reais da ML, retorna mock
    if not product or not product.cost:
        return _generate_mock_analysis(listing, product)

    # Busca snapshots
    snapshots_db = await get_listing_snapshots(db, mlb_id, user_id, days)

    if not snapshots_db:
        # Sem dados ainda, retorna mock
        return _generate_mock_analysis(listing, product)

    # Converte para dicts
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
            "captured_at": s.captured_at,
        }
        for s in snapshots_db
    ]

    cost = Decimal(str(product.cost))

    # Calcula faixas de preço
    price_bands = _calculate_price_bands(snapshots, cost, listing.listing_type)

    # Calcula projeção de estoque
    last_stock = snapshots[-1]["stock"] if snapshots else 0
    stock_projection = _calculate_stock_projection(last_stock, snapshots)

    # Busca concorrente vinculado (primeiro encontrado para este SKU)
    from app.concorrencia.models import Competitor, CompetitorSnapshot

    competitor_result = await db.execute(
        select(Competitor)
        .join(Listing, Competitor.listing_id == Listing.id)
        .where(Listing.product_id == listing.product_id, Listing.user_id == user_id)
        .limit(1)
    )
    competitor = competitor_result.scalar_one_or_none()

    competitor_price = None
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

    # Retorna análise completa
    return {
        "is_mock": False,
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
            "id": str(product.id),
            "sku": product.sku,
            "cost": float(cost),
        },
        "snapshots": snapshots,
        "price_bands": price_bands,
        "full_stock": stock_projection,
        "promotions": [],  # TODO: integrar com ML API quando tiver token
        "ads": {},  # TODO: integrar com ML API quando tiver token
        "competitor": {
            "mlb_id": competitor.mlb_id,
            "price": float(competitor_price),
            "last_updated": comp_snapshot.captured_at.isoformat(),
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
