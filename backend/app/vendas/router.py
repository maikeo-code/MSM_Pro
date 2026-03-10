from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.vendas import service
from app.vendas.schemas import ListingCreate, ListingOut, MargemResult, SnapshotOut

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("/", response_model=list[ListingOut])
async def list_listings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Lista todos os anúncios do usuário com o último snapshot."""
    return await service.list_listings(db, current_user.id)


@router.post("/", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cadastra novo anúncio MLB manualmente."""
    listing = await service.create_listing(db, current_user.id, payload)
    return {
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
        "last_snapshot": None,
    }


@router.get("/{mlb_id}/snapshots", response_model=list[SnapshotOut])
async def get_snapshots(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    dias: int = Query(default=30, ge=1, le=365, description="Número de dias de histórico"),
):
    """Retorna histórico de snapshots de um anúncio."""
    return await service.get_listing_snapshots(db, mlb_id, current_user.id, dias)


@router.get("/{mlb_id}/margem", response_model=MargemResult)
async def get_margem(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    preco: Decimal = Query(..., description="Preço para calcular a margem"),
):
    """Calcula margem para um anúncio com preço informado."""
    return await service.get_margem(db, mlb_id, current_user.id, preco)
