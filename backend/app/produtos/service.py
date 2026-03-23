from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.produtos.models import Product
from app.produtos.schemas import ProductCreate, ProductUpdate


async def list_products(db: AsyncSession, user_id: UUID, include_inactive: bool = False) -> list[Product]:
    """Lista SKUs do usuário. Por padrão apenas ativos, opcional incluir inativos."""
    query = select(Product).where(Product.user_id == user_id)
    if not include_inactive:
        query = query.where(Product.is_active == True)  # noqa: E712
    result = await db.execute(query.order_by(Product.sku))
    return list(result.scalars().all())


async def get_product(db: AsyncSession, product_id: UUID, user_id: UUID) -> Product:
    """Busca um SKU por ID, validando que pertence ao usuário."""
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.user_id == user_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return product


async def create_product(db: AsyncSession, user_id: UUID, data: ProductCreate) -> Product:
    """Cria novo SKU. Valida unicidade de SKU por usuário."""
    # Verifica duplicidade
    result = await db.execute(
        select(Product).where(
            Product.user_id == user_id,
            Product.sku == data.sku,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SKU '{data.sku}' já existe para este usuário",
        )

    product = Product(user_id=user_id, **data.model_dump())
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


async def update_product(
    db: AsyncSession, product_id: UUID, user_id: UUID, data: ProductUpdate
) -> Product:
    """Atualiza campos de um SKU."""
    product = await get_product(db, product_id, user_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.flush()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: UUID, user_id: UUID) -> None:
    """Soft-delete de um SKU (marca is_active=False)."""
    product = await get_product(db, product_id, user_id)
    product.is_active = False
    await db.flush()
