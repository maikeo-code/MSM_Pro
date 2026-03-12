from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.consultor.schemas import ConsultorRequest, ConsultorResponse
from app.consultor.service import analisar_listings
from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter(prefix="/consultor", tags=["consultor"])


@router.post("/analisar", response_model=ConsultorResponse)
async def analisar(
    payload: ConsultorRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Analisa os anúncios do usuário usando IA (Claude) e retorna insights e recomendações.

    - Se `mlb_id` for informado, analisa apenas aquele anúncio.
    - Se não informado, analisa todos (máximo 20).
    """
    analise, anuncios_analisados = await analisar_listings(
        db=db,
        user_id=current_user.id,
        mlb_id=payload.mlb_id,
    )

    return ConsultorResponse(
        analise=analise,
        anuncios_analisados=anuncios_analisados,
        gerado_em=datetime.now(timezone.utc),
    )
