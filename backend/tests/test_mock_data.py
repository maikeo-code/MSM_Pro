"""Tests for vendas/service_mock.py — mock data generators."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.vendas.service_mock import _generate_mock_snapshots


def test_mock_snapshots_default_30_days():
    snaps = _generate_mock_snapshots()
    assert len(snaps) == 30


def test_mock_snapshots_custom_days():
    snaps = _generate_mock_snapshots(days=7)
    assert len(snaps) == 7


def test_mock_snapshots_have_required_fields():
    snaps = _generate_mock_snapshots(days=1)
    required = {"id", "listing_id", "price", "visits", "sales_today",
                "questions", "stock", "conversion_rate", "captured_at",
                "orders_count", "revenue", "avg_selling_price",
                "cancelled_orders", "cancelled_revenue",
                "returns_count", "returns_revenue"}
    assert required.issubset(set(snaps[0].keys()))


def test_mock_snapshots_price_is_decimal():
    snaps = _generate_mock_snapshots(days=1)
    assert isinstance(snaps[0]["price"], Decimal)


def test_mock_snapshots_visits_positive():
    snaps = _generate_mock_snapshots()
    for s in snaps:
        assert s["visits"] >= 400


def test_mock_snapshots_sales_positive():
    snaps = _generate_mock_snapshots()
    for s in snaps:
        assert s["sales_today"] >= 1


def test_mock_snapshots_revenue_consistent():
    snaps = _generate_mock_snapshots(days=1)
    s = snaps[0]
    assert s["revenue"] == float(s["price"]) * s["sales_today"]
