from pydantic import BaseModel
from typing import Optional


class AnuncioAnalise(BaseModel):
    """Schema de análise de um anúncio individual."""
    mlb_id: str
    titulo: str
    descricao: Optional[str] = None
    tipo: str  # "fulfillment", "classico", "premium"
    preco: float
    preco_original: Optional[float] = None

    # Visitas
    visitas_hoje: int = 0
    visitas_ontem: int = 0

    # Conversão (%)
    conversao_7d: Optional[float] = None
    conversao_15d: Optional[float] = None
    conversao_30d: Optional[float] = None

    # Vendas
    vendas_hoje: int = 0
    vendas_ontem: int = 0
    vendas_anteontem: int = 0
    vendas_7d: int = 0

    # Estoque
    estoque: int = 0

    # ROAS (%)
    roas_7d: Optional[float] = None  # null = N/D (Ads API indisponível)
    roas_15d: Optional[float] = None
    roas_30d: Optional[float] = None

    # Extras
    thumbnail: Optional[str] = None
    permalink: Optional[str] = None
    quality_score: Optional[int] = None

    class Config:
        from_attributes = True


class AnaliseResponse(BaseModel):
    """Response com lista de análises."""
    total: int
    anuncios: list[AnuncioAnalise]
