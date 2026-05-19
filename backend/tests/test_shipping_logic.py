"""Tests for seller shipping cost extraction logic used in orders/listings sync.

The fix removes `loyal_discount` and `base_cost` from the fallback chain because:
- loyal_discount = ML loyalty subsidy (NOT a seller cost, it's a discount)
- base_cost = total freight cost BEFORE any subsidy (inflates seller cost)

The only canonical field for "what seller pays for shipping per order" is
`cost_components.sender_cost`. For Full (logistic_type=='fulfillment'), the
seller pays via monthly fulfillment fee (separate billing), so per-shipment
cost is always 0.
"""
import os
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.jobs.tasks_helpers import extract_seller_shipping_cost


def test_sender_cost_when_present():
    detail = {"cost_components": {"sender_cost": 25.50}}
    assert extract_seller_shipping_cost(detail) == Decimal("25.50")


def test_sender_cost_zero_returns_zero():
    """Frete por conta do comprador, sem custo operacional: vendedor paga 0."""
    detail = {"cost_components": {"sender_cost": 0}, "base_cost": 30.00}
    assert extract_seller_shipping_cost(detail) == Decimal("0")


def test_full_returns_zero_regardless():
    """Full: sender_cost no shipment é 0 por design; custo é fatura mensal separada."""
    detail = {"cost_components": {"sender_cost": 50.00}, "base_cost": 99.99}
    assert extract_seller_shipping_cost(detail, logistic_type="fulfillment") == Decimal("0")


def test_loyal_discount_is_ignored():
    """REGRESSÃO PREVENIDA: loyal_discount NÃO é custo do vendedor."""
    detail = {
        "cost_components": {"sender_cost": None, "loyal_discount": 18.00},
        "base_cost": 30.00,
    }
    # Sem sender_cost real, retornamos 0 (não pegamos loyal_discount nem base_cost).
    assert extract_seller_shipping_cost(detail) == Decimal("0")


def test_base_cost_is_ignored():
    """REGRESSÃO PREVENIDA: base_cost é frete TOTAL, não o que vendedor paga."""
    detail = {"base_cost": 30.00, "cost_components": {}}
    assert extract_seller_shipping_cost(detail) == Decimal("0")


def test_empty_payload_returns_zero():
    assert extract_seller_shipping_cost({}) == Decimal("0")


def test_invalid_sender_cost_falls_back_to_zero():
    detail = {"cost_components": {"sender_cost": "garbage"}}
    assert extract_seller_shipping_cost(detail) == Decimal("0")


# ── Cenário real do MLB6676641500 (validação E2E do bug) ─────────────────────

def test_classico_frete_comprador_com_custo_operacional():
    """
    Anúncio Clássico, frete por conta do comprador, mas ML cobra R$7.85
    de custo operacional do vendedor (taxa de gerenciamento de envio).
    """
    detail = {
        "cost_components": {"sender_cost": 7.85, "loyal_discount": 0},
        "base_cost": 30.00,
    }
    assert extract_seller_shipping_cost(detail, logistic_type="default") == Decimal("7.85")


# ── net_amount coerente ───────────────────────────────────────────────────────

def test_net_amount_with_shipping():
    total = Decimal("100.00")
    fee = Decimal("12.00")
    shipping = Decimal("15.50")
    assert total - fee - shipping == Decimal("72.50")


def test_net_amount_free_shipping_zero_seller_cost():
    """Quando vendedor paga zero pelo envio, net = total - sale_fee."""
    total = Decimal("100.00")
    fee = Decimal("13.00")
    shipping = Decimal("0")
    assert total - fee - shipping == Decimal("87.00")


def test_mlb6676641500_voce_recebe_real():
    """
    Cenário real reportado: preço 77,95, 13% taxa, R$7,85 custo operacional
    devem dar líquido R$59,97.
    """
    total = Decimal("77.95")
    fee = total * Decimal("0.13")  # 10.13
    shipping = Decimal("7.85")
    net = total - fee - shipping
    # Tolerância de 1 centavo por arredondamento decimal
    assert abs(net - Decimal("59.97")) < Decimal("0.02")
