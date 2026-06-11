"""Schemas da aba Vendas (MT) — réplica do Mercado Turbo.

Campos em camelCase para casar 1:1 com o tipo `Venda` do frontend portado,
evitando camada de mapeamento. Ver mercadoturbo_research/03-MECANISMO-ENDPOINTS.md.
"""

from pydantic import BaseModel


class VendaMTOut(BaseModel):
    venda: str
    mlb: str | None = None
    sku: str | None = None
    titulo: str
    data: str | None = None
    status: str | None = None
    total: float
    produtos: float
    tarifaML: float | None = None
    imposto: float | None = None
    receitaLiquida: float | None = None
    custoProduto: float | None = None
    frete: float | None = None
    lucro: float | None = None
    margem: float | None = None
    temCusto: bool = False


class VendasMTResponse(BaseModel):
    fonte: str  # "ml-live" — sempre cadeia ML ao vivo
    conta: str  # nickname da conta ML usada
    total: int
    vendas: list[VendaMTOut]
