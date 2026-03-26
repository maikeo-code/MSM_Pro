from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConsultorRequest(BaseModel):
    mlb_id: Optional[str] = None


class ConsultorResponse(BaseModel):
    analise: str
    anuncios_analisados: int
    gerado_em: datetime


# Chat interativo com ferramentas
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(..., max_length=5000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    tokens_used: int = 0
