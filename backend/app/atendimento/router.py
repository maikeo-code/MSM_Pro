"""Router do módulo de Atendimento Unificado."""
import logging
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.mercadolivre.client import MLClientError
from app.atendimento.schemas import (
    AISuggestionOut,
    AtendimentoListOut,
    AtendimentoRespondIn,
    AtendimentoRespondOut,
    AtendimentoStatsOut,
)
from app.atendimento.service import (
    get_all_atendimentos,
    get_atendimento_stats,
    get_ai_suggestion,
    respond_to_item,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/atendimento", tags=["Atendimento"])

_VALID_TYPES = {"pergunta", "reclamacao", "mensagem", "devolucao"}


@router.get("/", response_model=AtendimentoListOut)
async def list_atendimentos(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    type: Optional[str] = Query(
        default=None,
        description="Filtrar por tipo: pergunta | reclamacao | mensagem | devolucao",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filtrar por status (ex: unanswered, open, answered, closed)",
    ),
    offset: int = Query(default=0, ge=0, description="Offset para paginação"),
    limit: int = Query(default=20, ge=1, le=100, description="Itens por página"),
):
    """
    Lista unificada de perguntas, reclamações, mensagens pós-venda e devoluções.
    Agrega todas as contas ML ativas do usuário, ordenado por data decrescente.
    Falhas em endpoints individuais são logadas e não interrompem a resposta.
    """
    if type and type not in _VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido. Use um de: {', '.join(sorted(_VALID_TYPES))}",
        )

    return await get_all_atendimentos(
        db=db,
        user=current_user,
        status_filter=status,
        type_filter=type,
        offset=offset,
        limit=limit,
    )


@router.get("/stats", response_model=AtendimentoStatsOut)
async def atendimento_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Retorna contadores de atendimentos por tipo e status.
    Útil para badges e alertas no dashboard (ex: N perguntas sem resposta).
    """
    return await get_atendimento_stats(db=db, user=current_user)


@router.post("/{item_type}/{item_id}/respond", response_model=AtendimentoRespondOut)
async def respond_atendimento(
    item_type: str,
    item_id: str,
    body: AtendimentoRespondIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Responde um item de atendimento.
    - pergunta: chama POST /answers no ML
    - reclamacao / devolucao: chama POST /v1/claims/{id}/messages
    - mensagem: chama POST /messages/packs/{id}/sellers/{seller_id}
    """
    if item_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido. Use um de: {', '.join(sorted(_VALID_TYPES))}",
        )

    try:
        result = await respond_to_item(
            db=db,
            user=current_user,
            item_type=item_type,
            item_id=item_id,
            text=body.text,
            account_id=body.account_id,
        )
        return AtendimentoRespondOut(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MLClientError as e:
        logger.error(
            "Falha ao responder item_type=%s item_id=%s user=%s: %s",
            item_type,
            item_id,
            current_user.id,
            e,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao enviar resposta ao Mercado Livre: {str(e)}",
        )


@router.get("/{item_type}/{item_id}/ai-suggestion", response_model=AISuggestionOut)
async def ai_suggestion(
    item_type: str,
    item_id: str,
    account_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Retorna sugestão de resposta gerada por IA (Claude Haiku) para um item de atendimento.
    Usa as últimas respostas da conta como exemplos few-shot.
    Requer ANTHROPIC_API_KEY configurada no servidor.
    """
    if item_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido. Use um de: {', '.join(sorted(_VALID_TYPES))}",
        )

    return await get_ai_suggestion(
        db=db,
        user=current_user,
        item_type=item_type,
        item_id=item_id,
        account_id=account_id,
    )
