"""Tests for vendas/service_health.py — health score calculations."""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.vendas.service_health import _calculate_health_score, calculate_quality_score_quick


class FakeListing:
    def __init__(self, **kwargs):
        defaults = {
            "title": "Produto Teste Com Titulo Grande Para Passar No Check De 60 Caracteres Minimo",
            "thumbnail": "http://img.com/thumb.jpg",
            "listing_type": "premium",
            "status": "active",
            "price": 199.90,
            "sale_price": None,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeProduct:
    def __init__(self, cost=50.0):
        self.cost = cost


def _snap(visits=200, sales=5, stock=50):
    return {"visits": visits, "sales_today": sales, "stock": stock}


def test_health_score_perfect():
    listing = FakeListing(listing_type="full")
    snaps = [_snap(visits=200, sales=10, stock=100)] * 7
    product = FakeProduct(cost=50)
    result = _calculate_health_score(listing, snaps, product, competitor_price=250.0)
    assert result["score"] == 100
    assert result["status"] == "excellent"


def test_health_score_minimal():
    listing = FakeListing(
        title="Short",
        thumbnail=None,
        listing_type="classico",
        status="paused",
        price=0,
    )
    result = _calculate_health_score(listing, [], None)
    assert result["score"] < 20
    assert result["status"] == "critical"


def test_health_score_returns_checks():
    listing = FakeListing()
    result = _calculate_health_score(listing, [_snap()] * 3)
    assert "checks" in result
    assert len(result["checks"]) == 10


def test_health_score_no_competitor_partial_points():
    listing = FakeListing()
    result = _calculate_health_score(listing, [_snap()] * 3)
    price_check = [c for c in result["checks"] if c["item"] == "Preço competitivo"][0]
    assert price_check["points"] == 5  # partial without competitor


def test_health_score_competitor_cheaper_loses_points():
    listing = FakeListing(price=200)
    result = _calculate_health_score(listing, [_snap()] * 3, competitor_price=100.0)
    price_check = [c for c in result["checks"] if c["item"] == "Preço competitivo"][0]
    assert price_check["points"] == 0


def test_health_score_low_conversion():
    listing = FakeListing()
    snaps = [_snap(visits=1000, sales=1, stock=50)] * 7
    result = _calculate_health_score(listing, snaps)
    conv_check = [c for c in result["checks"] if "Conversão" in c["item"]][0]
    assert conv_check["points"] < 10


def test_health_score_zero_stock():
    listing = FakeListing()
    snaps = [_snap(stock=3)] * 3
    result = _calculate_health_score(listing, snaps)
    stock_check = [c for c in result["checks"] if "Estoque" in c["item"]][0]
    assert stock_check["points"] == 0


# ── calculate_quality_score_quick ──

def test_quality_score_quick_full():
    listing = FakeListing(listing_type="full")
    score = calculate_quality_score_quick(listing)
    # title>60=10 + thumb=15 + premium=10 + full=10 + active=5 + price>0=5 = 55
    assert score == 55


def test_quality_score_quick_minimal():
    listing = FakeListing(title="X", thumbnail=None, listing_type="classico", status="paused", price=0)
    score = calculate_quality_score_quick(listing)
    assert score == 0


def test_quality_score_quick_max_100():
    listing = FakeListing(listing_type="full")
    score = calculate_quality_score_quick(listing)
    assert score <= 100
