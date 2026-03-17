"""Tests for shipping cost extraction logic used in orders sync."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def _extract_shipping_cost(shipment_detail: dict) -> Decimal:
    """Mirror the logic from tasks_orders.py for testing."""
    cost_comps = shipment_detail.get("cost_components", {})
    sender_cost = (
        cost_comps.get("sender_cost")
        or cost_comps.get("loyal_discount")
        or 0
    )
    if not sender_cost:
        sender_cost = shipment_detail.get("base_cost", 0)
    return Decimal(str(sender_cost or 0))


def test_shipping_cost_from_sender_cost():
    detail = {"cost_components": {"sender_cost": 25.50}}
    assert _extract_shipping_cost(detail) == Decimal("25.5")


def test_shipping_cost_from_loyal_discount():
    detail = {"cost_components": {"loyal_discount": 18.00, "sender_cost": None}}
    assert _extract_shipping_cost(detail) == Decimal("18.0")


def test_shipping_cost_from_base_cost():
    detail = {"base_cost": 30.00, "cost_components": {}}
    assert _extract_shipping_cost(detail) == Decimal("30.0")


def test_shipping_cost_no_data():
    detail = {}
    assert _extract_shipping_cost(detail) == Decimal("0")


def test_shipping_cost_zero_sender():
    detail = {"cost_components": {"sender_cost": 0}, "base_cost": 15.00}
    assert _extract_shipping_cost(detail) == Decimal("15.0")


def test_shipping_cost_all_none():
    detail = {"cost_components": {"sender_cost": None, "loyal_discount": None}, "base_cost": None}
    assert _extract_shipping_cost(detail) == Decimal("0")


def test_net_amount_with_shipping():
    total_amount = Decimal("100.00")
    sale_fee = Decimal("12.00")
    shipping_cost = Decimal("15.50")
    net_amount = total_amount - sale_fee - shipping_cost
    assert net_amount == Decimal("72.50")


def test_net_amount_free_shipping():
    total_amount = Decimal("100.00")
    sale_fee = Decimal("17.00")
    shipping_cost = Decimal("0")
    net_amount = total_amount - sale_fee - shipping_cost
    assert net_amount == Decimal("83.00")
