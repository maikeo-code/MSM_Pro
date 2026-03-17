"""Tests for produtos schemas validation."""
import os
import pytest
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from pydantic import ValidationError
from app.produtos.schemas import ProductCreate, ProductUpdate


def test_product_create_valid():
    p = ProductCreate(sku="SKU-001", name="Produto Teste", cost=Decimal("29.90"))
    assert p.unit == "un"
    assert p.notes is None


def test_product_create_empty_sku():
    with pytest.raises(ValidationError):
        ProductCreate(sku="", name="Produto", cost=Decimal("10"))


def test_product_create_negative_cost():
    with pytest.raises(ValidationError):
        ProductCreate(sku="SKU-001", name="Produto", cost=Decimal("-5.00"))


def test_product_create_zero_cost():
    p = ProductCreate(sku="SKU-001", name="Produto", cost=Decimal("0"))
    assert p.cost == Decimal("0")


def test_product_create_with_notes():
    p = ProductCreate(sku="SKU-001", name="Produto", cost=Decimal("10"), notes="Nota")
    assert p.notes == "Nota"


def test_product_update_partial():
    u = ProductUpdate(cost=Decimal("39.90"))
    assert u.name is None
    assert u.unit is None


def test_product_update_deactivate():
    u = ProductUpdate(is_active=False)
    assert u.is_active is False


def test_product_update_negative_cost():
    with pytest.raises(ValidationError):
        ProductUpdate(cost=Decimal("-1"))
