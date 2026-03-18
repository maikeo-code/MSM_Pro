import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount, User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.mercadolivre.client import MLClient, MLClientError

router = APIRouter(prefix="/perguntas", tags=["perguntas"])


@router.get("/")
async def list_questions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str = Query(
        default="UNANSWERED",
        pattern=r"^(UNANSWERED|ANSWERED|CLOSED_UNANSWERED|UNDER_REVIEW)$",
    ),
    limit: int = Query(default=20, ge=1, le=50),
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
        except Exception:
            # Falha silenciosa por conta — outras contas continuam
            continue

    # Ordenar por data mais recente
    all_questions.sort(
        key=lambda q: q.get("date_created", ""), reverse=True
    )

    return {"total": len(all_questions), "questions": all_questions[:limit]}


@router.post("/{question_id}/answer")
async def answer_question(
    question_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: dict,
):
    """Responde uma pergunta especifica do ML.

    Body esperado: {"text": "resposta", "account_id": "uuid-da-conta-ml"}
    """
    text: str = body.get("text", "").strip()
    account_id_raw: str | None = body.get("account_id")

    if not text:
        raise HTTPException(
            status_code=400, detail="Texto da resposta e obrigatorio"
        )
    if not account_id_raw:
        raise HTTPException(
            status_code=400, detail="account_id e obrigatorio"
        )

    try:
        account_uuid = uuid.UUID(account_id_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="account_id invalido")

    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == account_uuid,
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
            response = await client.answer_question(question_id, text)
            return {"status": "answered", "response": response}
    except MLClientError as e:
        raise HTTPException(
            status_code=502, detail=f"Erro ao responder pergunta: {str(e)}"
        )
