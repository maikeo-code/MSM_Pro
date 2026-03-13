from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount, User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.ads import service
from app.ads.schemas import AdsCampaignDetailOut, AdsDashboardOut

router = APIRouter(prefix="/ads", tags=["ads"])


async def _get_first_ml_account(db: AsyncSession, user_id: UUID) -> MLAccount | None:
    """Helper: retorna a primeira conta ML ativa do usuário."""
    result = await db.execute(
        select(MLAccount)
        .where(MLAccount.user_id == user_id, MLAccount.is_active == True)
        .order_by(MLAccount.created_at)
    )
    return result.scalar_one_or_none()


@router.get("/", response_model=AdsDashboardOut)
async def get_ads_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(default=None, description="ID da conta ML. Se omitido, usa a primeira conta ativa."),
    period: int = Query(default=30, ge=1, le=90, description="Periodo em dias (1-90)"),
):
    """Dashboard de publicidade — resumo agregado de todas as campanhas."""
    if ml_account_id is None:
        account = await _get_first_ml_account(db, current_user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nenhuma conta ML conectada",
            )
        ml_account_id = account.id

    return await service.get_ads_dashboard(db, ml_account_id, period=period, user_id=current_user.id)


@router.get("/{campaign_id}", response_model=AdsCampaignDetailOut)
async def get_campaign_detail(
    campaign_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=90, description="Janela de dias para snapshots"),
):
    """Detalhe de uma campanha + timeline de métricas."""
    # Ownership check: garante que a campanha pertence a uma ml_account do current_user
    from app.ads.models import AdCampaign
    campaign_result = await db.execute(
        select(AdCampaign)
        .join(MLAccount, AdCampaign.ml_account_id == MLAccount.id)
        .where(
            AdCampaign.id == campaign_id,
            MLAccount.user_id == current_user.id,
        )
    )
    campaign_obj = campaign_result.scalar_one_or_none()
    if not campaign_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada",
        )

    detail = await service.get_campaign_detail(db, campaign_id, days=days)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada",
        )
    return detail


@router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_ads(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(default=None, description="ID da conta ML. Se omitido, sincroniza todas as contas."),
):
    """Força sync de campanhas de publicidade da API ML."""
    from app.mercadolivre.client import MLClient

    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,
        )
    )
    accounts = list(result.scalars().all())

    if ml_account_id is not None:
        accounts = [a for a in accounts if a.id == ml_account_id]

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma conta ML encontrada",
        )

    results = []
    for account in accounts:
        if not account.access_token:
            continue
        async with MLClient(account.access_token) as ml_client:
            sync_result = await service.sync_ads_from_ml(db, ml_client, account)
            results.append(sync_result)

    # O caller (router) é responsável pelo commit
    await db.commit()
    return {"results": results, "accounts_synced": len(results)}
