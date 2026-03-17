"""
Módulo principal de vendas — CRUD básico + re-exports dos submódulos.

A lógica foi dividida em submódulos para facilitar manutenção:
  - service_calculations.py  → cálculos puros (price bands, stock, alertas)
  - service_mock.py          → dados mock para preview/testes
  - service_health.py        → health score e quality score
  - service_kpi.py           → KPI por período e listagem de anúncios
  - service_analytics.py     → análise de anúncio, funil e heatmap
  - service_price.py         → preço, margem e promoções
  - service_sync.py          → sincronização com ML API

O router.py importa `from app.vendas import service` e chama `service.<fn>()`,
portanto todos os nomes públicos devem permanecer acessíveis via este módulo.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount
from app.produtos.models import Product
from app.vendas.models import Listing
from app.vendas.schemas import ListingCreate

# ── Re-exports de submódulos ──────────────────────────────────────────────────
# Calculations
from app.vendas.service_calculations import (  # noqa: F401
    _calculate_price_bands,
    _calculate_stock_projection,
    _generate_alerts,
)

# Mock
from app.vendas.service_mock import (  # noqa: F401
    _generate_mock_analysis,
    _generate_mock_snapshots,
)

# Health
from app.vendas.service_health import (  # noqa: F401
    _calculate_health_score,
    calculate_quality_score_quick,
)

# KPI
from app.vendas.service_kpi import (  # noqa: F401
    _kpi_date_range,
    _kpi_single_day,
    get_kpi_by_period,
    list_listings,
)

# Analytics
from app.vendas.service_analytics import (  # noqa: F401
    _fetch_ads_for_listing,
    get_funnel_analytics,
    get_listing_analysis,
    get_listing_snapshots,
    get_sales_heatmap,
)

# Price
from app.vendas.service_price import (  # noqa: F401
    apply_price_suggestion,
    create_or_update_promotion,
    get_margem,
    update_listing_price,
)

# Sync
from app.vendas.service_sync import sync_listings_from_ml  # noqa: F401


# ── CRUD básico (permanecem aqui pois são referenciados por outros submódulos) ─


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


async def create_listing(db: AsyncSession, user_id: UUID, data: ListingCreate) -> Listing:
    """Cadastra novo anúncio MLB."""
    # Verifica duplicidade de MLB ID
    result = await db.execute(select(Listing).where(Listing.mlb_id == data.mlb_id))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Anúncio '{data.mlb_id}' já cadastrado",
        )

    # Verifica ownership da conta ML (IDOR protection)
    if data.ml_account_id:
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
