"""Schemas Pydantic para o módulo de Atendimento unificado."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AtendimentoItem(BaseModel):
    """Representa um item de atendimento unificado (pergunta, reclamação, mensagem ou devolução)."""

    id: str  # question_id, claim_id ou message pack_id (como string)
    type: str  # "pergunta" | "reclamacao" | "mensagem" | "devolucao"
    status: str  # unanswered, open, closed, answered, etc.
    date_created: datetime
    text: str
    from_user: Optional[dict] = None  # {"id": ..., "nickname": ...}
    item_id: Optional[str] = None
    item_title: Optional[str] = None
    order_id: Optional[str] = None
    last_message: Optional[str] = None
    requires_action: bool = False
    ai_suggested_response: Optional[str] = None
    # Metadados de conta ML (para roteamento de resposta)
    account_id: Optional[str] = None
    account_nickname: Optional[str] = None


class AtendimentoListOut(BaseModel):
    """Resposta paginada da listagem unificada de atendimentos."""

    total: int
    items: list[AtendimentoItem]
    by_type: dict  # {"perguntas": 5, "reclamacoes": 2, "mensagens": 1, "devolucoes": 0}


class AtendimentoRespondIn(BaseModel):
    """Body para responder um item de atendimento."""

    text: str = Field(min_length=1, max_length=2000, description="Texto da resposta")
    account_id: UUID = Field(description="UUID da conta ML que fará a resposta")


class AtendimentoRespondOut(BaseModel):
    """Retorno após responder um item de atendimento."""

    success: bool
    message: str


class AtendimentoStatsOut(BaseModel):
    """Contadores por tipo e status de atendimento."""

    total: int
    requires_action: int
    by_type: dict  # {"perguntas": N, "reclamacoes": N, "mensagens": N, "devolucoes": N}
    by_status: dict  # {"unanswered": N, "open": N, "answered": N, "closed": N}


class AISuggestionOut(BaseModel):
    """Sugestão de resposta gerada por IA."""

    suggestion: str
    confidence: float  # 0.0 a 1.0
    based_on: list[str]  # IDs das respostas anteriores usadas como base
