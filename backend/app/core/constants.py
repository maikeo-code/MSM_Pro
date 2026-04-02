"""
Constantes compartilhadas do projeto MSM_Pro.

Taxas ML por tipo de anuncio — fonte unica de verdade.
Valores atualizados conforme tabela oficial ML:
https://www.mercadolivre.com.br/tarifas
"""
from decimal import Decimal


# Taxas ML por tipo de anuncio (percentual sobre o preco de venda)
# Fonte: https://www.mercadolivre.com.br/tarifas
ML_FEES: dict[str, Decimal] = {
    "classico": Decimal("0.11"),    # 11%
    "premium": Decimal("0.16"),     # 16%
    "full": Decimal("0.16"),        # 16% + frete gratis (custo separado)
}

# Mapeamento para uso em contextos float (vendas/service.py, etc.)
ML_FEES_FLOAT: dict[str, float] = {
    "classico": 0.11,
    "premium": 0.16,
    "full": 0.16,
}

# Default ML fee for unknown listing types
ML_FEE_DEFAULT = Decimal("0.16")  # 16%

# ML API pagination
ML_PAGINATION_LIMIT = 50

# Health score thresholds
HEALTH_TITLE_MIN_LEN = 60
HEALTH_MIN_CONVERSION_PCT = 3
HEALTH_MIN_STOCK = 10
HEALTH_RECENT_DAYS_CHECK = 3

# Stock projection thresholds
STOCK_CRITICAL_DAYS = 7
STOCK_WARNING_DAYS = 14
STOCK_EXCESS_DAYS = 60

# Health score status thresholds
HEALTH_EXCELLENT_THRESHOLD = 80
HEALTH_GOOD_THRESHOLD = 60
HEALTH_WARNING_THRESHOLD = 40
