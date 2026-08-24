"""
Tests for scenario_planning.py

test_msft_regression locks in the exact hand-calculated values verified
when this module was built - Upside/Downside are derived from MSFT's own
real historical best/worst years, not fabricated percentages.
"""

import pytest
from scenario_planning import build_scenario_assumptions, run_scenario_valuations


def test_upside_uses_best_historical_year(msft_like_df):
    """Upside growth/margin should equal the historical MAX, and upside
    capex should equal the historical MIN (lower capex = more optimistic)."""
    scenarios = build_scenario_assumptions(msft_like_df)
    hist = scenarios["historical_range"]

    assert scenarios["upside"]["avg_revenue_growth"] == pytest.approx(hist["growth_max"], abs=1e-6)
    assert scenarios["upside"]["avg_ebit_margin"] == pytest.approx(hist["margin_max"], abs=1e-6)
    assert scenarios["upside"]["avg_capex_pct_revenue"] == pytest.approx(hist["capex_pct_min"], abs=1e-6)


def test_downside_uses_worst_historical_year(msft_like_df):
    scenarios = build_scenario_assumptions(msft_like_df)
    hist = scenarios["historical_range"]

    assert scenarios["downside"]["avg_revenue_growth"] == pytest.approx(hist["growth_min"], abs=1e-6)
    assert scenarios["downside"]["avg_ebit_margin"] == pytest.approx(hist["margin_min"], abs=1e-6)
    assert scenarios["downside"]["avg_capex_pct_revenue"] == pytest.approx(hist["capex_pct_max"], abs=1e-6)


def test_base_case_matches_existing_median_logic(msft_like_df):
    """Base case must be identical to what get_historical_assumptions()
    already produces elsewhere in the project - no divergent logic."""
    from step3_dcf_engine import get_historical_assumptions
    scenarios = build_scenario_assumptions(msft_like_df)
    expected_base = get_historical_assumptions(msft_like_df, method="median")

    assert scenarios["base"]["avg_revenue_growth"] == expected_base["avg_revenue_growth"]
    assert scenarios["base"]["avg_ebit_margin"] == expected_base["avg_ebit_margin"]


def test_msft_valuation_regression(msft_like_df):
    """Regression test locking in the exact hand-verified implied prices."""
    results = run_scenario_valuations(
        msft_like_df, cash=20935000000, total_debt=56826000000, shares_outstanding=7425545491,
        wacc=0.09, terminal_growth=0.025,
    )
    assert results["downside"]["implied_price"] == pytest.approx(85.61, abs=0.5)
    assert results["base"]["implied_price"] == pytest.approx(281.19, abs=0.5)
    assert results["upside"]["implied_price"] == pytest.approx(463.18, abs=0.5)


def test_scenarios_are_correctly_ordered(msft_like_df):
    """Downside must always be lowest and Upside always highest - a basic
    sanity check that the labels match the actual computed magnitudes."""
    results = run_scenario_valuations(
        msft_like_df, cash=20935000000, total_debt=56826000000, shares_outstanding=7425545491,
        wacc=0.09, terminal_growth=0.025,
    )
    assert results["downside"]["implied_price"] < results["base"]["implied_price"] < results["upside"]["implied_price"]
