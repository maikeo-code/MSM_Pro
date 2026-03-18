from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, MLAccount
from app.core.database import get_db
from app.core.deps import get_current_user
from app.reputacao import service
from app.reputacao.schemas import HealthDimensionItem, ReputationCurrentOut, ReputationRiskOut, ReputationSnapshotOut, ReputationThresholdsOut
from app.reputacao.service import REPUTATION_THRESHOLDS

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.get("/current", response_model=ReputationCurrentOut)
async def get_current_reputation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(default=None),
):
    """
    Retorna a reputacao mais recente do vendedor.
    Se nao houver snapshot salvo, busca em tempo real da API ML.
    """
    from sqlalchemy import select

    snapshot = await service.get_current_reputation(
        db, current_user.id, ml_account_id
    )

    # Se nao tem snapshot, tenta buscar em tempo real
    if not snapshot:
        query = select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
        if ml_account_id:
            query = query.where(MLAccount.id == ml_account_id)
        query = query.limit(1)
        result = await db.execute(query)
        account = result.scalar_one_or_none()

        if account:
            snapshot = await service.fetch_and_save_reputation(db, account)
            await db.commit()

    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum snapshot de reputacao encontrado. Conecte uma conta ML ou execute /reputation/sync.",
        )

    # Busca nickname da conta
    acc_result = await db.execute(
        select(MLAccount).where(MLAccount.id == snapshot.ml_account_id)
    )
    account = acc_result.scalar_one_or_none()
    nickname = account.nickname if account else None

    # Calcula score de saude por dimensao com thresholds granulares
    _health_thresholds = {
        "claims": {"good": 0.5, "warning": 2.0},
        "mediations": {"good": 0.3, "warning": 1.0},
        "cancellations": {"good": 1.0, "warning": 3.0},
        "late_shipments": {"good": 2.0, "warning": 5.0},
    }
    _rate_fields = {
        "claims": float(snapshot.claims_rate) if snapshot.claims_rate is not None else 0.0,
        "mediations": float(snapshot.mediations_rate) if snapshot.mediations_rate is not None else 0.0,
        "cancellations": float(snapshot.cancellations_rate) if snapshot.cancellations_rate is not None else 0.0,
        "late_shipments": float(snapshot.late_shipments_rate) if snapshot.late_shipments_rate is not None else 0.0,
    }
    health_by_dimension = []
    for dim, limits in _health_thresholds.items():
        rate = _rate_fields[dim]
        if rate <= limits["good"]:
            dim_status = "good"
        elif rate <= limits["warning"]:
            dim_status = "warning"
        else:
            dim_status = "critical"
        health_by_dimension.append(HealthDimensionItem(
            dimension=dim,
            rate=rate,
            status=dim_status,
            threshold_good=limits["good"],
            threshold_warning=limits["warning"],
        ))

    return ReputationCurrentOut(
        ml_account_id=snapshot.ml_account_id,
        nickname=nickname,
        seller_level=snapshot.seller_level,
        power_seller_status=snapshot.power_seller_status,
        claims_rate=_rate_fields["claims"],
        mediations_rate=_rate_fields["mediations"],
        cancellations_rate=_rate_fields["cancellations"],
        late_shipments_rate=_rate_fields["late_shipments"],
        claims_value=snapshot.claims_value or 0,
        mediations_value=snapshot.mediations_value or 0,
        cancellations_value=snapshot.cancellations_value or 0,
        late_shipments_value=snapshot.late_shipments_value or 0,
        total_sales_60d=snapshot.total_sales_60d or 0,
        completed_sales_60d=snapshot.completed_sales_60d or 0,
        total_revenue_60d=float(snapshot.total_revenue_60d) if snapshot.total_revenue_60d else 0.0,
        captured_at=snapshot.captured_at,
        thresholds=ReputationThresholdsOut(
            claims=float(REPUTATION_THRESHOLDS["claims"]),
            mediations=float(REPUTATION_THRESHOLDS["mediations"]),
            cancellations=float(REPUTATION_THRESHOLDS["cancellations"]),
            late_shipments=float(REPUTATION_THRESHOLDS["late_shipments"]),
        ),
        health_by_dimension=health_by_dimension,
    )


@router.get("/history", response_model=list[ReputationSnapshotOut])
async def get_reputation_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=60, ge=1, le=365),
    ml_account_id: UUID | None = Query(default=None),
):
    """Retorna historico de snapshots de reputacao."""
    snapshots = await service.get_reputation_history(
        db, current_user.id, days, ml_account_id
    )
    return snapshots


@router.post("/sync")
async def sync_reputation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(default=None),
):
    """Forca sync de reputacao agora."""
    from sqlalchemy import select

    query = select(MLAccount).where(
        MLAccount.user_id == current_user.id,
        MLAccount.is_active == True,  # noqa: E712
    )
    if ml_account_id:
        query = query.where(MLAccount.id == ml_account_id)

    result = await db.execute(query)
    accounts = result.scalars().all()

    synced = 0
    for account in accounts:
        snapshot = await service.fetch_and_save_reputation(db, account)
        if snapshot:
            synced += 1

    await db.commit()
    return {"success": True, "synced": synced}


@router.get("/risk-simulator", response_model=ReputationRiskOut)
async def get_risk_simulator(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(default=None),
):
    """
    Simulador de risco de rebaixamento de reputacao.

    Calcula para cada KPI (reclamacoes, mediacoes, cancelamentos, atrasos)
    quantas ocorrencias adicionais podem ocorrer antes de perder o nivel atual.

    risk_level:
      - critical: buffer <= 1 ocorrencia
      - warning: buffer <= 3 ocorrencias
      - safe: buffer > 3 ocorrencias
    """
    risk = await service.get_reputation_risk(db, current_user.id, ml_account_id)

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum snapshot de reputacao disponivel. Execute /reputation/sync primeiro.",
        )

    return ReputationRiskOut(**risk)
