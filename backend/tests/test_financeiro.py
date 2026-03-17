"""Tests for financeiro service helper functions."""
import os
import pytest
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def test_parse_period_7d():
    from app.financeiro.service import _parse_period
    start, end = _parse_period("7d")
    assert isinstance(start, date)
    assert isinstance(end, date)
    assert (end - start).days == 6  # 7 days inclusive


def test_parse_period_30d():
    from app.financeiro.service import _parse_period
    start, end = _parse_period("30d")
    assert (end - start).days == 29


def test_parse_period_unknown_defaults_30d():
    from app.financeiro.service import _parse_period
    start, end = _parse_period("unknown")
    assert (end - start).days == 29


def test_parse_period_end_is_yesterday():
    from app.financeiro.service import _parse_period
    _, end = _parse_period("7d")
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    assert end == yesterday


def test_period_label():
    from app.financeiro.service import _period_label
    assert _period_label("7d") == "7d"
    assert _period_label("30d") == "30d"


def test_calcular_margem_returns_all_keys():
    from app.financeiro.service import calcular_margem
    result = calcular_margem(
        preco=Decimal("100"), custo=Decimal("50"),
        listing_type="classico",
    )
    expected_keys = {"taxa_ml_pct", "taxa_ml_valor", "frete", "margem_bruta", "margem_pct", "lucro"}
    assert expected_keys.issubset(set(result.keys()))


def test_calcular_margem_string_inputs():
    """Test that string inputs are converted to Decimal correctly."""
    from app.financeiro.service import calcular_margem
    result = calcular_margem(
        preco="199.90",
        custo="80.00",
        listing_type="premium",
        frete="12.50",
    )
    assert isinstance(result["margem_bruta"], Decimal)
    assert result["margem_bruta"] > 0
