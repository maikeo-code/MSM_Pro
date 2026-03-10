from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.financeiro.service import calcular_margem
from app.vendas.models import Listing, ListingSnapshot
from app.vendas.schemas import ListingCreate, ListingOut, ListingUpdate, MargemResult


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
    from app.produtos.models import Product

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
