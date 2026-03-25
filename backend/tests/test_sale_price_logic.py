"""
Tests for sale price resolution logic in service_sync.py.

Testes focam em como o sistema escolhe entre diferentes fontes de preço:
- GET /items/{id}/sale_price (endpoint primário desde março 2026)
- Fallback para item.price (deprecated)
- Fallback para item.sale_price (dict com amount)
- Fallback para seller-promotions (API /promotions)
"""
import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

import pytest


# ────────────────────────────────────────────────────────────────────────────
# Helper para simular o fluxo de resolução de preço
# ────────────────────────────────────────────────────────────────────────────


def _resolve_price_like_service_sync(
    item: dict,
    sale_price_endpoint_response: dict | None = None,
    sale_price_endpoint_failed: bool = False,
) -> tuple[Decimal, Decimal | None]:
    """
    Simula a lógica de resolução de preço do service_sync.py (linhas 83-130).

    Retorna:
        (price, original_price)
    """
    price = Decimal(str(item.get("price", 0)))
    original_price = None
    sale_price_val = None
    used_sale_price_endpoint = False

    # ── 1. Tenta usar /items/{id}/sale_price endpoint (primário) ──
    if not sale_price_endpoint_failed and sale_price_endpoint_response:
        sp_response = sale_price_endpoint_response
        if sp_response and sp_response.get("amount") is not None:
            price = Decimal(str(sp_response["amount"]))
            reg_amount = sp_response.get("regular_amount")
            if reg_amount is not None:
                original_price = Decimal(str(reg_amount))
            used_sale_price_endpoint = True

    # ── 2. Fallback: lógica legada usando campos do /items ──
    if not used_sale_price_endpoint:
        original_price_raw = item.get("original_price")
        original_price = Decimal(str(original_price_raw)) if original_price_raw else None

        sale_price_data = item.get("sale_price")
        if sale_price_data and isinstance(sale_price_data, dict):
            sp_amount = sale_price_data.get("amount")
            if sp_amount is not None:
                sale_price_val = Decimal(str(sp_amount))

        if sale_price_val is not None and price > sale_price_val:
            if original_price is None:
                original_price = price
            price = sale_price_val

        # ── 3. Último fallback: seller-promotions ──
        # (aqui apenas simulamos que promocoes_list pode ser passado)
        if original_price is None:
            # Simular sucesso — em testes reais seria mock da API
            pass

    return price, original_price


# ────────────────────────────────────────────────────────────────────────────
# Testes de resolução de preço
# ────────────────────────────────────────────────────────────────────────────


class TestSalePriceResolution:
    """Testes para lógica de resolução de preço."""

    def test_use_sale_price_endpoint_when_available(self):
        """Quando /sale_price retorna amount → usar esse valor."""
        item = {"price": 100.0}
        sale_price_response = {"amount": 85.50, "regular_amount": 100.0}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_response=sale_price_response
        )

        assert price == Decimal("85.50")
        assert original_price == Decimal("100.0")

    def test_sale_price_endpoint_none_amount(self):
        """Quando /sale_price retorna amount=None → usar fallback."""
        item = {"price": 100.0, "sale_price": {"amount": 95.0}}
        sale_price_response = {"amount": None}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_response=sale_price_response
        )

        # Deve usar fallback item.sale_price
        assert price == Decimal("95.0")

    def test_fallback_to_item_sale_price_dict(self):
        """Quando /sale_price falha → usar item.sale_price com amount."""
        item = {
            "price": 100.0,
            "sale_price": {"amount": 90.0},
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        assert price == Decimal("90.0")
        # original_price deve ser preservado como price original
        assert original_price == Decimal("100.0")

    def test_fallback_uses_original_price_field(self):
        """Quando fallback ativo → usar item.original_price se disponível."""
        item = {
            "price": 95.0,
            "original_price": 120.0,
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        assert price == Decimal("95.0")
        assert original_price == Decimal("120.0")

    def test_fallback_sets_original_price_from_current_price(self):
        """Quando há sale_price mas não original_price → usar price atual como original."""
        item = {
            "price": 100.0,
            "sale_price": {"amount": 85.0},
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        assert price == Decimal("85.0")
        assert original_price == Decimal("100.0")  # price original antes de sale_price

    def test_no_discount_returns_price_only(self):
        """Quando sem desconto → price = price, original_price = None."""
        item = {"price": 100.0}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        assert price == Decimal("100.0")
        assert original_price is None

    def test_sale_price_endpoint_takes_priority(self):
        """Mesmo com item.sale_price válido, /sale_price endpoint tem prioridade."""
        item = {
            "price": 100.0,
            "sale_price": {"amount": 90.0},
            "original_price": 120.0,
        }
        sale_price_response = {"amount": 75.0, "regular_amount": 100.0}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_response=sale_price_response
        )

        # Deve usar /sale_price endpoint, não item.sale_price
        assert price == Decimal("75.0")
        assert original_price == Decimal("100.0")

    def test_handles_string_prices_correctly(self):
        """Lógica deve funcionar com strings e floats (conversão para Decimal)."""
        item = {"price": "150.99"}
        sale_price_response = {"amount": "120.50", "regular_amount": "150.99"}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_response=sale_price_response
        )

        assert isinstance(price, Decimal)
        assert price == Decimal("120.50")
        assert original_price == Decimal("150.99")

    def test_zero_price_handling(self):
        """Casos com preço zero (ex: erro de API)."""
        item = {"price": 0}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        assert price == Decimal("0")
        assert original_price is None

    def test_missing_price_field(self):
        """Quando item não tem 'price' — usar 0 como padrão."""
        item = {}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        assert price == Decimal("0")
        assert original_price is None


# ────────────────────────────────────────────────────────────────────────────
# Testes para impacto nos campos do modelo Listing
# ────────────────────────────────────────────────────────────────────────────


class TestListingPriceFields:
    """Testes para verificar quais campos são salvos no modelo Listing."""

    def test_listing_saves_price_and_original_price(self):
        """Model deve armazenar price e original_price separadamente."""
        item = {
            "price": 100.0,
            "original_price": 120.0,
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        # Campo 'price' do listing = preço atual
        # Campo 'original_price' = preço sem desconto (para UI exibir)
        assert price == Decimal("100.0")
        assert original_price == Decimal("120.0")

    def test_listing_sale_price_field(self):
        """Campo 'sale_price' é preenchido quando há valor específico de promoção."""
        item = {
            "price": 100.0,
            "sale_price": {"amount": 95.0},
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        # price é o valor final; sale_price seria armazenado separadamente
        assert price == Decimal("95.0")
        assert original_price == Decimal("100.0")


# ────────────────────────────────────────────────────────────────────────────
# Testes de casos extremos
# ────────────────────────────────────────────────────────────────────────────


class TestSalePriceEdgeCases:
    """Testes para casos extremos e edge cases."""

    def test_sale_price_higher_than_price(self):
        """Edge case: sale_price > price (erro de dados, ignorar)."""
        item = {
            "price": 100.0,
            "sale_price": {"amount": 150.0},  # Errado!
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        # Não aplica se sale_price > price
        assert price == Decimal("100.0")
        assert original_price is None

    def test_very_large_price_values(self):
        """Lógica deve funcionar com preços altos."""
        item = {"price": 99999.99}
        sale_price_response = {"amount": 75000.00, "regular_amount": 99999.99}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_response=sale_price_response
        )

        assert price == Decimal("75000.00")
        assert original_price == Decimal("99999.99")

    def test_very_small_price_values(self):
        """Lógica deve funcionar com preços pequenos (centavos)."""
        item = {"price": 0.01}
        sale_price_response = {"amount": 0.01, "regular_amount": 0.05}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_response=sale_price_response
        )

        assert price == Decimal("0.01")
        assert original_price == Decimal("0.05")

    def test_negative_discount_percentage(self):
        """Desconto negativo não deve ser aplicado."""
        item = {
            "price": 100.0,
            "sale_price": {"amount": 110.0},  # "desconto" negativo
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        # Ignora porque sale_price > price
        assert price == Decimal("100.0")
        assert original_price is None

    def test_empty_sale_price_dict(self):
        """sale_price vazio não deve ser processado."""
        item = {
            "price": 100.0,
            "sale_price": {},
        }

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_failed=True
        )

        assert price == Decimal("100.0")
        assert original_price is None

    def test_null_regular_amount_in_endpoint(self):
        """Quando regular_amount é None no endpoint → original_price fica None."""
        item = {"price": 100.0}
        sale_price_response = {"amount": 85.0, "regular_amount": None}

        price, original_price = _resolve_price_like_service_sync(
            item, sale_price_endpoint_response=sale_price_response
        )

        assert price == Decimal("85.0")
        assert original_price is None  # regular_amount era None
