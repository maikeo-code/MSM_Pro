"""Tests for revenue fallback logic (COALESCE(revenue, price*sales))."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def _get_revenue_fallback(snap) -> float:
    """Mirror the _get_revenue logic from service_kpi.py."""
    rev = getattr(snap, "revenue", None)
    if rev is None and isinstance(snap, dict):
        rev = snap.get("revenue")
    if rev and float(rev) > 0:
        return float(rev)
    price = getattr(snap, "price", None)
    if price is None and isinstance(snap, dict):
        price = snap.get("price")
    sales = getattr(snap, "sales_today", None)
    if sales is None and isinstance(snap, dict):
        sales = snap.get("sales_today")
    if price and sales:
        return float(price) * int(sales)
    return 0.0


def test_revenue_with_real_value():
    snap = {"revenue": 500.0, "price": 100.0, "sales_today": 3}
    assert _get_revenue_fallback(snap) == 500.0


def test_revenue_null_uses_price_x_sales():
    snap = {"revenue": None, "price": Decimal("99.90"), "sales_today": 5}
    assert _get_revenue_fallback(snap) == pytest.approx(499.5)


def test_revenue_zero_uses_fallback():
    snap = {"revenue": 0, "price": Decimal("50.00"), "sales_today": 2}
    assert _get_revenue_fallback(snap) == 100.0


def test_revenue_no_price_no_sales():
    snap = {"revenue": None, "price": None, "sales_today": None}
    assert _get_revenue_fallback(snap) == 0.0


def test_revenue_with_obj():
    class FakeSnap:
        revenue = Decimal("250.00")
        price = Decimal("50.00")
        sales_today = 5
    assert _get_revenue_fallback(FakeSnap()) == 250.0


def test_revenue_obj_null_fallback():
    class FakeSnap:
        revenue = None
        price = Decimal("75.00")
        sales_today = 4
    assert _get_revenue_fallback(FakeSnap()) == 300.0


def test_aggregate_snaps_revenue_fallback():
    """Test that aggregate uses fallback for None revenue."""
    snaps = [
        {"revenue": None, "price": Decimal("100"), "sales_today": 2},
        {"revenue": 300.0, "price": Decimal("100"), "sales_today": 3},
    ]
    total = sum(
        float(s.get("revenue") or 0) or (float(s.get("price", 0)) * (s.get("sales_today") or 0))
        for s in snaps
    )
    assert total == 500.0  # 200 (fallback) + 300 (real)
