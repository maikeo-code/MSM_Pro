"""Tests for ads schemas validation."""
import os
import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import date, datetime

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.ads.schemas import AdsDashboardOut, AdCampaignOut


def test_ads_dashboard_empty():
    d = AdsDashboardOut(
        total_spend=Decimal("0"),
        total_revenue=Decimal("0"),
        total_clicks=0,
        total_impressions=0,
        roas_geral=None,
        acos_geral=None,
        campaigns=[],
    )
    assert d.roas_geral is None
    assert len(d.campaigns) == 0


def test_campaign_out():
    c = AdCampaignOut(
        id=uuid4(),
        ml_account_id=uuid4(),
        campaign_id="CAMP-123",
        name="Campanha Teste",
        status="active",
        daily_budget=Decimal("50.00"),
        roas_target=Decimal("3.5"),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert c.name == "Campanha Teste"


def test_ads_dashboard_with_campaigns():
    camp = AdCampaignOut(
        id=uuid4(),
        ml_account_id=uuid4(),
        campaign_id="CAMP-456",
        name="Test",
        status="paused",
        daily_budget=Decimal("100"),
        roas_target=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    d = AdsDashboardOut(
        total_spend=Decimal("500"),
        total_revenue=Decimal("2000"),
        total_clicks=150,
        total_impressions=10000,
        roas_geral=Decimal("4.0"),
        acos_geral=Decimal("25.0"),
        campaigns=[camp],
    )
    assert d.roas_geral == Decimal("4.0")
    assert len(d.campaigns) == 1
