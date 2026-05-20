"""
Lógica assíncrona para pré-geração de sugestões IA e auto-resposta.

Funções exportadas:
  - _pre_generate_suggestions_async: gera sugestões para perguntas sem sugestão
  - _auto_answer_high_confidence_async: envia respostas automáticas quando confidence=high
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.auth.models import MLAccount
from app.perguntas.models import Question
from app.perguntas.service import answer_question_and_track
from app.perguntas.service_suggestion import generate_suggestion

logger = logging.getLogger(__name__)


async def _pre_generate_suggestions_async() -> dict:
    """
    Pré-gera sugestões de IA para perguntas não respondidas que ainda
    não possuem sugestão (ai_suggestion_text IS NULL).

    Processa no máximo 20 perguntas por execução para não sobrecarregar
    a API da Anthropic.
    """
    total_generated = 0
    errors = 0

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Question, MLAccount)
                .join(MLAccount, Question.ml_account_id == MLAccount.id)
                .where(
                    Question.status == "UNANSWERED",
                    Question.ai_suggestion_text.is_(None),
                    MLAccount.is_active == True,  # noqa: E712
                    MLAccount.access_token.isnot(None),
                )
                .limit(20)
            )
            rows = result.all()

            for question, account in rows:
                try:
                    await generate_suggestion(
                        db, question, account.access_token,
                        regenerate=False,
                        account_id=str(account.id),
                    )
                    total_generated += 1
                except Exception as exc:
                    logger.error(
                        "Pre-generate: falha para pergunta %s: %s",
                        question.id, exc, exc_info=True,
                    )
                    errors += 1
                    continue

    except Exception as exc:
        logger.error("Erro geral em pre_generate_suggestions: %s", exc, exc_info=True)
        errors += 1

    return {
        "generated": total_generated,
        "errors": errors,
    }


async def _auto_answer_high_confidence_async() -> dict:
    """
    Envia respostas automáticas para perguntas não respondidas que possuem
    sugestão IA com confidence='high'.

    Critérios:
      - status = UNANSWERED
      - ai_suggestion_confidence = 'high'
      - ai_suggestion_text IS NOT NULL
      - answer_text IS NULL (ainda não respondida)

    Processa no máximo 10 perguntas por execução.
    """
    total_sent = 0
    errors = 0

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Question, MLAccount)
                .join(MLAccount, Question.ml_account_id == MLAccount.id)
                .where(
                    Question.status == "UNANSWERED",
                    Question.ai_suggestion_confidence == "high",
                    Question.ai_suggestion_text.isnot(None),
                    Question.answer_text.is_(None),
                    MLAccount.is_active == True,  # noqa: E712
                    MLAccount.access_token.isnot(None),
                )
                .limit(10)
            )
            rows = result.all()

            for question, account in rows:
                try:
                    suggestion = question.ai_suggestion_text
                    if not suggestion:
                        continue

                    await answer_question_and_track(
                        db=db,
                        question=question,
                        account=account,
                        answer_text=suggestion,
                        source="ai_auto",
                    )
                    total_sent += 1
                    logger.info(
                        "Auto-answer enviado para pergunta %s (conta %s)",
                        question.id, account.id,
                    )
                except Exception as exc:
                    logger.error(
                        "Auto-answer: falha para pergunta %s: %s",
                        question.id, exc, exc_info=True,
                    )
                    errors += 1
                    continue

    except Exception as exc:
        logger.error("Erro geral em auto_answer_high_confidence: %s", exc, exc_info=True)
        errors += 1

    return {
        "sent": total_sent,
        "errors": errors,
    }
