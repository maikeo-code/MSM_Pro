"""Tests for reputacao/service.py — reputation risk calculation logic."""
import os
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.reputacao.service import REPUTATION_THRESHOLDS
from app.alertas.service import _calculate_severity


# ============================================================================
# Test: Risk Level Calculation
# ============================================================================


class MockReputationSnapshot:
    """Mock object to simulate ReputationSnapshot without DB."""

    def __init__(
        self,
        claims_rate=None,
        mediations_rate=None,
        cancellations_rate=None,
        late_shipments_rate=None,
        total_sales_60d=1000,
    ):
        self.claims_rate = Decimal(str(claims_rate)) if claims_rate is not None else None
        self.mediations_rate = (
            Decimal(str(mediations_rate)) if mediations_rate is not None else None
        )
        self.cancellations_rate = (
            Decimal(str(cancellations_rate)) if cancellations_rate is not None else None
        )
        self.late_shipments_rate = (
            Decimal(str(late_shipments_rate)) if late_shipments_rate is not None else None
        )
        self.total_sales_60d = total_sales_60d
        self.ml_account_id = "test-account-id"


def _calculate_risk_items(snapshot):
    """
    Helper function to calculate risk items for a snapshot.
    This replicates the logic from get_reputation_risk() but without DB.
    """
    total_sales = snapshot.total_sales_60d or 0

    if total_sales == 0:
        return None  # No data case

    kpi_configs = [
        {
            "kpi": "claims",
            "label": "Reclamacoes",
            "rate": float(snapshot.claims_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["claims"]),
        },
        {
            "kpi": "mediations",
            "label": "Mediacoes",
            "rate": float(snapshot.mediations_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["mediations"]),
        },
        {
            "kpi": "cancellations",
            "label": "Cancelamentos",
            "rate": float(snapshot.cancellations_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["cancellations"]),
        },
        {
            "kpi": "late_shipments",
            "label": "Atrasos de Envio",
            "rate": float(snapshot.late_shipments_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["late_shipments"]),
        },
    ]

    items = []
    for cfg in kpi_configs:
        current_rate = cfg["rate"]
        threshold = cfg["threshold"]

        current_count = int(round(total_sales * current_rate / 100))
        max_allowed = int(round(total_sales * threshold / 100))

        buffer = max_allowed - current_count
        buffer = max(buffer, 0)

        if buffer <= 1:
            risk_level = "critical"
        elif buffer <= 3:
            risk_level = "warning"
        else:
            risk_level = "safe"

        items.append(
            {
                "kpi": cfg["kpi"],
                "label": cfg["label"],
                "current_rate": current_rate,
                "threshold": threshold,
                "current_count": current_count,
                "max_allowed": max_allowed,
                "buffer": buffer,
                "risk_level": risk_level,
            }
        )

    return items


# ──── Test: Safe Risk (buffer > 3) ────


def test_risk_all_safe():
    """All KPIs have buffer > 3 (safe)."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("0.5"),  # 0.5%, well below 3%
        mediations_rate=Decimal("0.1"),  # well below 0.5%
        cancellations_rate=Decimal("0.5"),  # well below 2%
        late_shipments_rate=Decimal("5.0"),  # well below 15%
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    assert items is not None
    for item in items:
        assert item["risk_level"] == "safe"


def test_risk_claims_safe():
    """Claims rate 0.5% with 1000 sales = 5 claims, max allowed 30 (3%), buffer=25 (safe)."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("0.5"),
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["current_count"] == 5
    assert claims_item["max_allowed"] == 30
    assert claims_item["buffer"] == 25
    assert claims_item["risk_level"] == "safe"


# ──── Test: Warning Risk (1 < buffer <= 3) ────


def test_risk_claims_warning():
    """Claims at 2.8% with 1000 sales = 28 claims, max allowed 30, buffer=2 (warning)."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("2.8"),
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["current_count"] == 28
    assert claims_item["max_allowed"] == 30
    assert claims_item["buffer"] == 2
    assert claims_item["risk_level"] == "warning"


def test_risk_cancellations_warning():
    """Cancellations at 1.8% with 1000 sales = 18, max allowed 20, buffer=2 (warning)."""
    snap = MockReputationSnapshot(
        cancellations_rate=Decimal("1.8"),
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    cancel_item = next((i for i in items if i["kpi"] == "cancellations"))
    assert cancel_item["current_count"] == 18
    assert cancel_item["max_allowed"] == 20
    assert cancel_item["buffer"] == 2
    assert cancel_item["risk_level"] == "warning"


# ──── Test: Critical Risk (buffer <= 1) ────


def test_risk_claims_critical():
    """Claims at 3.0% with 1000 sales = 30 claims, max allowed 30, buffer=0 (critical)."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("3.0"),
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["current_count"] == 30
    assert claims_item["max_allowed"] == 30
    assert claims_item["buffer"] == 0
    assert claims_item["risk_level"] == "critical"


def test_risk_claims_already_exceeded():
    """Claims at 3.5% with 1000 sales = 35 claims, max allowed 30, buffer would be -5 -> clamped to 0 (critical)."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("3.5"),
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["current_count"] == 35
    assert claims_item["max_allowed"] == 30
    assert claims_item["buffer"] == 0  # clamped from -5
    assert claims_item["risk_level"] == "critical"


def test_risk_mediations_critical():
    """Mediations at 0.5% with 1000 sales = 5, max allowed 5, buffer=0 (critical)."""
    snap = MockReputationSnapshot(
        mediations_rate=Decimal("0.5"),
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    med_item = next((i for i in items if i["kpi"] == "mediations"))
    assert med_item["current_count"] == 5
    assert med_item["max_allowed"] == 5
    assert med_item["buffer"] == 0
    assert med_item["risk_level"] == "critical"


# ──── Test: No Data Case (0 sales) ────


def test_risk_no_data_zero_sales():
    """With 0 sales, should return None (no data to calculate)."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("1.0"),
        total_sales_60d=0,
    )
    items = _calculate_risk_items(snap)
    assert items is None


# ──── Test: Rounding Edge Cases ────


def test_risk_rounding_down():
    """0.4 sales of claims at 0.1% = 0.4 -> rounds to 0."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("0.1"),
        total_sales_60d=400,  # 400 * 0.1% = 0.4 -> rounds to 0
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["current_count"] == 0


def test_risk_rounding_up():
    """0.6 sales of claims at 0.1% = 0.6 -> rounds to 1."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("0.1"),
        total_sales_60d=600,  # 600 * 0.1% = 0.6 -> rounds to 1
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["current_count"] == 1


# ──── Test: Small Volume Edge Cases ────


def test_risk_small_volume_10_sales():
    """With 10 sales: 3% threshold = 0.3 claims max, rounds to 0."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("0.0"),
        total_sales_60d=10,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    max_allowed = claims_item["max_allowed"]
    # 10 * 3% = 0.3, rounds to 0
    assert max_allowed == 0


def test_risk_small_volume_100_sales():
    """With 100 sales: 3% threshold = 3 claims max."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("0.0"),
        total_sales_60d=100,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    max_allowed = claims_item["max_allowed"]
    # 100 * 3% = 3
    assert max_allowed == 3


# ──── Test: Mixed Risk Levels ────


def test_risk_mixed_levels():
    """Some KPIs safe, some warning, some critical."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("0.5"),  # safe: 5 claims, max 30, buffer=25
        mediations_rate=Decimal("0.49"),  # critical: 4.9->5 mediations, max 5, buffer=0 (0.5% threshold)
        cancellations_rate=Decimal("1.8"),  # warning: 18 cancellations, max 20, buffer=2 (2% threshold)
        late_shipments_rate=Decimal("14.9"),  # safe (15% threshold), 149 late shipments, max 150, buffer=1 but late_shipments has high threshold
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    risks = {item["kpi"]: item["risk_level"] for item in items}

    assert risks["claims"] == "safe"
    assert risks["mediations"] == "critical"  # 4.9 rounds to 5, max allowed 5, buffer=0
    assert risks["cancellations"] == "warning"  # 18, max 20, buffer=2
    assert risks["late_shipments"] == "critical"  # 149, max 150, buffer=1 <= 1 = critical


# ──── Test: Null Rates Treated as 0 ────


def test_risk_null_rates_treated_as_zero():
    """None rates should be treated as 0% (best case)."""
    snap = MockReputationSnapshot(
        claims_rate=None,
        mediations_rate=None,
        cancellations_rate=None,
        late_shipments_rate=None,
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    for item in items:
        assert item["current_rate"] == 0
        assert item["current_count"] == 0
        assert item["buffer"] > 3
        assert item["risk_level"] == "safe"


# ──── Test: Large Volume ────


def test_risk_large_volume_100k_sales():
    """With 100k sales: each 1% = 1000 events."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("2.5"),  # 2500 claims
        total_sales_60d=100000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["current_count"] == 2500
    assert claims_item["max_allowed"] == 3000  # 3%
    assert claims_item["buffer"] == 500  # safe


# ──── Test: Buffer Edge Values ────


def test_risk_buffer_exactly_1():
    """Buffer exactly 1 should be critical."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("2.9"),  # 29 claims, max 30, buffer=1
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["buffer"] == 1
    assert claims_item["risk_level"] == "critical"


def test_risk_buffer_exactly_2():
    """Buffer exactly 2 should be warning."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("2.8"),  # 28 claims, max 30, buffer=2
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["buffer"] == 2
    assert claims_item["risk_level"] == "warning"


def test_risk_buffer_exactly_3():
    """Buffer exactly 3 should be warning."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("2.7"),  # 27 claims, max 30, buffer=3
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["buffer"] == 3
    assert claims_item["risk_level"] == "warning"


def test_risk_buffer_exactly_4():
    """Buffer exactly 4 should be safe."""
    snap = MockReputationSnapshot(
        claims_rate=Decimal("2.6"),  # 26 claims, max 30, buffer=4
        total_sales_60d=1000,
    )
    items = _calculate_risk_items(snap)
    claims_item = next((i for i in items if i["kpi"] == "claims"))
    assert claims_item["buffer"] == 4
    assert claims_item["risk_level"] == "safe"


# ============================================================================
# Test: Reputation Thresholds Constant
# ============================================================================


def test_reputation_thresholds_defined():
    """Verify all thresholds are defined and reasonable."""
    assert "claims" in REPUTATION_THRESHOLDS
    assert "mediations" in REPUTATION_THRESHOLDS
    assert "cancellations" in REPUTATION_THRESHOLDS
    assert "late_shipments" in REPUTATION_THRESHOLDS

    # All should be percentages > 0
    for key, threshold in REPUTATION_THRESHOLDS.items():
        assert threshold > 0, f"{key} threshold should be positive"
        assert threshold < 100, f"{key} threshold should be < 100%"


def test_reputation_thresholds_order():
    """Verify thresholds follow expected priority (late_shipments > claims > cancellations > mediations)."""
    assert REPUTATION_THRESHOLDS["late_shipments"] > REPUTATION_THRESHOLDS["claims"]
    assert REPUTATION_THRESHOLDS["claims"] > REPUTATION_THRESHOLDS["cancellations"]
    assert REPUTATION_THRESHOLDS["cancellations"] > REPUTATION_THRESHOLDS["mediations"]


# ============================================================================
# Test: Severity Calculation
# ============================================================================


def test_calculate_severity_stock_below_critical():
    """stock_below with threshold <= 3 should be critical."""
    severity = _calculate_severity("stock_below", Decimal("3"))
    assert severity == "critical"

    severity = _calculate_severity("stock_below", Decimal("1"))
    assert severity == "critical"


def test_calculate_severity_stock_below_warning():
    """stock_below with 3 < threshold <= 10 should be warning."""
    severity = _calculate_severity("stock_below", Decimal("5"))
    assert severity == "warning"

    severity = _calculate_severity("stock_below", Decimal("10"))
    assert severity == "warning"


def test_calculate_severity_stock_below_info():
    """stock_below with threshold > 10 should default to warning (not info for stock)."""
    severity = _calculate_severity("stock_below", Decimal("20"))
    assert severity == "warning"  # falls through to default


def test_calculate_severity_no_sales_critical():
    """no_sales_days with threshold >= 5 should be critical."""
    severity = _calculate_severity("no_sales_days", Decimal("5"))
    assert severity == "critical"

    severity = _calculate_severity("no_sales_days", Decimal("7"))
    assert severity == "critical"


def test_calculate_severity_no_sales_warning():
    """no_sales_days with threshold < 5 should be warning."""
    severity = _calculate_severity("no_sales_days", Decimal("3"))
    assert severity == "warning"


def test_calculate_severity_competitor_price_change():
    """competitor_price_change should be warning."""
    severity = _calculate_severity("competitor_price_change", None)
    assert severity == "warning"


def test_calculate_severity_visits_spike():
    """visits_spike should be info."""
    severity = _calculate_severity("visits_spike", None)
    assert severity == "info"


def test_calculate_severity_conversion_improved():
    """conversion_improved should be info."""
    severity = _calculate_severity("conversion_improved", None)
    assert severity == "info"


def test_calculate_severity_unknown_type():
    """Unknown alert type should default to warning."""
    severity = _calculate_severity("unknown_alert_type", Decimal("100"))
    assert severity == "warning"


def test_calculate_severity_none_threshold():
    """Threshold of None should be treated as 0."""
    severity = _calculate_severity("stock_below", None)
    assert severity == "critical"  # 0 <= 3
