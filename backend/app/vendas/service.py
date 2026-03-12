from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select, cast, Date, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # noqa: F401 (available for future use)

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
        visits = 400 + (i % 400)  # 400-799 visitas
        sales = max(1, int(visits * (0.01 + (i % 8) * 0.01)))  # 1-8% conversão
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


async def list_listings(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Lista anúncios com o último snapshot de cada um (single query via subquery)."""
    # Subquery: max captured_at por listing_id
    latest_snap_subq = (
        select(
            ListingSnapshot.listing_id,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .group_by(ListingSnapshot.listing_id)
        .subquery()
    )

    result = await db.execute(
        select(Listing)
        .where(Listing.user_id == user_id)
        .order_by(Listing.created_at.desc())
    )
    listings = result.scalars().all()

    if not listings:
        return []

    listing_ids = [l.id for l in listings]

    # Busca todos os últimos snapshots de uma vez
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

    output = []
    for listing in listings:
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
            "permalink": listing.permalink,
            "thumbnail": listing.thumbnail,
            "created_at": listing.created_at,
            "updated_at": listing.updated_at,
            "last_snapshot": snaps_by_listing.get(listing.id),
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
            "captured_at": s.captured_at.isoformat() if s.captured_at else None,
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
        "ads": {},  # TODO: integrar com ML API quando tiver token
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

    return {
        "vendas": vendas,
        "visitas": visitas,
        "conversao": conversao,
        "anuncios": int(row.anuncios) if row else 0,
        "valor_estoque": float(row.valor_estoque) if row else 0.0,
        "receita": float(row.receita) if row else 0.0,
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

    empty = {"vendas": 0, "visitas": 0, "conversao": 0.0, "anuncios": 0, "valor_estoque": 0.0, "receita": 0.0}
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

    return periods


# ============== HEALTH SCORE ==============


def _calculate_health_score(
    listing,
    snapshots: list[dict],
    product=None,
) -> dict:
    """
    Calcula score de saúde do anúncio (0-100).
    Cada critério tem peso diferente.
    """
    score = 0
    checks = []

    # Critério 1: Tem thumbnail/foto (10 pts)
    has_thumb = bool(listing.thumbnail) if hasattr(listing, 'thumbnail') else bool(getattr(listing, 'thumbnail', None))
    if has_thumb:
        score += 10
        checks.append({"item": "Imagem principal", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Imagem principal", "ok": False, "points": 0, "max": 10, "action": "Adicione uma foto de qualidade ao anúncio"})

    # Critério 2: Tem link de permalink (5 pts)
    has_link = bool(listing.permalink) if hasattr(listing, 'permalink') else False
    if has_link:
        score += 5
        checks.append({"item": "Link do anúncio", "ok": True, "points": 5, "max": 5})
    else:
        checks.append({"item": "Link do anúncio", "ok": False, "points": 0, "max": 5, "action": "Preencha o permalink do anúncio"})

    # Critério 3: Custo do SKU cadastrado (15 pts)
    has_cost = product is not None and product.cost and float(product.cost) > 0
    if has_cost:
        score += 15
        checks.append({"item": "Custo do SKU", "ok": True, "points": 15, "max": 15})
    else:
        checks.append({"item": "Custo do SKU", "ok": False, "points": 0, "max": 15, "action": "Cadastre o custo do produto para calcular margens reais"})

    # Critério 4: Estoque cobrindo pelo menos 14 dias (20 pts)
    if snapshots:
        last_snap = snapshots[-1]
        stock = last_snap.get("stock", 0)
        recent_sales = [s.get("sales_today", 0) for s in snapshots[-7:]]
        velocity = sum(recent_sales) / max(1, len(recent_sales))
        days_coverage = stock / max(0.1, velocity)
        if days_coverage >= 30:
            score += 20
            checks.append({"item": "Cobertura de estoque", "ok": True, "points": 20, "max": 20, "detail": f"{days_coverage:.0f} dias"})
        elif days_coverage >= 14:
            score += 10
            checks.append({"item": "Cobertura de estoque", "ok": True, "points": 10, "max": 20, "detail": f"{days_coverage:.0f} dias (ideal: 30+)"})
        else:
            checks.append({"item": "Cobertura de estoque", "ok": False, "points": 0, "max": 20, "action": f"Estoque para {days_coverage:.0f} dias. Reabasteça logo!", "detail": f"{days_coverage:.0f} dias"})
    else:
        checks.append({"item": "Cobertura de estoque", "ok": False, "points": 0, "max": 20, "action": "Sem dados de estoque ainda"})

    # Critério 5: Conversão acima de 1% nos últimos 7 dias (25 pts)
    if snapshots and len(snapshots) >= 3:
        recent = snapshots[-7:] if len(snapshots) >= 7 else snapshots
        total_visits = sum(s.get("visits", 0) for s in recent)
        total_sales = sum(s.get("sales_today", 0) for s in recent)
        conversion = (total_sales / max(1, total_visits)) * 100
        if conversion >= 3:
            score += 25
            checks.append({"item": "Taxa de conversão", "ok": True, "points": 25, "max": 25, "detail": f"{conversion:.1f}%"})
        elif conversion >= 1:
            score += 15
            checks.append({"item": "Taxa de conversão", "ok": True, "points": 15, "max": 25, "detail": f"{conversion:.1f}% (ideal: 3%+)"})
        else:
            checks.append({"item": "Taxa de conversão", "ok": False, "points": 0, "max": 25, "action": f"Conversão de {conversion:.1f}%. Revise título, fotos e preço.", "detail": f"{conversion:.1f}%"})
    else:
        checks.append({"item": "Taxa de conversão", "ok": False, "points": 0, "max": 25, "action": "Sem dados suficientes de vendas"})

    # Critério 6: Sem zero vendas nos últimos 3 dias (15 pts)
    if snapshots and len(snapshots) >= 3:
        last_3 = snapshots[-3:]
        total_recent = sum(s.get("sales_today", 0) for s in last_3)
        if total_recent > 0:
            score += 15
            checks.append({"item": "Vendas recentes", "ok": True, "points": 15, "max": 15, "detail": f"{total_recent} vendas nos últimos 3 dias"})
        else:
            checks.append({"item": "Vendas recentes", "ok": False, "points": 0, "max": 15, "action": "0 vendas nos últimos 3 dias. Verifique preço e visibilidade."})
    else:
        checks.append({"item": "Vendas recentes", "ok": False, "points": 0, "max": 15, "action": "Sem dados de vendas ainda"})

    # Critério 7: Anúncio ativo (10 pts)
    is_active = getattr(listing, 'status', 'active') == 'active'
    if is_active:
        score += 10
        checks.append({"item": "Status do anúncio", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Status do anúncio", "ok": False, "points": 0, "max": 10, "action": "Anúncio pausado ou inativo"})

    # Classifica o score
    if score >= 80:
        status = "excellent"
        label = "Excelente"
        color = "green"
    elif score >= 60:
        status = "good"
        label = "Bom"
        color = "yellow"
    elif score >= 40:
        status = "warning"
        label = "Atenção"
        color = "orange"
    else:
        status = "critical"
        label = "Crítico"
        color = "red"

    return {
        "score": score,
        "max_score": 100,
        "status": status,
        "label": label,
        "color": color,
        "checks": checks,
    }


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
                        if "gold_pro" in listing_type_raw or "gold_premium" in listing_type_raw:
                            listing_type = "premium"
                        elif "gold_special" in listing_type_raw:
                            listing_type = "full"
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

                        if listing:
                            listing.title = item.get("title", listing.title)
                            listing.price = price
                            listing.original_price = original_price
                            listing.sale_price = sale_price_val
                            listing.status = item.get("status", "active")
                            listing.thumbnail = item.get("thumbnail")
                            listing.permalink = item.get("permalink")
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
                                thumbnail=item.get("thumbnail"),
                                permalink=item.get("permalink"),
                            )
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
