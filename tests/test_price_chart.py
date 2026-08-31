"""
Tests for price_chart.py - the pure logic behind the YTD price chart:
a defensive trim to the current calendar year, and computing the
change/color info the chart header shows.
"""

import pandas as pd
import pytest
from price_chart import filter_to_ytd, compute_price_change


def _daily_series(n_days, start="2021-01-01", start_value=100.0, step=1.0):
    """A simple, deterministic daily price series for testing - value
    increases by `step` each day starting from `start_value`."""
    index = pd.date_range(start=start, periods=n_days, freq="D")
    values = [start_value + i * step for i in range(n_days)]
    return pd.Series(values, index=index)


def test_filter_to_ytd_uses_calendar_year_not_a_lookback_window():
    history = _daily_series(500, start="2024-06-01")
    filtered = filter_to_ytd(history)
    end_year = history.index.max().year
    assert filtered.index.min().year == end_year
    assert filtered.index.min().month == 1
    assert filtered.index.min().day == 1
    assert filtered.index.max() == history.index.max()


def test_filter_to_ytd_empty_history_returns_empty_without_error():
    empty = pd.Series(dtype=float)
    assert filter_to_ytd(empty).empty


def test_filter_to_ytd_handles_timezone_aware_index():
    """yfinance's real price history comes back with a tz-aware
    DatetimeIndex (e.g. America/New_York) - a naive/aware comparison
    mismatch would raise, not just give a wrong slice."""
    index = pd.date_range(start="2024-01-01", periods=400, freq="D", tz="America/New_York")
    history = pd.Series(range(400), index=index)
    filtered = filter_to_ytd(history)
    assert len(filtered) > 0
    assert filtered.index.min().year == history.index.max().year


def test_filter_to_ytd_drops_a_stray_row_from_the_prior_year():
    """Defensive case this function exists for: yfinance's own "ytd"
    fetch should already exclude prior-year rows, but if one slips
    through, this must still trim it rather than trust the input as-is."""
    history = _daily_series(40, start="2023-12-20")  # spills into Jan 2024
    filtered = filter_to_ytd(history)
    assert filtered.index.min().year == 2024
    assert (filtered.index < pd.Timestamp("2024-01-01", tz=filtered.index.tz)).sum() == 0


def test_compute_price_change_gain():
    history = _daily_series(10, start_value=100.0, step=2.0)  # 100 -> 118
    result = compute_price_change(history)
    assert result["first"] == 100.0
    assert result["last"] == 118.0
    assert result["change"] == pytest.approx(18.0)
    assert result["pct_change"] == pytest.approx(0.18)
    assert result["positive"] is True


def test_compute_price_change_loss():
    history = _daily_series(10, start_value=100.0, step=-2.0)  # 100 -> 82
    result = compute_price_change(history)
    assert result["change"] == pytest.approx(-18.0)
    assert result["positive"] is False


def test_compute_price_change_flat_counts_as_positive():
    history = _daily_series(10, start_value=50.0, step=0.0)
    result = compute_price_change(history)
    assert result["change"] == 0.0
    assert result["positive"] is True  # ties are green, matching upside/downside elsewhere


def test_compute_price_change_empty_series_does_not_crash():
    result = compute_price_change(pd.Series(dtype=float))
    assert result == {"first": None, "last": None, "change": None, "pct_change": None, "positive": True}


def test_compute_price_change_single_point_does_not_divide_by_zero():
    """A brand-new listing (or a YTD window at the very start of January)
    might only have one data point - there's no "change" to compute, but
    the single price should still be reported for display."""
    history = _daily_series(1, start_value=42.0)
    result = compute_price_change(history)
    assert result["last"] == 42.0
    assert result["change"] is None
    assert result["pct_change"] is None
    assert result["positive"] is True
