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
    ResponseTemplateIn,
    ResponseTemplateOut,
)
from app.atendimento.service import (
    get_all_atendimentos,
    get_atendimento_stats,
    get_ai_suggestion,
    respond_to_item,
)
# from app.atendimento.service_templates import (
#     list_templates,
#     get_template,
#     create_template,
#     update_template,
#     delete_template,
# )

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


# ─── Response Templates ────────────────────────────────────────────────────────

@router.get("/templates-test")
async def templates_test(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Teste simples para verificar se rotas estão carregando."""
    return {"status": "ok", "msg": "Templates route is loaded"}


@router.get("/templates", response_model=list[ResponseTemplateOut])
async def list_response_templates(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Optional[str] = Query(
        default=None,
        description="Filtrar por categoria: general | pergunta | reclamacao | devolucao | mensagem",
    ),
):
    """Lista todos os templates de resposta do usuário."""
    try:
        from app.atendimento.service_templates import list_templates
        return await list_templates(db=db, user=current_user, category=category)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao listar templates: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao listar templates")


@router.get("/templates/{template_id}", response_model=ResponseTemplateOut)
async def get_response_template(
    template_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obtém um template específico."""
    try:
        from app.atendimento.service_templates import get_template
        return await get_template(db=db, user=current_user, template_id=template_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Erro ao obter template: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao obter template")


@router.post("/templates", response_model=ResponseTemplateOut)
async def create_response_template(
    body: ResponseTemplateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cria um novo template de resposta."""
    try:
        from app.atendimento.service_templates import create_template
        return await create_template(db=db, user=current_user, data=body)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Erro ao criar template: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao criar template")


@router.put("/templates/{template_id}", response_model=ResponseTemplateOut)
async def update_response_template(
    template_id: UUID,
    body: ResponseTemplateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualiza um template existente."""
    try:
        from app.atendimento.service_templates import update_template
        return await update_template(db=db, user=current_user, template_id=template_id, data=body)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e) else 400, detail=str(e))
    except Exception as e:
        logger.error("Erro ao atualizar template: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao atualizar template")


@router.delete("/templates/{template_id}")
async def delete_response_template(
    template_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Deleta um template."""
    try:
        from app.atendimento.service_templates import delete_template
        await delete_template(db=db, user=current_user, template_id=template_id)
        return {"success": True, "message": "Template deletado com sucesso"}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Erro ao deletar template: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao deletar template")
