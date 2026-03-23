from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.concorrencia import service
from app.concorrencia.schemas import CompetitorCreate, CompetitorHistoryOut, CompetitorOut
from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.get("/", response_model=list[CompetitorOut])
async def list_all_competitors(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Lista todos os concorrentes ativos do usuário."""
    return await service.get_all_competitors(db, current_user.id)


@router.post("/", response_model=CompetitorOut, status_code=status.HTTP_201_CREATED)
async def add_competitor(
    payload: CompetitorCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Vincula um concorrente (MLB externo) a um listing do usuário.
    Busca dados reais do concorrente na API ML para enriquecer os dados (título, seller, thumbnail).
    """
    from sqlalchemy import select
    from app.auth.models import MLAccount
    from app.vendas.models import Listing

    # Busca o listing para obter a conta ML vinculada
    listing_result = await db.execute(
        select(Listing).where(
            Listing.id == payload.listing_id,
            Listing.user_id == current_user.id,
        )
    )
    listing = listing_result.scalar_one_or_none()

    # Busca o token da conta ML do listing
    ml_token = None
    if listing and listing.ml_account_id:
        ml_account_result = await db.execute(
            select(MLAccount).where(MLAccount.id == listing.ml_account_id)
        )
        ml_account = ml_account_result.scalar_one_or_none()
        if ml_account and ml_account.access_token:
            ml_token = ml_account.access_token

    competitor = await service.add_competitor(
        db,
        current_user.id,
        payload.listing_id,
        payload.competitor_mlb_id,
        ml_token=ml_token,
    )
    await db.commit()
    return competitor


@router.get("/listing/{listing_id}", response_model=list[CompetitorOut])
async def get_competitors_by_listing(
    listing_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Lista concorrentes vinculados a um listing específico.
    """
    competitors = await service.get_competitors_by_listing(
        db, current_user.id, listing_id
    )
    return competitors


@router.get("/sku/{product_id}", response_model=list[CompetitorOut])
async def get_competitors_by_sku(
    product_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Lista concorrentes vinculados a um SKU (produto).
    Retorna todos os concorrentes dos listings desse SKU.
    """
    competitors = await service.get_competitors_by_sku(
        db, current_user.id, product_id
    )
    return competitors


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_competitor(
    competitor_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Remove um concorrente vinculado.
    """
    await service.remove_competitor(db, current_user.id, competitor_id)
    await db.commit()


@router.get("/{competitor_id}/history", response_model=CompetitorHistoryOut)
async def get_competitor_history(
    competitor_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Numero de dias de historico"),
):
    """
    Retorna historico de preco e vendas de um concorrente nos ultimos N dias.
    Util para gerar grafico de preco ao longo do tempo.
    """
    return await service.get_competitor_history(db, current_user.id, competitor_id, days)
