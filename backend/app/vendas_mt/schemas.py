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
    total: float          # valor dos produtos (base de imposto e margem)
    pago: float           # o que o comprador pagou (paid_amount) — linha "Pago comprador" do Turbo
    produtos: float       # compat (== total)
    tarifaML: float | None = None
    frete: float | None = None        # custo do vendedor + frete pago pelo comprador
    lucroBruto: float | None = None   # pago - frete - tarifa
    custoProduto: float | None = None
    imposto: float | None = None      # 8,5% do total, só quando SKU configurado (como no Turbo)
    receitaLiquida: float | None = None  # compat (== lucroBruto)
    lucro: float | None = None
    margem: float | None = None       # lucro / total * 100
    temCusto: bool = False


class VendasMTResponse(BaseModel):
    fonte: str  # "ml-live" — sempre cadeia ML ao vivo
    conta: str  # nickname da conta ML usada
    total: int
    vendas: list[VendaMTOut]
