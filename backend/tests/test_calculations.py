"""Tests for vendas/service_calculations.py — pure functions, no DB."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.vendas.service_calculations import (
    _calculate_price_bands,
    _calculate_stock_projection,
    _generate_alerts,
)


# ── _calculate_price_bands ──

def _make_snap(price, sales, visits, revenue=None):
    return {"price": Decimal(str(price)), "sales_today": sales, "visits": visits, "revenue": revenue}


def test_price_bands_empty_snapshots():
    assert _calculate_price_bands([], Decimal("50"), "classico") == []


def test_price_bands_single_snapshot():
    snaps = [_make_snap(100, 5, 200)]
    bands = _calculate_price_bands(snaps, Decimal("40"), "classico")
    assert len(bands) == 1
    assert bands[0]["days_count"] == 1
    assert bands[0]["avg_sales_per_day"] == 5.0


def test_price_bands_marks_optimal():
    snaps = [
        _make_snap(100, 10, 500),  # high sales
        _make_snap(200, 2, 300),   # low sales
    ]
    bands = _calculate_price_bands(snaps, Decimal("40"), "classico")
    optimal_count = sum(1 for b in bands if b["is_optimal"])
    assert optimal_count == 1


def test_price_bands_sorted_by_price():
    snaps = [
        _make_snap(300, 3, 100),
        _make_snap(100, 5, 200),
        _make_snap(200, 4, 150),
    ]
    bands = _calculate_price_bands(snaps, Decimal("50"), "premium")
    labels = [b["price_range_label"] for b in bands]
    # Should be sorted ascending
    assert labels == sorted(labels)


def test_price_bands_uses_revenue_when_available():
    snaps = [_make_snap(100, 5, 200, revenue=600)]
    bands = _calculate_price_bands(snaps, Decimal("40"), "classico")
    assert bands[0]["total_revenue"] == 600.0


def test_price_bands_estimates_revenue_when_missing():
    snaps = [_make_snap(100, 5, 200, revenue=None)]
    bands = _calculate_price_bands(snaps, Decimal("40"), "classico")
    assert bands[0]["total_revenue"] == 500.0  # 100 * 5


# ── _calculate_stock_projection ──

def test_stock_projection_empty_snapshots():
    result = _calculate_stock_projection(100, [])
    assert result["status"] == "ok"
    assert result["days_until_stockout_7d"] is None


def test_stock_projection_zero_stock():
    result = _calculate_stock_projection(0, [_make_snap(100, 5, 200)])
    assert result["status"] == "ok"
    assert result["available"] == 0


def test_stock_projection_critical():
    snaps = [_make_snap(100, 10, 200)] * 7  # 10 sales/day
    result = _calculate_stock_projection(50, snaps)
    assert result["status"] == "critical"  # 50/10 = 5 days < 7


def test_stock_projection_warning():
    snaps = [_make_snap(100, 5, 200)] * 7  # 5 sales/day
    result = _calculate_stock_projection(50, snaps)
    assert result["status"] == "warning"  # 50/5 = 10 days (7-14)


def test_stock_projection_ok():
    snaps = [_make_snap(100, 2, 200)] * 7  # 2 sales/day
    result = _calculate_stock_projection(50, snaps)
    assert result["status"] == "ok"  # 50/2 = 25 days


def test_stock_projection_excess():
    snaps = [_make_snap(100, 1, 200)] * 7  # 1 sale/day
    result = _calculate_stock_projection(100, snaps)
    assert result["status"] == "excess"  # 100/1 = 100 days > 60


def test_stock_projection_zero_sales():
    snaps = [_make_snap(100, 0, 200)] * 7
    result = _calculate_stock_projection(100, snaps)
    assert result["days_until_stockout_7d"] is None


def test_stock_projection_velocity_calculated():
    snaps = [_make_snap(100, 3, 200)] * 10
    result = _calculate_stock_projection(100, snaps)
    assert result["velocity_7d"] == 3.0
    assert result["velocity_30d"] == 3.0


# ── _generate_alerts ──

def test_alerts_empty_snapshots():
    proj = {"days_until_stockout_7d": None}
    alerts = _generate_alerts([], proj, None, Decimal("100"))
    assert alerts == []


def test_alerts_stock_critical():
    snaps = [_make_snap(100, 5, 200)] * 3
    proj = {"days_until_stockout_7d": 3}
    alerts = _generate_alerts(snaps, proj, None, Decimal("100"))
    types = [a["type"] for a in alerts]
    assert "stock_critical" in types


def test_alerts_stock_excess():
    snaps = [_make_snap(100, 5, 200)] * 3
    proj = {"days_until_stockout_7d": 90}
    alerts = _generate_alerts(snaps, proj, None, Decimal("100"))
    types = [a["type"] for a in alerts]
    assert "stock_excess" in types


def test_alerts_zero_sales():
    snaps = [_make_snap(100, 0, 200)] * 3
    proj = {"days_until_stockout_7d": None}
    alerts = _generate_alerts(snaps, proj, None, Decimal("100"))
    types = [a["type"] for a in alerts]
    assert "zero_sales" in types


def test_alerts_low_conversion():
    # 1000 visits, 2 sales = 0.2% conversion
    snaps = [_make_snap(100, 2, 1000)] * 3
    proj = {"days_until_stockout_7d": 30}
    alerts = _generate_alerts(snaps, proj, None, Decimal("100"))
    types = [a["type"] for a in alerts]
    assert "low_conversion" in types


def test_alerts_competitor_cheaper():
    snaps = [_make_snap(100, 5, 200)] * 3
    proj = {"days_until_stockout_7d": 30}
    alerts = _generate_alerts(snaps, proj, Decimal("80"), Decimal("100"))
    types = [a["type"] for a in alerts]
    assert "competitor_cheaper" in types


def test_alerts_no_competitor_no_alert():
    snaps = [_make_snap(100, 5, 200)] * 3
    proj = {"days_until_stockout_7d": 30}
    alerts = _generate_alerts(snaps, proj, None, Decimal("100"))
    types = [a["type"] for a in alerts]
    assert "competitor_cheaper" not in types
