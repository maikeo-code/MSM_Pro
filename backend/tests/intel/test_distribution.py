"""
Tests for the revenue distribution and Gini coefficient logic.

The service_distribution module does not exist yet.  Per the project pattern
(test pure calculation helpers independently of the DB), we define the pure
distribution functions here and test them in isolation.  Once the module is
created, these helpers should be imported from it directly.
"""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.intel.analytics.schemas import DistributionItem, DistributionResponse


# ─── Pure distribution helpers ────────────────────────────────────────────────

def _compute_gini(revenues: list[float]) -> float:
    """
    Compute the Gini coefficient for a list of revenue values.

    Returns a value in [0.0, 1.0]:
      0.0  — perfect equality (all listings have equal revenue)
      1.0  — maximum concentration (one listing has all revenue)

    Algorithm: sorted-values formula used in welfare economics.
    """
    n = len(revenues)
    if n == 0:
        return 0.0

    sorted_rev = sorted(revenues)
    total = sum(sorted_rev)
    if total == 0:
        return 0.0

    cumulative_sum = 0.0
    for i, v in enumerate(sorted_rev):
        cumulative_sum += (2 * (i + 1) - n - 1) * v

    return cumulative_sum / (n * total)


def _build_distribution(rows: list[dict]) -> DistributionResponse:
    """
    Build a DistributionResponse from a list of dicts with keys:
      mlb_id, title, revenue_30d, sales_count.

    Items are returned sorted descending by revenue_30d.
    """
    if not rows:
        return DistributionResponse(
            items=[],
            total_revenue=0.0,
            total_sales=0,
            gini_coefficient=0.0,
        )

    sorted_rows = sorted(rows, key=lambda r: r["revenue_30d"], reverse=True)
    total_revenue = sum(r["revenue_30d"] for r in sorted_rows)
    total_sales = sum(r["sales_count"] for r in sorted_rows)

    items = [
        DistributionItem(
            mlb_id=r["mlb_id"],
            title=r["title"],
            revenue_30d=round(r["revenue_30d"], 2),
            sales_count=r["sales_count"],
            pct_of_total=round((r["revenue_30d"] / total_revenue * 100), 4)
            if total_revenue > 0 else 0.0,
        )
        for r in sorted_rows
    ]

    gini = _compute_gini([r["revenue_30d"] for r in rows])

    return DistributionResponse(
        items=items,
        total_revenue=round(total_revenue, 2),
        total_sales=total_sales,
        gini_coefficient=round(gini, 4),
    )


def _make_row(mlb_id: str, revenue: float, sales: int = 1, title: str = "") -> dict:
    return {
        "mlb_id": mlb_id,
        "title": title or f"Product {mlb_id}",
        "revenue_30d": revenue,
        "sales_count": sales,
    }


# ─── _compute_gini ────────────────────────────────────────────────────────────

def test_gini_empty_list():
    """Empty input → Gini = 0.0 (no concentration)."""
    assert _compute_gini([]) == 0.0


def test_gini_single_value():
    """Single value → Gini = 0.0 (trivially equal)."""
    assert _compute_gini([500.0]) == 0.0


def test_gini_perfect_equality():
    """All equal revenues → Gini ≈ 0.0."""
    revenues = [100.0, 100.0, 100.0, 100.0, 100.0]
    gini = _compute_gini(revenues)
    assert gini == pytest.approx(0.0, abs=1e-9)


def test_gini_maximum_concentration():
    """One listing has all revenue → Gini close to 1.0."""
    revenues = [0.0, 0.0, 0.0, 0.0, 10000.0]
    gini = _compute_gini(revenues)
    # With zero values, max concentration approaches (n-1)/n
    assert gini >= 0.7


def test_gini_between_zero_and_one():
    """Gini coefficient must always be in [0, 1]."""
    revenues = [100.0, 500.0, 250.0, 750.0, 1000.0, 80.0, 30.0]
    gini = _compute_gini(revenues)
    assert 0.0 <= gini <= 1.0


def test_gini_zero_total_returns_zero():
    """All-zero revenues → Gini = 0.0 (avoids division by zero)."""
    assert _compute_gini([0.0, 0.0, 0.0]) == 0.0


def test_gini_highly_unequal():
    """Skewed distribution has Gini > 0.5."""
    revenues = [1.0, 1.0, 1.0, 1.0, 1000.0]
    gini = _compute_gini(revenues)
    assert gini > 0.5


# ─── test_distribution_empty ─────────────────────────────────────────────────

def test_distribution_empty():
    """No data → returns zeroed DistributionResponse without raising."""
    result = _build_distribution([])
    assert result.items == []
    assert result.total_revenue == 0.0
    assert result.total_sales == 0
    assert result.gini_coefficient == 0.0


# ─── test_distribution_basic ─────────────────────────────────────────────────

def test_distribution_basic():
    """
    5 listings → percentages must sum to 100% and all fields must be populated.
    """
    rows = [
        _make_row("MLB1", 1000.0, sales=20),
        _make_row("MLB2",  800.0, sales=15),
        _make_row("MLB3",  600.0, sales=10),
        _make_row("MLB4",  400.0, sales=8),
        _make_row("MLB5",  200.0, sales=5),
    ]
    result = _build_distribution(rows)

    assert len(result.items) == 5
    assert result.total_revenue == pytest.approx(3000.0, abs=0.01)
    assert result.total_sales == 58

    pct_sum = sum(item.pct_of_total for item in result.items)
    assert pct_sum == pytest.approx(100.0, abs=0.01)


# ─── test_distribution_sorted ────────────────────────────────────────────────

def test_distribution_sorted():
    """Items must be returned in descending revenue order."""
    rows = [
        _make_row("MLB_C", 300.0, sales=5),
        _make_row("MLB_A", 900.0, sales=20),
        _make_row("MLB_B", 600.0, sales=10),
    ]
    result = _build_distribution(rows)

    revenues = [item.revenue_30d for item in result.items]
    assert revenues == sorted(revenues, reverse=True)

    # First item should be MLB_A
    assert result.items[0].mlb_id == "MLB_A"


# ─── test_distribution_gini_equal ────────────────────────────────────────────

def test_distribution_gini_equal():
    """Equal revenues across all listings → Gini coefficient ≈ 0."""
    rows = [_make_row(f"MLB{i}", 500.0, sales=10) for i in range(6)]
    result = _build_distribution(rows)

    assert result.gini_coefficient == pytest.approx(0.0, abs=1e-4)


# ─── test_distribution_gini_unequal ──────────────────────────────────────────

def test_distribution_gini_unequal():
    """One listing dominates → Gini coefficient approaches 1."""
    rows = [
        _make_row("MLB_DOM",  9900.0, sales=100),
        _make_row("MLB_TINY",  100.0, sales=2),
    ]
    result = _build_distribution(rows)

    # Two-item maximum Gini is (n-1)/n = 0.5; here inequality is extreme
    assert result.gini_coefficient > 0.4


# ─── test_distribution_pct_of_total ──────────────────────────────────────────

def test_distribution_pct_of_total_correct():
    """pct_of_total must reflect each listing's share of total revenue."""
    rows = [
        _make_row("MLB_A", 750.0, sales=15),
        _make_row("MLB_B", 250.0, sales=5),
    ]
    result = _build_distribution(rows)

    item_a = next(i for i in result.items if i.mlb_id == "MLB_A")
    item_b = next(i for i in result.items if i.mlb_id == "MLB_B")

    assert item_a.pct_of_total == pytest.approx(75.0, abs=0.01)
    assert item_b.pct_of_total == pytest.approx(25.0, abs=0.01)


# ─── test_distribution_single_listing ────────────────────────────────────────

def test_distribution_single_listing():
    """Single listing → 100% share, Gini = 0."""
    rows = [_make_row("MLB_SOLO", 2500.0, sales=50)]
    result = _build_distribution(rows)

    assert len(result.items) == 1
    assert result.items[0].pct_of_total == pytest.approx(100.0, abs=0.01)
    assert result.gini_coefficient == pytest.approx(0.0, abs=1e-4)


# ─── test_distribution_total_sales ───────────────────────────────────────────

def test_distribution_total_sales_aggregated():
    """total_sales must be the sum of all listing sales_count values."""
    rows = [
        _make_row("MLB1", 500.0, sales=12),
        _make_row("MLB2", 300.0, sales=8),
        _make_row("MLB3", 200.0, sales=5),
    ]
    result = _build_distribution(rows)
    assert result.total_sales == 25
