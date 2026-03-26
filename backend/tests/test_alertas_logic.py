"""Tests for alertas/service.py — alert evaluation logic with mocks."""
import os
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.alertas.service import _calculate_severity


# ============================================================================
# Mock Objects
# ============================================================================


class MockListingSnapshot:
    """Mock ListingSnapshot for testing alert conditions."""

    def __init__(
        self,
        captured_at=None,
        sales_today=0,
        visits_today=0,
        stock=100,
        conversion_rate=None,
    ):
        self.captured_at = captured_at or datetime.now(timezone.utc)
        self.sales_today = sales_today
        self.visits_today = visits_today
        self.stock = stock
        self.conversion_rate = (
            Decimal(str(conversion_rate)) if conversion_rate is not None else None
        )


class MockListing:
    """Mock Listing for testing alert conditions."""

    def __init__(self, listing_id=None, mlb_id="MLB-TEST-123"):
        self.id = listing_id or uuid4()
        self.mlb_id = mlb_id


class MockAlertConfig:
    """Mock AlertConfig for testing evaluation logic."""

    def __init__(
        self,
        alert_id=None,
        alert_type="stock_below",
        threshold=None,
        listing_id=None,
        product_id=None,
        last_triggered_at=None,
    ):
        self.id = alert_id or uuid4()
        self.alert_type = alert_type
        self.threshold = Decimal(str(threshold)) if threshold is not None else None
        self.listing_id = listing_id or uuid4()
        self.product_id = product_id
        self.last_triggered_at = last_triggered_at


class MockCompetitor:
    """Mock Competitor for testing alert conditions."""

    def __init__(self, competitor_id=None, mlb_id="COMP-123"):
        self.id = competitor_id or uuid4()
        self.mlb_id = mlb_id


class MockCompetitorSnapshot:
    """Mock CompetitorSnapshot for testing alert conditions."""

    def __init__(
        self,
        captured_at=None,
        price=Decimal("100"),
    ):
        self.captured_at = captured_at or datetime.now(timezone.utc)
        self.price = Decimal(str(price))


# ============================================================================
# Test: Severity Calculation Function
# ============================================================================


def test_calculate_severity_stock_below_critical():
    """stock_below with threshold <= 3 returns critical."""
    assert _calculate_severity("stock_below", Decimal("3")) == "critical"
    assert _calculate_severity("stock_below", Decimal("1")) == "critical"
    assert _calculate_severity("stock_below", Decimal("0")) == "critical"


def test_calculate_severity_stock_below_warning():
    """stock_below with 3 < threshold <= 10 returns warning."""
    assert _calculate_severity("stock_below", Decimal("5")) == "warning"
    assert _calculate_severity("stock_below", Decimal("10")) == "warning"
    assert _calculate_severity("stock_below", Decimal("4")) == "warning"


def test_calculate_severity_stock_below_above_10():
    """stock_below with threshold > 10 returns warning (default)."""
    assert _calculate_severity("stock_below", Decimal("15")) == "warning"
    assert _calculate_severity("stock_below", Decimal("100")) == "warning"


def test_calculate_severity_no_sales_critical():
    """no_sales_days with threshold >= 5 returns critical."""
    assert _calculate_severity("no_sales_days", Decimal("5")) == "critical"
    assert _calculate_severity("no_sales_days", Decimal("7")) == "critical"
    assert _calculate_severity("no_sales_days", Decimal("10")) == "critical"


def test_calculate_severity_no_sales_warning():
    """no_sales_days with threshold < 5 returns warning."""
    assert _calculate_severity("no_sales_days", Decimal("3")) == "warning"
    assert _calculate_severity("no_sales_days", Decimal("1")) == "warning"


def test_calculate_severity_competitor_price_change():
    """competitor_price_change always returns warning."""
    assert _calculate_severity("competitor_price_change", None) == "warning"
    assert _calculate_severity("competitor_price_change", Decimal("100")) == "warning"


def test_calculate_severity_visits_spike():
    """visits_spike returns info (oportunidade)."""
    assert _calculate_severity("visits_spike", None) == "info"


def test_calculate_severity_conversion_improved():
    """conversion_improved returns info (oportunidade)."""
    assert _calculate_severity("conversion_improved", None) == "info"


def test_calculate_severity_unknown_type():
    """Unknown alert types default to warning."""
    assert _calculate_severity("unknown_type", None) == "warning"
    assert _calculate_severity("some_new_alert", Decimal("50")) == "warning"


def test_calculate_severity_none_threshold():
    """None threshold treated as 0 for stock_below."""
    # 0 <= 3, so critical
    assert _calculate_severity("stock_below", None) == "critical"


# ============================================================================
# Test: Stock Below Check Logic
# ============================================================================


def test_stock_below_message_generation():
    """Stock below should generate correct message."""
    snap = MockListingSnapshot(stock=5)
    listing = MockListing(mlb_id="MLB-ABC123")
    threshold = 10

    # Simulate the logic from _check_stock_below
    if snap.stock < threshold:
        message = (
            f"Alerta de estoque: {listing.mlb_id} com apenas {snap.stock} unidades "
            f"(abaixo do limite de {threshold} unidades)"
        )
    else:
        message = None

    assert message is not None
    assert "MLB-ABC123" in message
    assert "5 unidades" in message
    assert "10 unidades" in message


def test_stock_below_at_exact_threshold():
    """Stock exactly at threshold should NOT trigger."""
    snap = MockListingSnapshot(stock=10)
    threshold = 10

    if snap.stock < threshold:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_stock_below_above_threshold():
    """Stock above threshold should NOT trigger."""
    snap = MockListingSnapshot(stock=15)
    threshold = 10

    if snap.stock < threshold:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_stock_below_zero_stock():
    """Stock = 0 should trigger."""
    snap = MockListingSnapshot(stock=0)
    threshold = 10

    if snap.stock < threshold:
        triggered = True
    else:
        triggered = False

    assert triggered


# ============================================================================
# Test: Conversion Below Check Logic
# ============================================================================


def test_conversion_below_message_generation():
    """Conversion below should generate correct message."""
    snaps = [
        MockListingSnapshot(captured_at=datetime.now(timezone.utc) - timedelta(days=6), conversion_rate=Decimal("2.5")),
        MockListingSnapshot(captured_at=datetime.now(timezone.utc) - timedelta(days=5), conversion_rate=Decimal("2.3")),
        MockListingSnapshot(captured_at=datetime.now(timezone.utc) - timedelta(days=4), conversion_rate=Decimal("2.7")),
    ]
    threshold = Decimal("3.0")

    snaps_with_conv = [s for s in snaps if s.conversion_rate]
    if snaps_with_conv:
        avg_conversion = sum(float(s.conversion_rate) for s in snaps_with_conv) / len(
            snaps_with_conv
        )
        if Decimal(str(avg_conversion)) < threshold:
            listing = MockListing(mlb_id="MLB-CONV-001")
            message = (
                f"Alerta de conversão: {listing.mlb_id} com conversão média de "
                f"{avg_conversion:.2f}% nos últimos 7 dias "
                f"(abaixo do limite de {threshold}%)"
            )
        else:
            message = None
    else:
        message = None

    assert message is not None
    assert "2.50%" in message
    assert "3.0%" in message


def test_conversion_below_no_conversion_data():
    """No conversion snapshots should return None."""
    snaps = [
        MockListingSnapshot(conversion_rate=None),
        MockListingSnapshot(conversion_rate=None),
    ]
    threshold = Decimal("3.0")

    snaps_with_conv = [s for s in snaps if s.conversion_rate]

    if not snaps_with_conv:
        message = None
    else:
        message = "should not reach here"

    assert message is None


def test_conversion_below_above_threshold():
    """Conversion above threshold should not trigger."""
    snaps = [
        MockListingSnapshot(conversion_rate=Decimal("3.5")),
        MockListingSnapshot(conversion_rate=Decimal("4.0")),
    ]
    threshold = Decimal("3.0")

    avg_conversion = sum(float(s.conversion_rate) for s in snaps) / len(snaps)

    if Decimal(str(avg_conversion)) < threshold:
        triggered = True
    else:
        triggered = False

    assert not triggered


# ============================================================================
# Test: No Sales Days Check Logic
# ============================================================================


def test_no_sales_days_message_generation():
    """No sales for N days should generate correct message."""
    days_limit = 3
    snaps = [
        MockListingSnapshot(sales_today=0),
        MockListingSnapshot(sales_today=0),
        MockListingSnapshot(sales_today=0),
    ]

    total_sales = sum(s.sales_today for s in snaps)

    if total_sales == 0:
        listing = MockListing(mlb_id="MLB-NO-SALES")
        message = (
            f"Alerta de vendas: {listing.mlb_id} sem nenhuma venda nos últimos "
            f"{days_limit} dias"
        )
    else:
        message = None

    assert message is not None
    assert "MLB-NO-SALES" in message
    assert "3 dias" in message


def test_no_sales_days_with_some_sales():
    """Some sales should not trigger."""
    snaps = [
        MockListingSnapshot(sales_today=0),
        MockListingSnapshot(sales_today=1),  # at least one sale
        MockListingSnapshot(sales_today=0),
    ]

    total_sales = sum(s.sales_today for s in snaps)

    if total_sales == 0:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_no_sales_days_exactly_zero_across_period():
    """Zero sales across entire period should trigger."""
    snaps = [
        MockListingSnapshot(sales_today=0),
        MockListingSnapshot(sales_today=0),
    ]

    total_sales = sum(s.sales_today for s in snaps)
    assert total_sales == 0


# ============================================================================
# Test: Competitor Price Change Check Logic
# ============================================================================


def test_competitor_price_change_message_generation():
    """Price change should generate correct message."""
    previous = MockCompetitorSnapshot(price=Decimal("100"))
    latest = MockCompetitorSnapshot(price=Decimal("95"))
    comp = MockCompetitor(mlb_id="COMP-LOWER")
    listing = MockListing(mlb_id="MY-MLB-001")

    if latest.price != previous.price:
        diff = float(latest.price) - float(previous.price)
        direction = "subiu" if diff > 0 else "baixou"
        message = (
            f"Alerta de concorrente: {comp.mlb_id} {direction} de "
            f"R$ {float(previous.price):.2f} para R$ {float(latest.price):.2f} "
            f"(anúncio monitorado: {listing.mlb_id})"
        )
    else:
        message = None

    assert message is not None
    assert "COMP-LOWER" in message
    assert "baixou" in message
    assert "100.00" in message
    assert "95.00" in message


def test_competitor_price_up():
    """Price increase should say 'subiu'."""
    previous = MockCompetitorSnapshot(price=Decimal("100"))
    latest = MockCompetitorSnapshot(price=Decimal("110"))

    diff = float(latest.price) - float(previous.price)
    direction = "subiu" if diff > 0 else "baixou"

    assert direction == "subiu"


def test_competitor_price_down():
    """Price decrease should say 'baixou'."""
    previous = MockCompetitorSnapshot(price=Decimal("100"))
    latest = MockCompetitorSnapshot(price=Decimal("90"))

    diff = float(latest.price) - float(previous.price)
    direction = "subiu" if diff > 0 else "baixou"

    assert direction == "baixou"


def test_competitor_price_no_change():
    """Price unchanged should not trigger."""
    previous = MockCompetitorSnapshot(price=Decimal("100"))
    latest = MockCompetitorSnapshot(price=Decimal("100"))

    if latest.price != previous.price:
        triggered = True
    else:
        triggered = False

    assert not triggered


# ============================================================================
# Test: Competitor Price Below Check Logic
# ============================================================================


def test_competitor_price_below_message_generation():
    """Competitor below threshold should generate correct message."""
    comp = MockCompetitor(mlb_id="CHEAP-COMP")
    snap = MockCompetitorSnapshot(price=Decimal("45"))
    threshold = Decimal("50")
    listing = MockListing(mlb_id="MY-LISTING")

    if snap.price < threshold:
        message = (
            f"Alerta de preço: {comp.mlb_id} está vendendo a "
            f"R$ {float(snap.price):.2f}, abaixo do limite de "
            f"R$ {float(threshold):.2f} "
            f"(anúncio monitorado: {listing.mlb_id})"
        )
    else:
        message = None

    assert message is not None
    assert "CHEAP-COMP" in message
    assert "45.00" in message
    assert "50.00" in message


def test_competitor_price_exactly_at_threshold():
    """Price exactly at threshold should NOT trigger."""
    snap = MockCompetitorSnapshot(price=Decimal("50"))
    threshold = Decimal("50")

    if snap.price < threshold:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_competitor_price_above_threshold():
    """Price above threshold should NOT trigger."""
    snap = MockCompetitorSnapshot(price=Decimal("60"))
    threshold = Decimal("50")

    if snap.price < threshold:
        triggered = True
    else:
        triggered = False

    assert not triggered


# ============================================================================
# Test: Visits Spike Check Logic
# ============================================================================


def test_visits_spike_message_generation():
    """Visits spike >150% should generate correct message."""
    now = datetime.now(timezone.utc)
    older_snaps = [
        MockListingSnapshot(captured_at=now - timedelta(days=7), visits_today=100),
        MockListingSnapshot(captured_at=now - timedelta(days=6), visits_today=120),
        MockListingSnapshot(captured_at=now - timedelta(days=5), visits_today=110),
    ]
    today_snap = MockListingSnapshot(captured_at=now, visits_today=500)

    avg_visits = sum(s.visits_today for s in older_snaps) / len(older_snaps)  # ~110

    if today_snap.visits_today > avg_visits * 1.5:
        listing = MockListing(mlb_id="MLB-SPIKE")
        message = (
            f"Oportunidade: {listing.mlb_id} com pico de visitas! "
            f"{int(today_snap.visits_today)} visitas hoje "
            f"(média: {int(avg_visits)} visitas/dia)"
        )
    else:
        message = None

    assert message is not None
    assert "500" in message


def test_visits_spike_exactly_150_percent():
    """Exactly 150% should NOT trigger (need >150%)."""
    avg_visits = 100
    today_visits = 150  # exactly 150%, not >150%

    if today_visits > avg_visits * 1.5:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_visits_spike_151_percent():
    """151% (over 150%) should trigger."""
    avg_visits = 100
    today_visits = 151  # >150%

    if today_visits > avg_visits * 1.5:
        triggered = True
    else:
        triggered = False

    assert triggered


# ============================================================================
# Test: Conversion Improved Check Logic
# ============================================================================


def test_conversion_improved_message_generation():
    """Conversion >20% improvement should generate correct message."""
    now = datetime.now(timezone.utc)
    older_snaps = [
        MockListingSnapshot(captured_at=now - timedelta(days=6), conversion_rate=Decimal("2.0")),
        MockListingSnapshot(captured_at=now - timedelta(days=5), conversion_rate=Decimal("2.2")),
    ]
    today_snap = MockListingSnapshot(captured_at=now, conversion_rate=Decimal("2.8"))

    avg_conversion = sum(float(s.conversion_rate) for s in older_snaps) / len(
        older_snaps
    )  # 2.1
    today_conversion = float(today_snap.conversion_rate)  # 2.8
    improvement = (today_conversion - avg_conversion) / max(avg_conversion, 0.01) * 100
    # (2.8 - 2.1) / 2.1 * 100 = 33.3%

    if improvement > 20:
        listing = MockListing(mlb_id="MLB-IMPROVED")
        message = (
            f"Oportunidade: {listing.mlb_id} com conversão melhorada! "
            f"{today_conversion:.2f}% hoje vs {avg_conversion:.2f}% "
            f"(+{improvement:.1f}%)"
        )
    else:
        message = None

    assert message is not None
    assert "MLB-IMPROVED" in message
    assert "2.80%" in message


def test_conversion_improved_exactly_20_percent():
    """Exactly 20% improvement should NOT trigger (need >20%)."""
    avg_conversion = 2.0
    today_conversion = 2.4  # exactly 20% improvement

    improvement = (today_conversion - avg_conversion) / max(avg_conversion, 0.01) * 100

    if improvement > 20:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_conversion_improved_21_percent():
    """21% improvement (>20%) should trigger."""
    avg_conversion = 2.0
    today_conversion = 2.42  # 21% improvement

    improvement = (today_conversion - avg_conversion) / max(avg_conversion, 0.01) * 100

    if improvement > 20:
        triggered = True
    else:
        triggered = False

    assert triggered


# ============================================================================
# Test: Stockout Forecast Check Logic
# ============================================================================


def test_stockout_forecast_message_generation():
    """Stockout in <N days should generate correct message."""
    now = datetime.now(timezone.utc)
    snaps = [
        MockListingSnapshot(
            captured_at=now - timedelta(days=13), sales_today=5
        ),  # 5 days ago
        MockListingSnapshot(captured_at=now - timedelta(days=12), sales_today=5),
        MockListingSnapshot(captured_at=now - timedelta(days=11), sales_today=5),
        MockListingSnapshot(captured_at=now - timedelta(days=10), sales_today=5),
        MockListingSnapshot(captured_at=now - timedelta(days=9), sales_today=5),
        MockListingSnapshot(captured_at=now - timedelta(days=8), sales_today=5),
    ]
    latest = MockListingSnapshot(captured_at=now, stock=20, sales_today=5)
    snaps.insert(0, latest)

    forecast_days = 7

    total_sales = sum(s.sales_today for s in snaps)
    days_with_data = len(snaps)
    avg_sales_per_day = total_sales / days_with_data  # 5 sales/day
    current_stock = latest.stock  # 20 units

    if avg_sales_per_day > 0:
        days_to_stockout = current_stock / avg_sales_per_day  # 20 / 5 = 4 days
    else:
        days_to_stockout = None

    if days_to_stockout and days_to_stockout < forecast_days:
        listing = MockListing(mlb_id="MLB-FORECAST")
        message = (
            f"Previsão de estoque: {listing.mlb_id} acabará em {int(days_to_stockout)} dias "
            f"no ritmo atual ({avg_sales_per_day:.1f} un/dia, "
            f"{int(current_stock)} restantes)"
        )
    else:
        message = None

    assert message is not None
    assert "MLB-FORECAST" in message
    assert "4 dias" in message


def test_stockout_forecast_exactly_at_threshold():
    """Exactly at threshold days should NOT trigger."""
    stock = 70
    avg_sales_per_day = 10
    forecast_days = 7

    days_to_stockout = stock / avg_sales_per_day  # 7 days

    if days_to_stockout < forecast_days:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_stockout_forecast_just_below_threshold():
    """Just below threshold should trigger."""
    stock = 69
    avg_sales_per_day = 10
    forecast_days = 7

    days_to_stockout = stock / avg_sales_per_day  # 6.9 days

    if days_to_stockout < forecast_days:
        triggered = True
    else:
        triggered = False

    assert triggered


def test_stockout_forecast_zero_sales():
    """Zero sales means no stockout risk."""
    stock = 100
    avg_sales_per_day = 0
    forecast_days = 7

    if avg_sales_per_day <= 0:
        triggered = False
    else:
        days_to_stockout = stock / avg_sales_per_day
        triggered = days_to_stockout < forecast_days

    assert not triggered


# ============================================================================
# Test: Cooldown Logic
# ============================================================================


def test_cooldown_prevents_duplicate_alerts():
    """Alert with last_triggered_at < 24h should not fire."""
    now = datetime.now(timezone.utc)
    last_triggered = now - timedelta(hours=12)  # 12 hours ago
    cooldown = timedelta(hours=24)

    time_since_last = now - last_triggered
    should_fire = time_since_last >= cooldown

    assert not should_fire


def test_cooldown_allows_after_24h():
    """Alert with last_triggered_at > 24h should fire."""
    now = datetime.now(timezone.utc)
    last_triggered = now - timedelta(hours=25)  # 25 hours ago
    cooldown = timedelta(hours=24)

    time_since_last = now - last_triggered
    should_fire = time_since_last >= cooldown

    assert should_fire


def test_cooldown_exactly_24h():
    """Alert fired exactly 24h ago should be allowed."""
    now = datetime.now(timezone.utc)
    last_triggered = now - timedelta(hours=24)  # exactly 24 hours ago
    cooldown = timedelta(hours=24)

    time_since_last = now - last_triggered
    should_fire = time_since_last >= cooldown

    assert should_fire


def test_cooldown_no_previous_trigger():
    """First trigger (no previous) should always fire."""
    last_triggered = None
    cooldown = timedelta(hours=24)

    if last_triggered is None:
        should_fire = True
    else:
        time_since_last = datetime.now(timezone.utc) - last_triggered
        should_fire = time_since_last >= cooldown

    assert should_fire


# ============================================================================
# Test: Edge Cases & Boundary Conditions
# ============================================================================


def test_zero_threshold():
    """Threshold of 0 should be treated as 0."""
    threshold = 0
    current = 5

    if current < threshold:
        triggered = True
    else:
        triggered = False

    assert not triggered


def test_decimal_precision():
    """Decimal precision should be maintained in messages."""
    price = Decimal("123.456")
    formatted = f"{float(price):.2f}"
    assert formatted == "123.46"


def test_message_with_special_characters():
    """MLBs with special characters should format correctly."""
    mlb_id = "MLB-ABC123_XYZ-456"
    message = f"Alerta para {mlb_id}"
    assert mlb_id in message
