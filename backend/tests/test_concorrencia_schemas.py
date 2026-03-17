"""Tests for concorrencia schemas validation."""
import os
import pytest
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from pydantic import ValidationError
from app.concorrencia.schemas import CompetitorCreate


def test_competitor_create_valid():
    c = CompetitorCreate(listing_id=uuid4(), competitor_mlb_id="MLB12345678")
    assert c.competitor_mlb_id == "MLB12345678"


def test_competitor_create_with_dash():
    c = CompetitorCreate(listing_id=uuid4(), competitor_mlb_id="MLB-12345678")
    assert c.competitor_mlb_id == "MLB-12345678"


def test_competitor_create_invalid_mlb_id():
    with pytest.raises(ValidationError):
        CompetitorCreate(listing_id=uuid4(), competitor_mlb_id="INVALID")


def test_competitor_create_too_short():
    with pytest.raises(ValidationError):
        CompetitorCreate(listing_id=uuid4(), competitor_mlb_id="ML")


def test_competitor_create_missing_listing():
    with pytest.raises(ValidationError):
        CompetitorCreate(competitor_mlb_id="MLB12345678")
