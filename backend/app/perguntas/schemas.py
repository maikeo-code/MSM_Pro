"""Schemas Pydantic para o módulo de perguntas."""
from uuid import UUID

from pydantic import BaseModel, Field


class AnswerQuestionIn(BaseModel):
    """Body para responder uma pergunta do ML."""

    text: str = Field(min_length=1, max_length=2000, description="Texto da resposta")
    account_id: UUID = Field(description="UUID da conta ML que fará a resposta")


class QuestionOut(BaseModel):
    """Representação de uma pergunta recebida do ML (pass-through da API ML)."""

    # Campos vindos diretamente da API ML — sem validação estrita
    # para não quebrar se ML adicionar campos novos.
    model_config = {"extra": "allow"}


class QuestionListOut(BaseModel):
    """Resposta paginada da listagem de perguntas."""

    total: int
    questions: list[dict]


class AnswerQuestionOut(BaseModel):
    """Resposta ao responder uma pergunta."""

    status: str
    response: dict | None = None
