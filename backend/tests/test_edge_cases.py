"""Edge case tests for various business logic."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


# ── Margin edge cases ──

def test_margem_very_high_price():
    from app.financeiro.service import calcular_margem
    result = calcular_margem(Decimal("99999.99"), Decimal("1000"), "full")
    assert result["margem_bruta"] > 0
    assert result["taxa_ml_valor"] > Decimal("10000")


def test_margem_very_low_price():
    from app.financeiro.service import calcular_margem
    result = calcular_margem(Decimal("0.01"), Decimal("0.01"), "classico")
    assert isinstance(result["margem_bruta"], Decimal)


def test_margem_equal_price_and_cost():
    from app.financeiro.service import calcular_margem
    result = calcular_margem(Decimal("100"), Decimal("100"), "classico")
    assert result["margem_bruta"] < 0  # tax makes it negative


# ── Crypto edge cases ──

def test_encrypt_long_token():
    from app.core.crypto import EncryptedString
    es = EncryptedString(2000)
    long_token = "A" * 1500
    encrypted = es.process_bind_param(long_token, None)
    decrypted = es.process_result_value(encrypted, None)
    assert decrypted == long_token


def test_encrypt_unicode_token():
    from app.core.crypto import EncryptedString
    es = EncryptedString(2000)
    unicode_token = "token-with-ação-üñ-日本語"
    encrypted = es.process_bind_param(unicode_token, None)
    decrypted = es.process_result_value(encrypted, None)
    assert decrypted == unicode_token


# ── Stock projection edge cases ──

def test_stock_projection_single_day():
    from app.vendas.service_calculations import _calculate_stock_projection
    snaps = [{"price": 100, "sales_today": 5, "visits": 200}]
    result = _calculate_stock_projection(100, snaps)
    assert result["velocity_7d"] == 5.0
    assert result["velocity_30d"] == 5.0


def test_stock_projection_varying_sales():
    from app.vendas.service_calculations import _calculate_stock_projection
    snaps = [{"price": 100, "sales_today": i, "visits": 200} for i in range(1, 31)]
    result = _calculate_stock_projection(100, snaps)
    assert result["velocity_30d"] == pytest.approx(15.5, abs=0.1)


# ── Price bands edge cases ──

def test_price_bands_all_same_price():
    from app.vendas.service_calculations import _calculate_price_bands
    snaps = [{"price": Decimal("100"), "sales_today": 5, "visits": 200, "revenue": None}] * 10
    bands = _calculate_price_bands(snaps, Decimal("50"), "classico")
    assert len(bands) == 1
    assert bands[0]["days_count"] == 10


def test_price_bands_low_price_smaller_bands():
    from app.vendas.service_calculations import _calculate_price_bands
    snaps = [
        {"price": Decimal("10"), "sales_today": 5, "visits": 200, "revenue": None},
        {"price": Decimal("20"), "sales_today": 5, "visits": 200, "revenue": None},
    ]
    bands = _calculate_price_bands(snaps, Decimal("5"), "classico")
    assert len(bands) == 2  # R$5 bands for prices < 50


def test_price_bands_high_price_larger_bands():
    from app.vendas.service_calculations import _calculate_price_bands
    snaps = [
        {"price": Decimal("600"), "sales_today": 5, "visits": 200, "revenue": None},
        {"price": Decimal("610"), "sales_today": 5, "visits": 200, "revenue": None},
    ]
    bands = _calculate_price_bands(snaps, Decimal("200"), "premium")
    assert len(bands) == 1  # R$25 bands for prices >= 500, both in same band


# ── Alerts edge cases ──

def test_alerts_all_conditions_at_once():
    from app.vendas.service_calculations import _generate_alerts
    snaps = [{"price": Decimal("100"), "sales_today": 0, "visits": 500}] * 3
    proj = {"days_until_stockout_7d": 2}
    alerts = _generate_alerts(snaps, proj, Decimal("80"), Decimal("100"))
    types = [a["type"] for a in alerts]
    assert "stock_critical" in types
    assert "zero_sales" in types
    assert "competitor_cheaper" in types


# ── JWT edge cases ──

def test_jwt_with_special_chars_in_user_id():
    import jwt as pyjwt
    from app.core.config import settings
    from datetime import datetime, timezone, timedelta

    payload = {
        "sub": "550e8400-e29b-41d4-a716-446655440000",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = pyjwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    decoded = pyjwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert decoded["sub"] == "550e8400-e29b-41d4-a716-446655440000"
