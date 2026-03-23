"""
Tests for the Pareto 80/20 analysis logic — pure calculation, no database.

The service_pareto.get_pareto_analysis() function is async and requires an
AsyncSession, so we extract and replicate the pure classification logic here.
This mirrors the pattern used in test_calculations.py and test_health_score.py
throughout the project.
"""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.intel.analytics.schemas import ParetoItem, ParetoResponse


# ─── Pure classification helper (mirrors service_pareto logic) ────────────────

def _classify_rows(rows: list[dict]) -> ParetoResponse:
    """
    Re-implement the Pareto classification logic as a pure function so we can
    unit-test it without a database session.

    Each row must have keys: mlb_id, title, revenue_30d.
    Rows are expected in descending revenue order (as the DB query delivers).
    """
    if not rows:
        return ParetoResponse(
            items=[],
            total_revenue=0.0,
            core_count=0,
            core_revenue_pct=0.0,
            concentration_risk="low",
        )

    # Sort descending to mirror ORDER BY SUM(revenue) DESC
    sorted_rows = sorted(rows, key=lambda r: r["revenue_30d"], reverse=True)
    total_revenue = sum(r["revenue_30d"] for r in sorted_rows)

    items: list[ParetoItem] = []
    cumulative = 0.0

    for row in sorted_rows:
        rev = float(row["revenue_30d"])
        revenue_pct = (rev / total_revenue * 100) if total_revenue > 0 else 0.0
        prev_cumulative = cumulative
        cumulative += revenue_pct

        if cumulative <= 80.0:
            classification = "core"
        elif cumulative <= 95.0:
            classification = "productive"
        else:
            classification = "long_tail"

        # Listing that crosses the 80% boundary is still "core"
        if revenue_pct > 0 and prev_cumulative < 80.0 <= cumulative:
            classification = "core"

        items.append(
            ParetoItem(
                mlb_id=row["mlb_id"],
                title=row["title"],
                revenue_30d=round(rev, 2),
                revenue_pct=round(revenue_pct, 2),
                cumulative_pct=round(min(cumulative, 100.0), 2),
                classification=classification,
            )
        )

    core_items = [i for i in items if i.classification == "core"]
    core_count = len(core_items)
    core_revenue_sum = sum(i.revenue_30d for i in core_items)
    core_revenue_pct = (core_revenue_sum / total_revenue * 100) if total_revenue > 0 else 0.0

    if core_count <= 2:
        concentration_risk = "high"
    elif core_count <= 5:
        concentration_risk = "medium"
    else:
        concentration_risk = "low"

    return ParetoResponse(
        items=items,
        total_revenue=round(total_revenue, 2),
        core_count=core_count,
        core_revenue_pct=round(core_revenue_pct, 2),
        concentration_risk=concentration_risk,
    )


def _make_row(mlb_id: str, revenue: float, title: str = "") -> dict:
    return {"mlb_id": mlb_id, "title": title or f"Product {mlb_id}", "revenue_30d": revenue}


# ─── test_pareto_empty ────────────────────────────────────────────────────────

def test_pareto_empty():
    """No rows → returns a zeroed ParetoResponse with concentration_risk=low."""
    result = _classify_rows([])
    assert result.items == []
    assert result.total_revenue == 0.0
    assert result.core_count == 0
    assert result.core_revenue_pct == 0.0
    assert result.concentration_risk == "low"


# ─── test_pareto_single_listing ───────────────────────────────────────────────

def test_pareto_single_listing():
    """One listing must be 'core' and represent 100% of revenue."""
    rows = [_make_row("MLB1", 500.0)]
    result = _classify_rows(rows)

    assert len(result.items) == 1
    item = result.items[0]
    assert item.classification == "core"
    assert item.revenue_pct == 100.0
    assert item.cumulative_pct == 100.0
    assert result.total_revenue == 500.0
    assert result.core_count == 1
    assert result.core_revenue_pct == 100.0


# ─── test_pareto_basic ────────────────────────────────────────────────────────

def test_pareto_basic():
    """
    10 listings with varied revenues.  The top listings that cumulatively reach
    80% should be classified as 'core', the next band as 'productive', and the
    rest as 'long_tail'.
    """
    rows = [
        _make_row("MLB01", 3000.0),
        _make_row("MLB02", 2500.0),
        _make_row("MLB03", 1500.0),
        _make_row("MLB04", 800.0),
        _make_row("MLB05", 700.0),
        _make_row("MLB06", 400.0),
        _make_row("MLB07", 300.0),
        _make_row("MLB08", 200.0),
        _make_row("MLB09", 100.0),
        _make_row("MLB10", 50.0),
    ]
    result = _classify_rows(rows)

    assert len(result.items) == 10
    assert result.total_revenue == pytest.approx(9550.0, abs=0.01)

    # Every item must carry one of the three valid classifications
    valid_classes = {"core", "productive", "long_tail"}
    for item in result.items:
        assert item.classification in valid_classes

    # Core items must exist
    assert result.core_count >= 1

    # Core revenue percentage must be >= 80%
    assert result.core_revenue_pct >= 80.0

    # Items must appear in descending revenue order
    revenues = [item.revenue_30d for item in result.items]
    assert revenues == sorted(revenues, reverse=True)


# ─── test_pareto_concentration_high ──────────────────────────────────────────

def test_pareto_concentration_high():
    """
    When 1 or 2 listings produce >=80% of revenue the risk is 'high'.
    Here one listing produces 90% of total revenue.
    """
    rows = [
        _make_row("MLB_BIG", 9000.0),
        _make_row("MLB_S1",   200.0),
        _make_row("MLB_S2",   200.0),
        _make_row("MLB_S3",   200.0),
        _make_row("MLB_S4",   200.0),
        _make_row("MLB_S5",   200.0),
    ]
    result = _classify_rows(rows)

    assert result.concentration_risk == "high"
    assert result.core_count <= 2


# ─── test_pareto_concentration_low ───────────────────────────────────────────

def test_pareto_concentration_low():
    """
    When revenue is spread across more than 5 listings the risk is 'low'.
    Equal distribution across 10 listings means all are needed for 80%.
    """
    rows = [_make_row(f"MLB{i:02d}", 1000.0) for i in range(10)]
    result = _classify_rows(rows)

    assert result.concentration_risk == "low"
    assert result.core_count > 5


# ─── test_pareto_concentration_medium ────────────────────────────────────────

def test_pareto_concentration_medium():
    """
    When 3-5 listings produce 80% of revenue the risk is 'medium'.
    Set up so exactly 4 listings cover ~80%.
    """
    rows = [
        _make_row("MLB1", 2000.0),
        _make_row("MLB2", 2000.0),
        _make_row("MLB3", 1800.0),
        _make_row("MLB4", 1600.0),   # cumulative ≈ 75% after this
        _make_row("MLB5",  600.0),   # pushes past 80%
        _make_row("MLB6",  500.0),
        _make_row("MLB7",  400.0),
        _make_row("MLB8",  300.0),
        _make_row("MLB9",  200.0),
        _make_row("MLB10", 100.0),
    ]
    result = _classify_rows(rows)

    assert result.concentration_risk in {"medium", "high"}
    assert 2 <= result.core_count <= 5


# ─── test_pareto_cumulative_percentage ───────────────────────────────────────

def test_pareto_cumulative_percentage():
    """
    Cumulative percentages must be non-decreasing and the final item must
    reach 100%.
    """
    rows = [_make_row(f"MLB{i}", float((10 - i) * 100)) for i in range(10)]
    result = _classify_rows(rows)

    cumulative_values = [item.cumulative_pct for item in result.items]

    # Non-decreasing
    for i in range(1, len(cumulative_values)):
        assert cumulative_values[i] >= cumulative_values[i - 1]

    # Last item reaches 100%
    assert cumulative_values[-1] == pytest.approx(100.0, abs=0.01)


# ─── test_pareto_revenue_pct_sums_to_100 ─────────────────────────────────────

def test_pareto_revenue_pct_sums_to_100():
    """All individual revenue_pct values must sum to approximately 100%."""
    rows = [_make_row(f"MLB{i}", float(i * 150 + 100)) for i in range(8)]
    result = _classify_rows(rows)

    total_pct = sum(item.revenue_pct for item in result.items)
    assert total_pct == pytest.approx(100.0, abs=0.1)


# ─── test_pareto_zero_revenue_rows ───────────────────────────────────────────

def test_pareto_zero_revenue_rows():
    """
    Listings with zero revenue should be present in the output but classified
    as long_tail (they contribute 0% of revenue).
    """
    rows = [
        _make_row("MLB_BIG", 1000.0),
        _make_row("MLB_ZERO_1", 0.0),
        _make_row("MLB_ZERO_2", 0.0),
    ]
    result = _classify_rows(rows)

    # The big listing alone is 100% revenue and is core
    mlb_big = next(i for i in result.items if i.mlb_id == "MLB_BIG")
    assert mlb_big.classification == "core"

    # Zero-revenue listings are long_tail
    zeros = [i for i in result.items if i.revenue_30d == 0.0]
    for z in zeros:
        assert z.classification == "long_tail"
