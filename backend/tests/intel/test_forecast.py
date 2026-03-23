"""
Tests for the sales forecast math — pure functions, no database.

We test the helper functions that are already exported from service_forecast.py:
  - _linear_regression(x, y) -> (slope, intercept, r_squared)
  - _standard_error(x, y, slope, intercept) -> float
  - _flat_forecast(mlb_id, today, value) -> ForecastResponse

Higher-level trend-detection and confidence-bound logic is validated by driving
those helpers with controlled data, mirroring how test_calculations.py tests
pure functions extracted from service_calculations.py.
"""
import os
import math
import pytest
from datetime import date, timedelta

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.intel.analytics.service_forecast import (
    _linear_regression,
    _standard_error,
    _flat_forecast,
)
from app.intel.analytics.schemas import ForecastResponse, ForecastPoint


# ─── _linear_regression ───────────────────────────────────────────────────────

def test_linear_regression_perfect_fit():
    """y = 2x should yield slope=2, intercept=0, r_squared=1.0."""
    x = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [0.0, 2.0, 4.0, 6.0, 8.0]
    slope, intercept, r_sq = _linear_regression(x, y)
    assert slope == pytest.approx(2.0, abs=1e-9)
    assert intercept == pytest.approx(0.0, abs=1e-9)
    assert r_sq == pytest.approx(1.0, abs=1e-9)


def test_linear_regression_flat_data():
    """Constant series has slope=0 and r_squared=1.0 (all values on a line)."""
    x = [0.0, 1.0, 2.0, 3.0]
    y = [5.0, 5.0, 5.0, 5.0]
    slope, intercept, r_sq = _linear_regression(x, y)
    assert slope == pytest.approx(0.0, abs=1e-9)
    assert intercept == pytest.approx(5.0, abs=1e-9)
    # Perfect horizontal line — r_squared is 1.0 when ss_tot == 0 and ss_res == 0
    assert r_sq == pytest.approx(1.0, abs=1e-9)


def test_linear_regression_declining_trend():
    """Decreasing series should produce negative slope."""
    x = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [10.0, 8.0, 6.0, 4.0, 2.0]
    slope, intercept, r_sq = _linear_regression(x, y)
    assert slope < 0.0
    assert r_sq == pytest.approx(1.0, abs=1e-6)


def test_linear_regression_single_point():
    """Single point: slope=0, intercept=y[0], r_squared=0."""
    x = [0.0]
    y = [7.0]
    slope, intercept, r_sq = _linear_regression(x, y)
    assert slope == 0.0
    assert intercept == 7.0
    assert r_sq == 0.0


def test_linear_regression_empty():
    """Empty lists: should return 0.0 without raising."""
    slope, intercept, r_sq = _linear_regression([], [])
    assert slope == 0.0
    assert intercept == 0.0
    assert r_sq == 0.0


def test_linear_regression_r_squared_clamped():
    """r_squared must always be in [0, 1]."""
    # Noisy data with poor fit
    x = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    y = [1.0, 5.0, 2.0, 8.0, 3.0, 7.0]
    _, _, r_sq = _linear_regression(x, y)
    assert 0.0 <= r_sq <= 1.0


def test_linear_regression_two_points():
    """Two-point regression always fits perfectly (one degree of freedom)."""
    x = [0.0, 4.0]
    y = [2.0, 6.0]
    slope, intercept, r_sq = _linear_regression(x, y)
    assert slope == pytest.approx(1.0, abs=1e-9)
    assert intercept == pytest.approx(2.0, abs=1e-9)


# ─── _standard_error ──────────────────────────────────────────────────────────

def test_standard_error_perfect_fit():
    """Perfect regression has zero residuals so SE=0."""
    x = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [0.0, 2.0, 4.0, 6.0, 8.0]
    slope, intercept, _ = _linear_regression(x, y)
    se = _standard_error(x, y, slope, intercept)
    assert se == pytest.approx(0.0, abs=1e-9)


def test_standard_error_returns_non_negative():
    """Standard error must never be negative."""
    x = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 5.0, 1.0, 9.0, 4.0, 6.0]
    slope, intercept, _ = _linear_regression(x, y)
    se = _standard_error(x, y, slope, intercept)
    assert se >= 0.0


def test_standard_error_two_points_returns_zero():
    """Less than 3 points: SE returns 0.0 (not enough degrees of freedom)."""
    x = [0.0, 1.0]
    y = [1.0, 3.0]
    slope, intercept, _ = _linear_regression(x, y)
    se = _standard_error(x, y, slope, intercept)
    assert se == 0.0


def test_standard_error_one_point_returns_zero():
    """Single point: SE returns 0.0."""
    x = [0.0]
    y = [5.0]
    se = _standard_error(x, y, 0.0, 5.0)
    assert se == 0.0


# ─── _flat_forecast ───────────────────────────────────────────────────────────

def test_flat_forecast_returns_correct_structure():
    """_flat_forecast must return a ForecastResponse with 7 and 30 points."""
    today = date.today()
    result = _flat_forecast("MLB-TEST", today, 3.5)

    assert isinstance(result, ForecastResponse)
    assert result.listing_mlb_id == "MLB-TEST"
    assert len(result.forecast_7d) == 7
    assert len(result.forecast_30d) == 30
    assert result.trend == "stable"
    assert result.confidence == 0.0


def test_flat_forecast_dates_are_sequential():
    """Forecast dates must start at today+1 and increment by 1 day."""
    today = date.today()
    result = _flat_forecast("MLB-X", today, 5.0)

    for i, point in enumerate(result.forecast_7d, start=1):
        assert point.date == today + timedelta(days=i)

    for i, point in enumerate(result.forecast_30d, start=1):
        assert point.date == today + timedelta(days=i)


def test_flat_forecast_predicted_equals_value():
    """All predicted_sales values in a flat forecast equal the seed value."""
    today = date.today()
    value = 7.0
    result = _flat_forecast("MLB-Y", today, value)

    for point in result.forecast_7d:
        assert point.predicted_sales == pytest.approx(value, abs=0.01)
    for point in result.forecast_30d:
        assert point.predicted_sales == pytest.approx(value, abs=0.01)


def test_flat_forecast_confidence_bounds():
    """lower_bound must be 0, upper_bound must be >= predicted_sales."""
    today = date.today()
    result = _flat_forecast("MLB-Z", today, 4.0)

    for point in result.forecast_7d + result.forecast_30d:
        assert point.lower_bound == 0.0
        assert point.upper_bound >= point.predicted_sales


def test_flat_forecast_zero_value():
    """Zero seed value produces all-zero bounds without error."""
    today = date.today()
    result = _flat_forecast("MLB-ZERO", today, 0.0)

    for point in result.forecast_7d:
        assert point.predicted_sales == 0.0
        assert point.lower_bound == 0.0
        assert point.upper_bound == 0.0


# ─── Trend detection logic (testing the threshold applied in service) ─────────

def _detect_trend(slope: float, threshold: float = 0.05) -> str:
    """Replicate the trend-detection logic from get_sales_forecast."""
    if slope > threshold:
        return "up"
    elif slope < -threshold:
        return "down"
    return "stable"


def test_forecast_trend_up():
    """Positive slope above threshold → trend is 'up'."""
    x = list(range(10))
    y = [float(i * 2) for i in range(10)]   # slope = 2
    slope, _, _ = _linear_regression(x, y)
    assert _detect_trend(slope) == "up"


def test_forecast_trend_down():
    """Negative slope below -threshold → trend is 'down'."""
    x = list(range(10))
    y = [float(10 - i) for i in range(10)]   # slope = -1
    slope, _, _ = _linear_regression(x, y)
    assert _detect_trend(slope) == "down"


def test_forecast_trend_stable():
    """Slope within ±threshold → trend is 'stable'."""
    x = list(range(10))
    y = [5.0] * 10   # slope = 0
    slope, _, _ = _linear_regression(x, y)
    assert _detect_trend(slope) == "stable"


def test_forecast_trend_near_threshold_stable():
    """Slope of exactly 0.05 sits on the boundary and should be 'stable'."""
    assert _detect_trend(0.05) == "stable"   # not > 0.05
    assert _detect_trend(-0.05) == "stable"  # not < -0.05


# ─── Confidence-bound ordering ────────────────────────────────────────────────

def test_forecast_confidence_bounds_ordering():
    """
    For a well-fitted series: upper_bound >= predicted_sales >= lower_bound
    for all forecast points.
    """
    today = date.today()

    # Build a growing series so regression produces a non-trivial SE
    x = list(range(20))
    y = [float(i) + (i % 3) * 0.5 for i in range(20)]  # trend + small noise

    slope, intercept, r_sq = _linear_regression(x, y)
    se = _standard_error(x, y, slope, intercept)

    last_x = len(y) - 1
    points: list[ForecastPoint] = []
    for delta in range(1, 8):
        future_x = last_x + delta
        predicted = max(0.0, slope * future_x + intercept)
        lower = max(0.0, predicted - se)
        upper = predicted + se
        points.append(
            ForecastPoint(
                date=today + timedelta(days=delta),
                predicted_sales=round(predicted, 2),
                lower_bound=round(lower, 2),
                upper_bound=round(upper, 2),
            )
        )

    for pt in points:
        assert pt.upper_bound >= pt.predicted_sales
        assert pt.predicted_sales >= pt.lower_bound
        assert pt.lower_bound >= 0.0


# ─── Graceful handling of minimal history ────────────────────────────────────

def test_forecast_empty_data_uses_flat():
    """Zero history points → _flat_forecast is used, no exception raised."""
    today = date.today()
    result = _flat_forecast("MLB-EMPTY", today, 0.0)
    assert result.trend == "stable"
    assert result.confidence == 0.0
    assert len(result.forecast_7d) == 7
    assert len(result.forecast_30d) == 30


def test_forecast_single_history_point_uses_flat():
    """
    A single data point cannot drive linear regression meaningfully.
    _flat_forecast is called with the lone value and must return valid output.
    """
    today = date.today()
    lone_value = 12.0
    result = _flat_forecast("MLB-ONE", today, lone_value)

    assert result.confidence == 0.0
    for pt in result.forecast_7d:
        assert pt.predicted_sales == pytest.approx(lone_value, abs=0.01)
