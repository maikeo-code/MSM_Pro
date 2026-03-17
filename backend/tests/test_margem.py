"""Tests for margin calculation logic (calcular_margem, calcular_taxa_ml)."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def test_taxa_ml_classico():
    from app.financeiro.service import calcular_taxa_ml
    assert calcular_taxa_ml("classico") == Decimal("0.115")


def test_taxa_ml_premium():
    from app.financeiro.service import calcular_taxa_ml
    assert calcular_taxa_ml("premium") == Decimal("0.17")


def test_taxa_ml_full():
    from app.financeiro.service import calcular_taxa_ml
    assert calcular_taxa_ml("full") == Decimal("0.17")


def test_taxa_ml_unknown_fallback():
    from app.financeiro.service import calcular_taxa_ml
    assert calcular_taxa_ml("unknown_type") == Decimal("0.16")


def test_taxa_ml_none_fallback():
    from app.financeiro.service import calcular_taxa_ml
    assert calcular_taxa_ml(None) == Decimal("0.16")


def test_taxa_ml_custom_sale_fee():
    from app.financeiro.service import calcular_taxa_ml
    custom = Decimal("0.12")
    assert calcular_taxa_ml("classico", sale_fee_pct=custom) == custom


def test_taxa_ml_zero_sale_fee_uses_table():
    from app.financeiro.service import calcular_taxa_ml
    assert calcular_taxa_ml("classico", sale_fee_pct=Decimal("0")) == Decimal("0.115")


def test_margem_classico():
    from app.financeiro.service import calcular_margem

    result = calcular_margem(
        preco=Decimal("100.00"),
        custo=Decimal("40.00"),
        listing_type="classico",
    )
    # taxa = 100 * 0.115 = 11.50
    # margem = 100 - 40 - 11.50 - 0 = 48.50
    assert result["taxa_ml_valor"] == Decimal("11.50")
    assert result["margem_bruta"] == Decimal("48.50")
    assert result["margem_pct"] == Decimal("48.50")
    assert result["lucro"] == result["margem_bruta"]


def test_margem_premium_with_frete():
    from app.financeiro.service import calcular_margem

    result = calcular_margem(
        preco=Decimal("200.00"),
        custo=Decimal("80.00"),
        listing_type="premium",
        frete=Decimal("15.00"),
    )
    # taxa = 200 * 0.17 = 34.00
    # margem = 200 - 80 - 34 - 15 = 71.00
    assert result["taxa_ml_valor"] == Decimal("34.00")
    assert result["margem_bruta"] == Decimal("71.00")
    assert result["frete"] == Decimal("15.00")


def test_margem_zero_price():
    from app.financeiro.service import calcular_margem

    result = calcular_margem(
        preco=Decimal("0"),
        custo=Decimal("50.00"),
        listing_type="classico",
    )
    assert result["margem_pct"] == Decimal("0.00")


def test_margem_negative_margin():
    from app.financeiro.service import calcular_margem

    result = calcular_margem(
        preco=Decimal("50.00"),
        custo=Decimal("60.00"),
        listing_type="premium",
        frete=Decimal("10.00"),
    )
    # taxa = 50 * 0.17 = 8.50
    # margem = 50 - 60 - 8.50 - 10 = -28.50
    assert result["margem_bruta"] == Decimal("-28.50")
    assert result["margem_pct"] < 0


def test_margem_with_custom_sale_fee():
    from app.financeiro.service import calcular_margem

    result = calcular_margem(
        preco=Decimal("100.00"),
        custo=Decimal("40.00"),
        listing_type="classico",
        sale_fee_pct=Decimal("0.12"),
    )
    # taxa = 100 * 0.12 = 12.00 (custom overrides table)
    assert result["taxa_ml_valor"] == Decimal("12.00")
    assert result["margem_bruta"] == Decimal("48.00")
