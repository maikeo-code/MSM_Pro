"""
Router de análise de anúncios.

Endpoints para buscar análise detalhada de anúncios com métricas de vendas,
visitas, conversão, estoque e ROAS.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.analise import service
from app.analise.schemas import AnaliseResponse
from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/listings", response_model=AnaliseResponse)
async def get_analysis_listings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Busca análise completa de todos os anúncios do usuário.

    Retorna tabela com:
    - Anúncio (título, MLB ID)
    - Tipo de anúncio (classico, premium, fulfillment)
    - Preço (com desconto)
    - Visitas (hoje, ontem)
    - Conversão últimos 7/15/30 dias (%)
    - Vendas (hoje, ontem, anteontem, últimos 7 dias)
    - Estoque
    - ROAS últimos 7/15/30 dias (%) ou N/D se Ads API indisponível

    Dados calculados a partir dos snapshots históricos dos listings.
    Timezone: BRT (América/São Paulo).

    Returns:
        AnaliseResponse com total de anúncios e lista detalhada.
    """
    anuncios = await service.get_analysis_listings(db, user)
    return AnaliseResponse(total=len(anuncios), anuncios=anuncios)
