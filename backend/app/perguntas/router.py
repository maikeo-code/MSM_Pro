import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount, User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.mercadolivre.client import MLClient, MLClientError
from app.perguntas.schemas import AnswerQuestionIn, AnswerQuestionOut, QuestionListOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/perguntas", tags=["perguntas"])


@router.get("/", response_model=QuestionListOut)
async def list_questions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str = Query(
        default="UNANSWERED",
        pattern=r"^(UNANSWERED|ANSWERED|CLOSED_UNANSWERED|UNDER_REVIEW)$",
    ),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """Lista perguntas recebidas de todas as contas ML ativas do usuario."""
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    all_questions: list[dict] = []

    for account in accounts:
        if not account.access_token:
            continue
        try:
            async with MLClient(account.access_token) as client:
                data = await client.get_received_questions(
                    status=status, limit=limit
                )
                questions = data.get("questions", [])
                for q in questions:
                    q["_account_nickname"] = account.nickname
                    q["_account_id"] = str(account.id)
                all_questions.extend(questions)
        except Exception as exc:
            logger.error(
                "Falha ao buscar perguntas da conta %s (user=%s): %s",
                account.id,
                current_user.id,
                exc,
                exc_info=True,
            )
            # Falha por conta — outras contas continuam
            continue

    # Ordenar por data mais recente
    all_questions.sort(
        key=lambda q: q.get("date_created", ""), reverse=True
    )

    paginated = all_questions[offset : offset + limit]
    return QuestionListOut(total=len(all_questions), questions=paginated)


@router.post("/{question_id}/answer", response_model=AnswerQuestionOut)
async def answer_question(
    question_id: int,
    body: AnswerQuestionIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Responde uma pergunta especifica do ML."""
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == body.account_id,
            MLAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()

    if not account or not account.access_token:
        raise HTTPException(
            status_code=404, detail="Conta ML nao encontrada"
        )

    try:
        async with MLClient(account.access_token) as client:
            response = await client.answer_question(question_id, body.text)
            return AnswerQuestionOut(status="answered", response=response)
    except MLClientError as e:
        raise HTTPException(
            status_code=502, detail=f"Erro ao responder pergunta: {str(e)}"
        )
