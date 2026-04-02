"""
Tests for price calculations in financeiro/service.py — pure functions, no DB.

Testes focam em:
- calcular_taxa_ml: taxa por tipo de anúncio (classico, premium, full)
- calcular_margem: lucro bruto, margem %, divisão por zero
- Edge cases: preço zero, custo zero, taxa desconhecida
"""
import os
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

import pytest

from app.financeiro.service import calcular_taxa_ml, calcular_margem


# ────────────────────────────────────────────────────────────────────────────
# Testes para calcular_taxa_ml
# ────────────────────────────────────────────────────────────────────────────


class TestCalcularTaxaML:
    """Testes para cálculo da taxa do Mercado Livre."""

    def test_classico_taxa_default(self):
        """Tipo 'classico' → taxa 11% (0.11)."""
        taxa = calcular_taxa_ml("classico")
        assert taxa == Decimal("0.11")

    def test_premium_taxa_default(self):
        """Tipo 'premium' → taxa 16% (0.16)."""
        taxa = calcular_taxa_ml("premium")
        assert taxa == Decimal("0.16")

    def test_full_taxa_default(self):
        """Tipo 'full' → taxa 16% (0.16)."""
        taxa = calcular_taxa_ml("full")
        assert taxa == Decimal("0.16")

    def test_classico_case_insensitive(self):
        """Tipo 'CLASSICO' (maiúsculas) → mesmo que 'classico'."""
        taxa_lower = calcular_taxa_ml("classico")
        taxa_upper = calcular_taxa_ml("CLASSICO")
        taxa_mixed = calcular_taxa_ml("Classico")

        assert taxa_lower == taxa_upper == taxa_mixed == Decimal("0.11")

    def test_unknown_listing_type_fallback_to_16_percent(self):
        """Tipo desconhecido → fallback 16% (0.16)."""
        taxa = calcular_taxa_ml("unknown_type_xyz")
        assert taxa == Decimal("0.16")

    def test_none_listing_type_fallback(self):
        """listing_type=None → fallback 16%."""
        taxa = calcular_taxa_ml(None)
        assert taxa == Decimal("0.16")

    def test_empty_string_listing_type_fallback(self):
        """listing_type='' → fallback 16%."""
        taxa = calcular_taxa_ml("")
        assert taxa == Decimal("0.16")

    def test_sale_fee_pct_overrides_default(self):
        """sale_fee_pct fornecido → usa esse valor em vez da tabela."""
        # Mesmo que listing_type seja classico (11%), se sale_fee_pct=0.12
        taxa = calcular_taxa_ml("classico", sale_fee_pct=Decimal("0.12"))
        assert taxa == Decimal("0.12")

    def test_sale_fee_pct_zero_ignores_override(self):
        """sale_fee_pct=0 → ignora e usa default da tabela."""
        taxa = calcular_taxa_ml("premium", sale_fee_pct=Decimal("0"))
        # 0 é falsy, portanto usa default
        assert taxa == Decimal("0.16")

    def test_sale_fee_pct_none_uses_default(self):
        """sale_fee_pct=None → usa default da tabela."""
        taxa = calcular_taxa_ml("full", sale_fee_pct=None)
        assert taxa == Decimal("0.16")

    def test_sale_fee_pct_negative_uses_default(self):
        """sale_fee_pct negativo → ignora (não faz sentido), usa default."""
        # Depende da implementação; se checar "< 0", ignora
        # Aqui assumimos que negativos são tratados como inválidos
        taxa = calcular_taxa_ml("classico", sale_fee_pct=Decimal("-0.10"))
        # -0.10 < 0, então ignora e usa default
        assert taxa == Decimal("0.11")

    def test_sale_fee_pct_very_high(self):
        """sale_fee_pct muito alta (erro de API) → ainda respeita."""
        taxa = calcular_taxa_ml("classico", sale_fee_pct=Decimal("0.50"))
        assert taxa == Decimal("0.50")

    def test_sale_fee_pct_as_float_converted_to_decimal(self):
        """sale_fee_pct como float deve ser convertido para Decimal."""
        # Se função receber float em vez de Decimal
        taxa = calcular_taxa_ml("classico", sale_fee_pct=0.12)
        # Comparação deve funcionar mesmo se interno converter
        assert taxa == Decimal("0.12") or taxa == 0.12


# ────────────────────────────────────────────────────────────────────────────
# Testes para calcular_margem
# ────────────────────────────────────────────────────────────────────────────


class TestCalcularMargem:
    """Testes para cálculo de margem bruta e lucro."""

    def test_simple_margin_calculation(self):
        """Caso básico: preço 100, custo 40, classico."""
        # Preço: 100
        # Custo: 40
        # Taxa ML 11%: 100 * 0.11 = 11.00
        # Margem bruta: 100 - 40 - 11.00 - 0 (frete) = 49.00
        result = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("40"),
            listing_type="classico",
        )

        assert result["taxa_ml_pct"] == Decimal("0.11")
        assert result["taxa_ml_valor"] == Decimal("11.00")
        assert result["margem_bruta"] == Decimal("49.00")
        assert result["lucro"] == Decimal("49.00")  # alias

    def test_margin_with_frete(self):
        """Margem com custo de frete."""
        # Preço: 100, Custo: 40, Frete: 5
        # Taxa: 11.00, Margem: 100 - 40 - 11.00 - 5 = 44.00
        result = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("40"),
            listing_type="classico",
            frete=Decimal("5"),
        )

        assert result["frete"] == Decimal("5")
        assert result["margem_bruta"] == Decimal("44.00")

    def test_margin_percentage_calculation(self):
        """margem_pct = (margem_bruta / preco) * 100."""
        # Preço: 100, Margem bruta: 49.00
        # Margem %: 49.00 / 100 * 100 = 49.00%
        result = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("40"),
            listing_type="classico",
        )

        assert result["margem_pct"] == Decimal("49.00")

    def test_margin_negative_when_cost_too_high(self):
        """Margem negativa quando custo > preço."""
        # Preço: 50, Custo: 60
        # Margem: 50 - 60 - taxa = negativa
        result = calcular_margem(
            preco=Decimal("50"),
            custo=Decimal("60"),
            listing_type="classico",
        )

        assert result["margem_bruta"] < 0
        assert result["margem_pct"] < 0

    def test_margin_zero_when_break_even(self):
        """Margem zero quando preço = custo + taxa."""
        # Preço: 44.94, Custo: 40
        # Taxa classico 11%: 44.94 * 0.11 = 4.94
        # Margem: 44.94 - 40 - 4.94 = 0.00 (arredondado próximo a zero)
        result = calcular_margem(
            preco=Decimal("44.94"),
            custo=Decimal("40"),
            listing_type="classico",
        )

        # Será muito próximo a zero (pequeno resto de arredondamento)
        assert result["margem_bruta"] <= Decimal("0.10")

    def test_premium_higher_tax_lower_margin(self):
        """Premium (16%) tem taxa maior que classico (11%)."""
        # Mesmo preço e custo
        result_classico = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("40"),
            listing_type="classico",
        )

        result_premium = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("40"),
            listing_type="premium",
        )

        # Premium tem mais taxa, então menos margem
        assert result_premium["taxa_ml_valor"] > result_classico["taxa_ml_valor"]
        assert result_premium["margem_bruta"] < result_classico["margem_bruta"]

    def test_sale_fee_pct_override(self):
        """sale_fee_pct real (da API) sobrescreve tabela."""
        # API retorna taxa real de 12% para este anúncio
        result = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("40"),
            listing_type="classico",
            sale_fee_pct=Decimal("0.12"),
        )

        assert result["taxa_ml_pct"] == Decimal("0.12")
        assert result["taxa_ml_valor"] == Decimal("12.00")
        assert result["margem_bruta"] == Decimal("48.00")

    def test_margin_with_all_costs(self):
        """Margem com todos os custos: taxa + frete."""
        result = calcular_margem(
            preco=Decimal("200"),
            custo=Decimal("80"),
            listing_type="premium",
            frete=Decimal("15"),
            sale_fee_pct=Decimal("0.15"),
        )

        # Taxa: 200 * 0.15 = 30
        # Margem: 200 - 80 - 30 - 15 = 75
        assert result["taxa_ml_valor"] == Decimal("30.00")
        assert result["margem_bruta"] == Decimal("75.00")


# ────────────────────────────────────────────────────────────────────────────
# Testes para Edge Cases — Preço Zero
# ────────────────────────────────────────────────────────────────────────────


class TestMargemPriceZero:
    """Testes para casos com preço zero."""

    def test_price_zero_returns_zero_margin(self):
        """Preço zero → margem zero (proteção contra divisão por zero)."""
        result = calcular_margem(
            preco=Decimal("0"),
            custo=Decimal("40"),
            listing_type="classico",
        )

        assert result["taxa_ml_pct"] == Decimal("0.11")
        assert result["taxa_ml_valor"] == Decimal("0.00")  # 0 * taxa = 0
        assert result["margem_bruta"] == Decimal("-40.00")  # 0 - 40 - 0
        assert result["margem_pct"] == Decimal("0.00")  # proteção: preco > 0

    def test_price_zero_margem_pct_protected(self):
        """margem_pct com preço zero não gera erro (retorna 0.00)."""
        result = calcular_margem(
            preco=Decimal("0"),
            custo=Decimal("10"),
            listing_type="classico",
        )

        # Não deve lançar ZeroDivisionError
        assert result["margem_pct"] == Decimal("0.00")


# ────────────────────────────────────────────────────────────────────────────
# Testes para Edge Cases — Custo Zero
# ────────────────────────────────────────────────────────────────────────────


class TestMargemCostZero:
    """Testes para casos com custo zero (produto virtual ou markup puro)."""

    def test_cost_zero_margin_equals_price_minus_tax_and_frete(self):
        """Custo zero → margem = preço - taxa - frete."""
        result = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("0"),
            listing_type="classico",
        )

        # Margem: 100 - 0 - 11.00 = 89.00
        assert result["margem_bruta"] == Decimal("89.00")
        assert result["margem_pct"] == Decimal("89.00")

    def test_cost_zero_with_frete(self):
        """Custo zero mas com frete → frete reduz margem."""
        result = calcular_margem(
            preco=Decimal("100"),
            custo=Decimal("0"),
            listing_type="classico",
            frete=Decimal("10"),
        )

        # Margem: 100 - 0 - 11.00 - 10 = 79.00
        assert result["margem_bruta"] == Decimal("79.00")


# ────────────────────────────────────────────────────────────────────────────
# Testes para Edge Cases — Valores Muito Grandes
# ────────────────────────────────────────────────────────────────────────────


class TestMargemLargeValues:
    """Testes para valores muito grandes (overflow protection)."""

    def test_very_high_price(self):
        """Preço muito alto (ex: eletroeletrônico caro)."""
        result = calcular_margem(
            preco=Decimal("50000"),
            custo=Decimal("30000"),
            listing_type="full",
        )

        # Taxa 16%: 50000 * 0.16 = 8000
        # Margem: 50000 - 30000 - 8000 = 12000
        assert result["taxa_ml_valor"] == Decimal("8000.00")
        assert result["margem_bruta"] == Decimal("12000.00")

    def test_very_high_cost(self):
        """Custo muito alto (produto importado)."""
        result = calcular_margem(
            preco=Decimal("10000"),
            custo=Decimal("9500"),
            listing_type="classico",
        )

        # Taxa: 10000 * 0.11 = 1100
        # Margem: 10000 - 9500 - 1100 = -600 (prejuízo)
        assert result["margem_bruta"] == Decimal("-600.00")
        assert result["margem_pct"] == Decimal("-6.00")


# ────────────────────────────────────────────────────────────────────────────
# Testes para Edge Cases — Valores Muito Pequenos
# ────────────────────────────────────────────────────────────────────────────


class TestMargemSmallValues:
    """Testes para valores muito pequenos (centavos)."""

    def test_very_small_price(self):
        """Preço muito pequeno (ex: item barato)."""
        result = calcular_margem(
            preco=Decimal("1.00"),
            custo=Decimal("0.50"),
            listing_type="classico",
        )

        # Taxa: 1.00 * 0.11 = 0.11
        # Margem: 1.00 - 0.50 - 0.11 = 0.39
        assert result["taxa_ml_valor"] == Decimal("0.11")
        # Margem será aproximada
        assert Decimal("0.38") <= result["margem_bruta"] <= Decimal("0.40")

    def test_fractional_prices_and_costs(self):
        """Preços e custos com frações (centavos)."""
        result = calcular_margem(
            preco=Decimal("99.99"),
            custo=Decimal("45.50"),
            listing_type="premium",
            frete=Decimal("8.75"),
        )

        # Taxa 16%: 99.99 * 0.16 = 15.9984 (arredondado para 16.00)
        # Margem: 99.99 - 45.50 - 16.00 - 8.75 = 29.74
        assert result["margem_bruta"] == Decimal("29.74")


# ────────────────────────────────────────────────────────────────────────────
# Testes para Arredondamento
# ────────────────────────────────────────────────────────────────────────────


class TestMargemRounding:
    """Testes para comportamento de arredondamento."""

    def test_taxa_valor_always_two_decimal_places(self):
        """taxa_ml_valor sempre com 2 casas decimais."""
        result = calcular_margem(
            preco=Decimal("10.33"),
            custo=Decimal("5"),
            listing_type="classico",
        )

        # Taxa: 10.33 * 0.11 = 1.1363... deve arredondar para 1.14
        taxa_str = str(result["taxa_ml_valor"])
        decimal_places = taxa_str.split(".")[-1] if "." in taxa_str else "0"
        assert len(decimal_places) <= 2

    def test_margem_pct_always_two_decimal_places(self):
        """margem_pct sempre com 2 casas decimais."""
        result = calcular_margem(
            preco=Decimal("77.77"),
            custo=Decimal("33.33"),
            listing_type="premium",
        )

        margem_pct_str = str(result["margem_pct"])
        decimal_places = margem_pct_str.split(".")[-1] if "." in margem_pct_str else "0"
        assert len(decimal_places) <= 2

    def test_rounding_half_up_behavior(self):
        """Arredondamento usa ROUND_HALF_UP (0.5 sobe)."""
        # 10.005 * 0.11 = 1.10055 → deve arredondar para 1.10
        result = calcular_margem(
            preco=Decimal("10.005"),
            custo=Decimal("5"),
            listing_type="classico",
        )

        # Verificar que o arredondamento foi aplicado
        taxa_valor = result["taxa_ml_valor"]
        assert taxa_valor == Decimal("1.10")


# ────────────────────────────────────────────────────────────────────────────
# Testes de Integração (múltiplos cálculos)
# ────────────────────────────────────────────────────────────────────────────


class TestMargemIntegration:
    """Testes de integração com múltiplos cenários."""

    def test_compare_listing_types(self):
        """Comparar margem entre tipos de anúncio."""
        scenarios = {
            "classico": calcular_margem(Decimal("100"), Decimal("40"), "classico"),
            "premium": calcular_margem(Decimal("100"), Decimal("40"), "premium"),
            "full": calcular_margem(Decimal("100"), Decimal("40"), "full"),
        }

        # Premium e full têm mesma taxa (16%)
        assert scenarios["premium"]["taxa_ml_valor"] == scenarios["full"]["taxa_ml_valor"]

        # Classico é mais vantajoso (menor taxa)
        assert scenarios["classico"]["margem_bruta"] > scenarios["premium"]["margem_bruta"]

    def test_scalable_cost_percentage_effects(self):
        """Testar efeito de diferentes custos em % do preço."""
        price = Decimal("100")

        costs = [
            (Decimal("10"), "10%"),
            (Decimal("30"), "30%"),
            (Decimal("50"), "50%"),
            (Decimal("80"), "80%"),
        ]

        results = []
        for cost, label in costs:
            result = calcular_margem(price, cost, "classico")
            results.append((label, result["margem_pct"]))

        # Quanto maior o custo, menor a margem
        margins = [m for _, m in results]
        assert margins == sorted(margins, reverse=True)
