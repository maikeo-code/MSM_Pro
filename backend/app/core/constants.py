"""
Constantes compartilhadas do projeto MSM_Pro.

Taxas ML por tipo de anuncio — fonte unica de verdade.
Valores atualizados conforme tabela oficial ML:
https://www.mercadolivre.com.br/tarifas
"""
from decimal import Decimal


# Taxas ML por tipo de anuncio (percentual sobre o preco de venda)
ML_FEES: dict[str, Decimal] = {
    "classico": Decimal("0.115"),   # 11.5%
    "premium": Decimal("0.17"),     # 17%
    "full": Decimal("0.17"),        # 17% + frete gratis (custo separado)
}

# Mapeamento para uso em contextos float (vendas/service.py, etc.)
ML_FEES_FLOAT: dict[str, float] = {
    "classico": 0.115,
    "premium": 0.17,
    "full": 0.17,
}
