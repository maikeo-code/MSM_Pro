"""
Router de alertas MSM_Pro.

Prefixo: /api/v1/alertas
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.alertas import service
from app.alertas.schemas import (
    AlertConfigCreate,
    AlertConfigOut,
    AlertConfigUpdate,
    AlertEventOut,
)
from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter(prefix="/alertas", tags=["alertas"])


# ============================================================
# AlertConfig — CRUD
# ============================================================


@router.get("/", response_model=list[AlertConfigOut])
async def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    listing_id: UUID | None = Query(default=None, description="Filtrar por listing"),
    is_active: bool | None = Query(default=None, description="Filtrar por status ativo"),
):
    """Lista configurações de alerta do usuário."""
    return await service.list_alert_configs(
        db, current_user.id, listing_id=listing_id, is_active=is_active
    )


@router.post("/", response_model=AlertConfigOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: AlertConfigCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Cria uma nova configuração de alerta.

    Tipos suportados:
    - `conversion_below` — conversão < threshold%
    - `stock_below` — estoque < threshold unidades
    - `competitor_price_change` — concorrente mudou preço
    - `no_sales_days` — 0 vendas por threshold dias
    - `competitor_price_below` — concorrente vendendo abaixo de R$ threshold

    Canais: `email` (padrão) | `webhook`
    """
    alert = await service.create_alert_config(db, current_user.id, payload)
    await db.commit()
    return alert


@router.get("/events/", response_model=list[AlertEventOut])
async def list_events(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=90, description="Janela de dias"),
):
    """Lista todos os eventos de alerta disparados nos últimos N dias."""
    return await service.list_alert_events(db, current_user.id, days=days)


@router.get("/events/{alert_id}", response_model=list[AlertEventOut])
async def list_events_by_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=90, description="Janela de dias"),
):
    """Lista eventos disparados por um alerta específico."""
    return await service.list_events_by_alert(db, current_user.id, alert_id, days=days)


@router.get("/{alert_id}", response_model=AlertConfigOut)
async def get_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna detalhes de uma configuração de alerta."""
    return await service.get_alert_config(db, current_user.id, alert_id)


@router.put("/{alert_id}", response_model=AlertConfigOut)
async def update_alert(
    alert_id: UUID,
    payload: AlertConfigUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualiza threshold, canal ou status ativo de um alerta."""
    alert = await service.update_alert_config(db, current_user.id, alert_id, payload)
    await db.commit()
    return alert


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Desativa (soft-delete) uma configuração de alerta."""
    await service.deactivate_alert_config(db, current_user.id, alert_id)
    await db.commit()
