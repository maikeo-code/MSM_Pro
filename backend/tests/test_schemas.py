"""Tests for Pydantic schema validation."""
import os
import pytest
from decimal import Decimal
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def test_listing_create_valid():
    from app.vendas.schemas import ListingCreate

    listing = ListingCreate(
        ml_account_id=uuid4(),
        mlb_id="MLB12345678",
        title="Produto Teste",
        price=Decimal("199.90"),
    )
    assert listing.listing_type == "classico"
    assert listing.product_id is None


def test_listing_create_with_dash():
    from app.vendas.schemas import ListingCreate

    listing = ListingCreate(
        ml_account_id=uuid4(),
        mlb_id="MLB-12345678",
        title="Produto",
        price=Decimal("99.99"),
    )
    assert listing.mlb_id == "MLB-12345678"


def test_listing_create_invalid_mlb_id():
    from app.vendas.schemas import ListingCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ListingCreate(
            ml_account_id=uuid4(),
            mlb_id="INVALID",
            title="Produto",
            price=Decimal("99.99"),
        )


def test_listing_create_negative_price():
    from app.vendas.schemas import ListingCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ListingCreate(
            ml_account_id=uuid4(),
            mlb_id="MLB12345678",
            title="Produto",
            price=Decimal("-10.00"),
        )


def test_listing_create_invalid_listing_type():
    from app.vendas.schemas import ListingCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ListingCreate(
            ml_account_id=uuid4(),
            mlb_id="MLB12345678",
            title="Produto",
            price=Decimal("99.99"),
            listing_type="invalido",
        )


def test_listing_create_all_types():
    from app.vendas.schemas import ListingCreate

    for lt in ["classico", "premium", "full"]:
        listing = ListingCreate(
            ml_account_id=uuid4(),
            mlb_id="MLB12345678",
            title="Produto",
            price=Decimal("99.99"),
            listing_type=lt,
        )
        assert listing.listing_type == lt
