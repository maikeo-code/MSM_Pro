from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ConsultorRequest(BaseModel):
    mlb_id: Optional[str] = None


class ConsultorResponse(BaseModel):
    analise: str
    anuncios_analisados: int
    gerado_em: datetime
