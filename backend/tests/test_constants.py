"""Tests for core constants — ensure values are sane."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.core.constants import (
    ML_FEES, ML_FEES_FLOAT, ML_FEE_DEFAULT,
    ML_PAGINATION_LIMIT,
    HEALTH_TITLE_MIN_LEN, HEALTH_MIN_CONVERSION_PCT,
    HEALTH_MIN_STOCK, STOCK_CRITICAL_DAYS, STOCK_WARNING_DAYS,
    STOCK_EXCESS_DAYS,
)


def test_ml_fees_all_types_present():
    for lt in ("classico", "premium", "full"):
        assert lt in ML_FEES
        assert lt in ML_FEES_FLOAT


def test_ml_fees_values_match():
    for lt in ML_FEES:
        assert abs(float(ML_FEES[lt]) - ML_FEES_FLOAT[lt]) < 0.001


def test_ml_fees_range():
    for lt, fee in ML_FEES.items():
        assert Decimal("0.05") < fee < Decimal("0.30"), f"{lt} fee out of range"


def test_ml_fee_default():
    assert ML_FEE_DEFAULT == Decimal("0.16")


def test_pagination_limit():
    assert ML_PAGINATION_LIMIT == 50


def test_health_thresholds_make_sense():
    assert HEALTH_TITLE_MIN_LEN > 30
    assert 1 <= HEALTH_MIN_CONVERSION_PCT <= 10
    assert HEALTH_MIN_STOCK > 0


def test_stock_thresholds_ordered():
    assert STOCK_CRITICAL_DAYS < STOCK_WARNING_DAYS < STOCK_EXCESS_DAYS
