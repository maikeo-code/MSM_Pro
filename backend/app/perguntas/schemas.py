"""Schemas Pydantic para o módulo de perguntas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


# ========== Schemas para persistência em banco ==========


class QuestionDB(BaseModel):
    """Pergunta persistida no banco local."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ml_question_id: int
    ml_account_id: UUID
    mlb_id: str
    item_title: str | None = None
    item_thumbnail: str | None = None
    text: str
    status: str
    buyer_id: int | None = None
    buyer_nickname: str | None = None
    date_created: datetime
    answer_text: str | None = None
    answer_date: datetime | None = None
    answer_source: str | None = None
    ai_suggestion_text: str | None = None
    ai_suggestion_confidence: str | None = None
    ai_suggested_at: datetime | None = None
    synced_at: datetime
    created_at: datetime
    updated_at: datetime


class QuestionDBListOut(BaseModel):
    """Resposta paginada da listagem de perguntas do banco."""

    total: int
    page: int
    limit: int
    questions: list[QuestionDB]


class QuestionStatsOut(BaseModel):
    """Estatísticas de perguntas por usuário e período."""

    total: int
    unanswered: int
    answered: int
    urgent: int
    avg_response_time_hours: float | None = None
    by_account: dict[str, int] = Field(
        default_factory=dict, description="account_nickname -> count"
    )


class AISuggestionRequest(BaseModel):
    """Request para gerar sugestão IA."""

    regenerate: bool = Field(
        default=False, description="Regenerar sugestão ignorando cache"
    )


class AISuggestionResponse(BaseModel):
    """Resposta com sugestão IA."""

    suggestion: str
    confidence: str = Field(pattern=r"^(high|medium|low)$")
    question_type: str | None = None
    cached: bool = False
    latency_ms: int | None = None


class SyncQuestionsOut(BaseModel):
    """Resultado da sincronização de perguntas."""

    synced: int = Field(description="Total de perguntas sincronizadas")
    new: int = Field(description="Perguntas novas inseridas")
    updated: int = Field(description="Perguntas atualizadas")
    errors: int = Field(description="Erros durante sincronização")


class AnswerFromSuggestionIn(BaseModel):
    """Body para responder uma pergunta usando sugestão IA."""

    text: str = Field(
        min_length=1, max_length=2000, description="Texto da resposta (pode editada)"
    )
    account_id: UUID = Field(description="UUID da conta ML")
    source: str = Field(
        default="ai",
        pattern=r"^(ai|template|manual)$",
        description="Origem da resposta",
    )
    template_id: UUID | None = Field(
        default=None, description="Se source=template, ID do template"
    )
    suggestion_was_edited: bool = Field(
        default=False, description="Se o usuário editou a sugestão antes de enviar"
    )
