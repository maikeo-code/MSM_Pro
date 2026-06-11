"""Router da aba Vendas (MT) — réplica do Mercado Turbo dentro do MSM_Pro.

Endpoint isolado e aditivo: NÃO altera a tela de Vendas/Pedidos atual.
Usa o OAuth do ML já gerenciado pelo MSM_Pro.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.vendas_mt import service
from app.vendas_mt.schemas import VendasMTResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vendas-mt", tags=["vendas-mt"])


@router.get("/", response_model=VendasMTResponse)
async def listar_vendas_mt(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(
        default="30d",
        pattern=r"^(1d|2d|7d|15d|30d|60d)$",
        description="Período: 1d, 2d, 7d, 15d, 30d (padrão), 60d",
    ),
    ml_account_id: UUID | None = Query(
        default=None, description="Conta ML específica (opcional; padrão = primeira ativa)"
    ),
    limit: int = Query(default=50, ge=1, le=50),
):
    """Lista vendas calculadas pela cadeia de endpoints do Mercado Turbo (ML ao vivo).

    Decomposição: pago − frete (shipments/costs) − tarifa (marketplace_fee)
    − custo (Produtos) − imposto (tax-config) = lucro.
    """
    days = {"1d": 1, "2d": 2, "7d": 7, "15d": 15, "30d": 30, "60d": 60}.get(period, 30)
    conta, vendas = await service.listar_vendas_mt(
        db, current_user.id, ml_account_id, days, limit
    )
    return VendasMTResponse(
        fonte="ml-live",
        conta=conta.nickname if conta else "",
        total=len(vendas),
        vendas=vendas,
    )
