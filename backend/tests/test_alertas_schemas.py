"""Tests for alertas schemas validation."""
import os
import pytest
from decimal import Decimal
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from pydantic import ValidationError
from app.alertas.schemas import AlertConfigCreate, AlertConfigUpdate


def test_alert_config_valid():
    a = AlertConfigCreate(
        alert_type="stock_below",
        listing_id=uuid4(),
        threshold=Decimal("10"),
    )
    assert a.channel == "email"


def test_alert_config_threshold_required_for_conversion():
    with pytest.raises(ValidationError, match="threshold"):
        AlertConfigCreate(alert_type="conversion_below", listing_id=uuid4())


def test_alert_config_threshold_required_for_stock():
    with pytest.raises(ValidationError, match="threshold"):
        AlertConfigCreate(alert_type="stock_below", listing_id=uuid4())


def test_alert_config_threshold_required_for_no_sales():
    with pytest.raises(ValidationError, match="threshold"):
        AlertConfigCreate(alert_type="no_sales_days", listing_id=uuid4())


def test_alert_config_threshold_not_required_for_competitor_change():
    a = AlertConfigCreate(
        alert_type="competitor_price_change",
        listing_id=uuid4(),
    )
    assert a.threshold is None


def test_alert_config_requires_listing_or_product():
    with pytest.raises(ValidationError, match="listing_id"):
        AlertConfigCreate(alert_type="stock_below", threshold=Decimal("5"))


def test_alert_config_with_product_id():
    a = AlertConfigCreate(
        alert_type="stock_below",
        product_id=uuid4(),
        threshold=Decimal("5"),
    )
    assert a.listing_id is None


def test_alert_config_webhook_channel():
    a = AlertConfigCreate(
        alert_type="stock_below",
        listing_id=uuid4(),
        threshold=Decimal("10"),
        channel="webhook",
    )
    assert a.channel == "webhook"


def test_alert_config_invalid_channel():
    with pytest.raises(ValidationError):
        AlertConfigCreate(
            alert_type="stock_below",
            listing_id=uuid4(),
            threshold=Decimal("10"),
            channel="sms",
        )


def test_alert_config_invalid_type():
    with pytest.raises(ValidationError):
        AlertConfigCreate(alert_type="invalid_type", listing_id=uuid4())


def test_alert_config_update_partial():
    u = AlertConfigUpdate(threshold=Decimal("20"))
    assert u.channel is None
    assert u.is_active is None


def test_alert_config_update_deactivate():
    u = AlertConfigUpdate(is_active=False)
    assert u.is_active is False
