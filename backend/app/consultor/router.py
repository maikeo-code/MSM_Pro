from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.consultor.schemas import ChatRequest, ChatResponse, ConsultorRequest, ConsultorResponse
from app.consultor.service import analisar_listings
from app.consultor.service_chat import chat_with_tools
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


@router.post("/chat", response_model=ChatResponse)
async def chat_consultor(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Chat interativo com o Consultor IA. Consulta dados do sistema via tools read-only."""
    history = [{"role": msg.role, "content": msg.content} for msg in request.history]
    reply, tokens = await chat_with_tools(db, current_user.id, request.message, history)
    return ChatResponse(reply=reply, tokens_used=tokens)
