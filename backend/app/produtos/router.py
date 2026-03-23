from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.produtos import service
from app.produtos.schemas import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/produtos", tags=["produtos"])


@router.get("/", response_model=list[ProductOut])
async def list_products(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = False,
):
    """Lista SKUs do usuário. Por padrão apenas ativos, opcional incluir inativos."""
    return await service.list_products(db, current_user.id, include_inactive=include_inactive)


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cadastra novo SKU."""
    return await service.create_product(db, current_user.id, payload)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Busca SKU por ID."""
    return await service.get_product(db, product_id, current_user.id)


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualiza dados do SKU (custo, nome, etc.)."""
    return await service.update_product(db, product_id, current_user.id, payload)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove (soft-delete) um SKU."""
    await service.delete_product(db, product_id, current_user.id)
