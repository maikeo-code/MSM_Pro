import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount, User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.perguntas.models import Question
from app.perguntas.schemas import (
    AISuggestionRequest,
    AISuggestionResponse,
    AnswerFromSuggestionIn,
    AnswerQuestionOut,
    QuestionDB,
    QuestionDBListOut,
    QuestionStatsOut,
    SyncQuestionsOut,
)
from app.perguntas.service import (
    answer_question_and_track,
    get_question_stats,
    get_questions_by_listing,
    list_questions_from_db,
    sync_questions_for_account,
)
from app.perguntas.service_suggestion import generate_suggestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/perguntas", tags=["perguntas"])


async def _get_validated_account(
    db: AsyncSession, account_id: UUID, user_id: UUID
) -> MLAccount:
    """
    Valida que a conta pertence ao usuário e tem token.

    Raises:
        HTTPException 404 se conta não encontrada ou sem token
    """
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == account_id,
            MLAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()

    if not account or not account.access_token:
        raise HTTPException(
            status_code=404, detail="Conta ML não encontrada ou sem token"
        )

    return account


@router.get("/", response_model=QuestionDBListOut)
async def list_questions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None),
    ml_account_id: UUID | None = Query(default=None),
    mlb_id: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Lista perguntas do banco local com filtros.

    Query parameters:
    - status: UNANSWERED | ANSWERED | CLOSED_UNANSWERED | UNDER_REVIEW
    - ml_account_id: Filtro de conta ML (opcional)
    - mlb_id: Filtro de anúncio específico (opcional)
    - search: Busca em texto ou nickname do comprador (opcional)
    - limit: Paginação (padrão 20)
    - offset: Paginação (padrão 0)
    """
    questions, total = await list_questions_from_db(
        db,
        current_user.id,
        status=status,
        ml_account_id=ml_account_id,
        mlb_id=mlb_id,
        search=search,
        offset=offset,
        limit=limit,
    )

    # list_questions_from_db agora retorna dicts ja enriquecidos com
    # item_thumbnail e item_permalink (Tema 4).
    return QuestionDBListOut(
        total=total,
        page=offset // limit + 1,
        limit=limit,
        questions=[QuestionDB(**q) for q in questions],
    )


@router.get("/stats", response_model=QuestionStatsOut)
async def question_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(default=None),
):
    """
    Retorna estatísticas de perguntas.

    Query parameters:
    - ml_account_id: Filtro de conta ML (opcional; sem parâmetro = todas as contas)
    """
    stats = await get_question_stats(db, current_user.id, ml_account_id)
    return QuestionStatsOut(**stats)


@router.post("/sync", response_model=SyncQuestionsOut)
async def sync_questions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Trigger manual de sincronização de perguntas.

    Sincroniza perguntas de TODAS as contas ML ativas do usuário.
    """
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    totals = {"synced": 0, "new": 0, "updated": 0, "errors": 0}

    for account in accounts:
        if not account.access_token:
            continue

        try:
            r = await sync_questions_for_account(db, account)
            for k in totals:
                totals[k] += r.get(k, 0)
        except Exception as exc:
            logger.error(
                "Erro ao sincronizar perguntas da conta %s (user=%s): %s",
                account.id,
                current_user.id,
                exc,
                exc_info=True,
            )
            totals["errors"] += 1

    return SyncQuestionsOut(**totals)


@router.post("/{question_id}/answer", response_model=AnswerQuestionOut)
async def answer_question(
    question_id: UUID,
    body: AnswerFromSuggestionIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Responde uma pergunta e registra no banco.

    Body:
    - text: Texto da resposta (pode ser editado de sugestão IA)
    - account_id: UUID da conta ML que fará a resposta
    - source: 'ai' | 'template' | 'manual' (padrão 'ai')
    - template_id: UUID do template (se source='template')
    - suggestion_was_edited: Se editou a sugestão antes de enviar
    """
    # Valida conta
    account = await _get_validated_account(db, body.account_id, current_user.id)

    # Responde e registra
    result = await answer_question_and_track(
        db,
        question_id,
        body.text,
        account,
        source=body.source,
        template_id=body.template_id,
        suggestion_was_edited=body.suggestion_was_edited,
    )

    return AnswerQuestionOut(status=result["status"], response=result)


@router.post("/{question_id}/suggest", response_model=AISuggestionResponse)
async def suggest_answer(
    question_id: UUID,
    body: AISuggestionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Gera sugestão IA para uma pergunta.

    Body:
    - regenerate: Se True, ignora cache e gera nova sugestão

    Retorna sugestão com confiança, tipo de pergunta e latência.
    """
    # Busca pergunta do banco
    result = await db.execute(
        select(Question).where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")

    # Valida que pertence a uma conta do usuário
    account_result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == question.ml_account_id,
            MLAccount.user_id == current_user.id,
        )
    )
    account = account_result.scalar_one_or_none()

    if not account or not account.access_token:
        raise HTTPException(
            status_code=403, detail="Acesso negado a esta pergunta"
        )

    # Gera sugestão
    result = await generate_suggestion(
        db, question, account.access_token, regenerate=body.regenerate
    )

    return AISuggestionResponse(**result)


@router.get("/by-listing/{mlb_id}")
async def questions_by_listing(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Retorna histórico Q&A de um anúncio específico.

    Path parameters:
    - mlb_id: ID do anúncio (ex: MLB1234567890)
    """
    questions = await get_questions_by_listing(db, current_user.id, mlb_id)
    return {
        "total": len(questions),
        "questions": [QuestionDB(**q) for q in questions],
    }
