from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.vendas import service
from app.vendas.schemas import (
    CreatePromotionIn,
    ListingAnalysisOut,
    ListingCreate,
    ListingOut,
    MargemResult,
    SnapshotOut,
    UpdatePriceIn,
)

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


@router.get("/{mlb_id}", response_model=ListingOut)
async def get_listing(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Busca um anúncio específico."""
    listing = await service.get_listing(db, mlb_id, current_user.id)
    return listing


@router.get("/{mlb_id}/snapshots", response_model=list[SnapshotOut])
async def get_snapshots(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    dias: int = Query(default=30, ge=1, le=365, description="Número de dias de histórico"),
):
    """Retorna histórico de snapshots de um anúncio."""
    return await service.get_listing_snapshots(db, mlb_id, current_user.id, dias)


@router.get("/{mlb_id}/analysis", response_model=ListingAnalysisOut)
async def get_analysis(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Número de dias de histórico"),
):
    """
    Retorna análise completa de um anúncio:
    - Dados do listing e SKU
    - Snapshots históricos
    - Faixas de preço e margem ótima
    - Projeção de estoque
    - Promoções ativas
    - Dados de publicidade
    - Concorrente vinculado
    - Alertas inteligentes
    """
    return await service.get_listing_analysis(db, mlb_id, current_user.id, days)


@router.get("/{mlb_id}/margem", response_model=MargemResult)
async def get_margem(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    preco: Decimal = Query(..., description="Preço para calcular a margem"),
):
    """Calcula margem para um anúncio com preço informado."""
    return await service.get_margem(db, mlb_id, current_user.id, preco)


@router.patch("/{mlb_id}/price")
async def update_price(
    mlb_id: str,
    payload: UpdatePriceIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Altera o preço de um anúncio."""
    return await service.update_listing_price(
        db, mlb_id, current_user.id, Decimal(str(payload.price))
    )


@router.post("/{mlb_id}/promotions")
async def create_promotion(
    mlb_id: str,
    payload: CreatePromotionIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cria ou renova promoção para um anúncio."""
    return await service.create_or_update_promotion(
        db,
        mlb_id,
        current_user.id,
        payload.discount_pct,
        payload.start_date,
        payload.end_date,
        payload.promotion_id,
    )
