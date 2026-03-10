from decimal import Decimal, ROUND_HALF_UP


# Taxas ML por tipo de anúncio
ML_FEES = {
    "classico": Decimal("0.11"),
    "premium": Decimal("0.16"),
    "full": Decimal("0.16"),  # Full também tem frete grátis (custo separado)
}


def calcular_taxa_ml(listing_type: str) -> Decimal:
    """
    Retorna a taxa percentual do ML para o tipo de anúncio.
    classico=0.11, premium=0.16, full=0.16
    """
    listing_type_lower = listing_type.lower()
    if listing_type_lower not in ML_FEES:
        raise ValueError(f"Tipo de anúncio inválido: {listing_type}. Use: classico, premium, full")
    return ML_FEES[listing_type_lower]


def calcular_margem(
    preco: Decimal,
    custo: Decimal,
    listing_type: str,
    frete: Decimal = Decimal("0"),
) -> dict:
    """
    Calcula a margem de um anúncio.

    Args:
        preco: Preço de venda do produto
        custo: Custo do SKU (CMV)
        listing_type: Tipo do anúncio (classico/premium/full)
        frete: Custo de frete (para anúncios full, normalmente embutido)

    Returns:
        dict com:
            - taxa_ml_pct: percentual da taxa ML
            - taxa_ml_valor: valor da taxa ML em R$
            - frete: custo do frete
            - margem_bruta: lucro bruto (preco - custo - taxa_ml - frete)
            - margem_pct: margem como percentual do preço de venda
            - lucro: alias de margem_bruta
    """
    preco = Decimal(str(preco))
    custo = Decimal(str(custo))
    frete = Decimal(str(frete))

    taxa_pct = calcular_taxa_ml(listing_type)
    taxa_valor = (preco * taxa_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    margem_bruta = preco - custo - taxa_valor - frete
    margem_pct = (
        (margem_bruta / preco * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if preco > 0
        else Decimal("0.00")
    )

    return {
        "taxa_ml_pct": taxa_pct,
        "taxa_ml_valor": taxa_valor,
        "frete": frete,
        "margem_bruta": margem_bruta,
        "margem_pct": margem_pct,
        "lucro": margem_bruta,
    }
