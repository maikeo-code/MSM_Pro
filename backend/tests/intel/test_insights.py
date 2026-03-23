"""
Tests for the insights generation logic — pure functions, no database.

The insights engine consumes the outputs of the Pareto and Distribution
analyses and produces a bounded list of actionable InsightItem objects.
Since a dedicated service_insights module does not exist yet, we define the
pure generation function inline (following the established project test pattern)
and validate every rule it must enforce.
"""
import os
import pytest
from datetime import datetime, timezone

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.intel.analytics.schemas import (
    InsightItem,
    InsightsResponse,
    ParetoItem,
    ParetoResponse,
    DistributionItem,
    DistributionResponse,
)


# ─── Pure insights generator (mirrors future service_insights logic) ──────────

_MAX_INSIGHTS = 5


def _make_insight(
    insight_id: str,
    insight_type: str,
    title: str,
    description: str,
    priority: str,
) -> InsightItem:
    return InsightItem(
        id=insight_id,
        type=insight_type,
        title=title,
        description=description,
        priority=priority,
        created_at=datetime.now(timezone.utc),
    )


def generate_insights(
    pareto: ParetoResponse,
    distribution: DistributionResponse,
) -> InsightsResponse:
    """
    Derive actionable insights from Pareto and Distribution analysis results.

    Rules applied (in priority order, capped at _MAX_INSIGHTS):
      1. HIGH  — concentration_risk == "high": fewer than 3 listings drive 80% revenue.
      2. HIGH  — any listing has zero revenue (zero_sales alert).
      3. MEDIUM — single listing accounts for more than 60% of revenue.
      4. MEDIUM — Gini coefficient > 0.6 (revenue is heavily skewed).
      5. LOW   — fewer than 3 listings in the entire portfolio.
    """
    insights: list[InsightItem] = []

    # Rule 1: high concentration risk
    if pareto.concentration_risk == "high":
        insights.append(_make_insight(
            "concentration_high",
            "concentration_risk",
            "High Revenue Concentration",
            (
                f"Only {pareto.core_count} listing(s) generate "
                f"{pareto.core_revenue_pct:.1f}% of your total revenue. "
                "A problem with any one of them could severely impact income."
            ),
            "high",
        ))

    # Rule 2: zero-sales listings
    zero_sales_items = [i for i in distribution.items if i.sales_count == 0]
    if zero_sales_items:
        mlb_ids = ", ".join(i.mlb_id for i in zero_sales_items[:3])
        suffix = f" (+{len(zero_sales_items) - 3} more)" if len(zero_sales_items) > 3 else ""
        insights.append(_make_insight(
            "zero_sales",
            "zero_sales",
            "Listings With Zero Sales",
            f"{len(zero_sales_items)} listing(s) recorded no sales: {mlb_ids}{suffix}.",
            "high",
        ))

    # Rule 3: single listing dominates (>60%)
    if distribution.items and distribution.items[0].pct_of_total > 60.0:
        top = distribution.items[0]
        insights.append(_make_insight(
            "single_listing_dominance",
            "revenue_dominance",
            "Single Listing Dominates Revenue",
            (
                f"{top.mlb_id} ({top.title[:40]}) accounts for "
                f"{top.pct_of_total:.1f}% of total revenue. "
                "Consider diversifying your portfolio."
            ),
            "medium",
        ))

    # Rule 4: high Gini coefficient
    if distribution.gini_coefficient > 0.6:
        insights.append(_make_insight(
            "high_gini",
            "revenue_inequality",
            "Unequal Revenue Distribution",
            (
                f"Gini coefficient is {distribution.gini_coefficient:.2f} "
                "(scale 0–1). Revenue is heavily concentrated among a small "
                "number of listings."
            ),
            "medium",
        ))

    # Rule 5: small portfolio
    if len(distribution.items) < 3:
        insights.append(_make_insight(
            "small_portfolio",
            "portfolio_size",
            "Small Active Portfolio",
            (
                f"You have only {len(distribution.items)} active listing(s). "
                "A larger portfolio reduces individual listing risk."
            ),
            "low",
        ))

    # Cap at _MAX_INSIGHTS
    capped = insights[:_MAX_INSIGHTS]

    return InsightsResponse(
        insights=capped,
        generated_at=datetime.now(timezone.utc),
    )


# ─── Fixtures / builders ──────────────────────────────────────────────────────

def _pareto(
    concentration_risk: str = "low",
    core_count: int = 5,
    core_revenue_pct: float = 82.0,
    items: list[ParetoItem] | None = None,
) -> ParetoResponse:
    return ParetoResponse(
        items=items or [],
        total_revenue=10000.0,
        core_count=core_count,
        core_revenue_pct=core_revenue_pct,
        concentration_risk=concentration_risk,
    )


def _distribution(
    revenues: list[float],
    sales_per_item: list[int] | None = None,
    gini: float = 0.2,
) -> DistributionResponse:
    if sales_per_item is None:
        sales_per_item = [5] * len(revenues)

    total = sum(revenues)
    items = [
        DistributionItem(
            mlb_id=f"MLB{i:02d}",
            title=f"Product {i}",
            revenue_30d=rev,
            sales_count=sales_per_item[i],
            pct_of_total=round(rev / total * 100, 4) if total > 0 else 0.0,
        )
        for i, rev in enumerate(revenues)
    ]
    # Sort descending as the service would deliver
    items.sort(key=lambda x: x.revenue_30d, reverse=True)
    return DistributionResponse(
        items=items,
        total_revenue=total,
        total_sales=sum(sales_per_item),
        gini_coefficient=gini,
    )


# ─── test_insights_high_concentration ────────────────────────────────────────

def test_insights_high_concentration_generates_insight():
    """concentration_risk='high' must produce a concentration_risk insight."""
    pareto = _pareto(concentration_risk="high", core_count=1, core_revenue_pct=90.0)
    dist = _distribution([9000.0, 500.0, 300.0, 200.0])

    result = generate_insights(pareto, dist)

    types = [i.type for i in result.insights]
    assert "concentration_risk" in types


def test_insights_high_concentration_has_high_priority():
    """The concentration_risk insight must carry 'high' priority."""
    pareto = _pareto(concentration_risk="high", core_count=2, core_revenue_pct=85.0)
    dist = _distribution([5000.0, 3000.0, 500.0, 300.0, 200.0])

    result = generate_insights(pareto, dist)

    concentration_insight = next(
        (i for i in result.insights if i.type == "concentration_risk"), None
    )
    assert concentration_insight is not None
    assert concentration_insight.priority == "high"


def test_insights_low_concentration_no_concentration_insight():
    """concentration_risk='low' must NOT produce a concentration_risk insight."""
    pareto = _pareto(concentration_risk="low", core_count=7, core_revenue_pct=82.0)
    dist = _distribution([1000.0] * 10, gini=0.1)

    result = generate_insights(pareto, dist)

    types = [i.type for i in result.insights]
    assert "concentration_risk" not in types


# ─── test_insights_zero_sales ─────────────────────────────────────────────────

def test_insights_zero_sales_generates_alert():
    """Listings with sales_count=0 must trigger a zero_sales insight."""
    pareto = _pareto(concentration_risk="low")
    dist = _distribution(
        revenues=[1000.0, 500.0, 200.0, 100.0],
        sales_per_item=[20, 10, 0, 0],
        gini=0.3,
    )

    result = generate_insights(pareto, dist)

    types = [i.type for i in result.insights]
    assert "zero_sales" in types


def test_insights_zero_sales_has_high_priority():
    """zero_sales insight must carry 'high' priority."""
    pareto = _pareto(concentration_risk="low")
    dist = _distribution(
        revenues=[500.0, 300.0, 0.0],
        sales_per_item=[10, 5, 0],
    )

    result = generate_insights(pareto, dist)

    zero_insight = next((i for i in result.insights if i.type == "zero_sales"), None)
    assert zero_insight is not None
    assert zero_insight.priority == "high"


def test_insights_no_zero_sales_no_alert():
    """When all listings have sales, no zero_sales insight should appear."""
    pareto = _pareto(concentration_risk="low")
    dist = _distribution(
        revenues=[1000.0, 800.0, 600.0],
        sales_per_item=[20, 15, 10],
    )

    result = generate_insights(pareto, dist)

    types = [i.type for i in result.insights]
    assert "zero_sales" not in types


# ─── test_insights_max_count ──────────────────────────────────────────────────

def test_insights_max_count():
    """The insights list must never contain more than 5 items."""
    # Configure data to trigger every rule simultaneously
    pareto = _pareto(
        concentration_risk="high",
        core_count=1,
        core_revenue_pct=99.0,
    )
    dist = _distribution(
        revenues=[9900.0, 50.0],
        sales_per_item=[100, 0],
        gini=0.98,
    )

    result = generate_insights(pareto, dist)

    assert len(result.insights) <= 5


def test_insights_max_count_enforced_precisely():
    """Even if more than 5 rules fire, exactly 5 insights are returned."""
    # Trigger all 5 rules: high risk + zero sales + dominance + high gini + small portfolio
    pareto = _pareto(
        concentration_risk="high",
        core_count=1,
        core_revenue_pct=99.0,
    )
    dist = _distribution(
        revenues=[9900.0, 0.0],
        sales_per_item=[50, 0],
        gini=0.99,
    )

    result = generate_insights(pareto, dist)

    assert len(result.insights) == _MAX_INSIGHTS


# ─── test_insights_structure ─────────────────────────────────────────────────

def test_insights_response_has_generated_at():
    """InsightsResponse must include a generated_at timestamp."""
    pareto = _pareto()
    dist = _distribution([500.0, 300.0, 200.0])

    result = generate_insights(pareto, dist)

    assert isinstance(result.generated_at, datetime)


def test_insights_items_have_required_fields():
    """Each InsightItem must carry all required fields with non-empty values."""
    pareto = _pareto(concentration_risk="high", core_count=1, core_revenue_pct=95.0)
    dist = _distribution([9500.0, 300.0, 200.0])

    result = generate_insights(pareto, dist)

    for insight in result.insights:
        assert insight.id
        assert insight.type
        assert insight.title
        assert insight.description
        assert insight.priority in {"high", "medium", "low"}
        assert isinstance(insight.created_at, datetime)


# ─── test_insights_empty_data ─────────────────────────────────────────────────

def test_insights_empty_distribution_no_crash():
    """Empty distribution must not raise; only rules that apply should fire."""
    pareto = _pareto(concentration_risk="low", core_count=0, core_revenue_pct=0.0)
    dist = DistributionResponse(
        items=[],
        total_revenue=0.0,
        total_sales=0,
        gini_coefficient=0.0,
    )

    result = generate_insights(pareto, dist)

    # Only the small_portfolio rule fires (0 items < 3)
    types = [i.type for i in result.insights]
    assert "portfolio_size" in types
    assert len(result.insights) <= _MAX_INSIGHTS


def test_insights_healthy_portfolio_few_insights():
    """
    A healthy, well-diversified portfolio with active sales should produce
    few or no high-priority insights.
    """
    pareto = _pareto(concentration_risk="low", core_count=8, core_revenue_pct=81.0)
    dist = _distribution(
        revenues=[1200.0, 1100.0, 1000.0, 900.0, 800.0, 700.0, 600.0, 500.0],
        sales_per_item=[24, 22, 20, 18, 16, 14, 12, 10],
        gini=0.15,
    )

    result = generate_insights(pareto, dist)

    high_priority = [i for i in result.insights if i.priority == "high"]
    assert len(high_priority) == 0
