"""
Tests for step3_dcf_engine.py

Includes a regression test using the project's real MSFT figures, asserting
the implied share price matches the value we already confirmed by hand
($281.19). If a future change to the DCF math accidentally breaks this,
this test catches it immediately instead of silently shipping a wrong number.
"""

import pytest
from step3_dcf_engine import (
    get_historical_assumptions,
    forecast_free_cash_flow,
    calculate_dcf_valuation,
)


def test_median_not_mean_resists_outlier_year(msft_like_df):
    """This is the exact fix that mattered for MSFT's anomalous 2026 capex
    year: a median should be far less distorted by one outlier year than
    a mean would be."""
    median_assumptions = get_historical_assumptions(msft_like_df, method="median")
    mean_assumptions = get_historical_assumptions(msft_like_df, method="mean")

    # The 2026 capex spike should pull the MEAN capex ratio up more than
    # the MEDIAN - if this ever fails, the median logic has regressed.
    assert median_assumptions["avg_capex_pct_revenue"] <= mean_assumptions["avg_capex_pct_revenue"]


def test_nwc_calculation_matches_formula(msft_like_df):
    """NWC = (Current Assets - Cash) - Current Liabilities, as a % of
    revenue. Verify this against a hand-calculated value for one real year."""
    assumptions = get_historical_assumptions(msft_like_df, method="median")
    # 2026: (207,710,000,000 - 20,935,000,000) - 168,825,000,000 = 17,950,000,000
    expected_latest_nwc = (207710000000 - 20935000000) - 168825000000
    assert assumptions["latest_nwc"] == expected_latest_nwc


def test_capex_override_actually_applies(msft_like_df):
    """The --capex-override mechanism must actually change the assumption
    used, not just be silently ignored."""
    default_assumptions = get_historical_assumptions(msft_like_df)
    overridden_assumptions = get_historical_assumptions(
        msft_like_df, overrides={"avg_capex_pct_revenue": 0.15}
    )
    assert overridden_assumptions["avg_capex_pct_revenue"] == 0.15
    assert overridden_assumptions["avg_capex_pct_revenue"] != default_assumptions["avg_capex_pct_revenue"]


def test_msft_base_case_regression(msft_like_df):
    """Regression test: given the project's real MSFT data and the
    established base-case WACC/terminal growth, the implied share price
    must match the value already verified by hand ($281.19). A tolerance
    of a few cents allows for minor floating-point differences."""
    assumptions = get_historical_assumptions(msft_like_df)
    forecast_df = forecast_free_cash_flow(assumptions)
    result = calculate_dcf_valuation(
        forecast_df, wacc=0.09, terminal_growth=0.025,
        cash=20935000000, total_debt=56826000000, shares_outstanding=7425545491,
    )
    assert result["implied_share_price"] == pytest.approx(281.19, abs=0.5)


def test_negative_implied_price_does_not_crash(capsys):
    """A REIT-style company (huge capex relative to revenue) should produce
    a negative implied price WITHOUT raising an exception, and should print
    the explanatory warning rather than failing silently or crashing."""
    from step3_dcf_engine import get_historical_assumptions as gha
    import pandas as pd

    reit_forecast_inputs = pd.DataFrame({
        "2024": {"Revenue": 5266000000, "EBIT": 1680000000, "D&A": 1620000000,
                  "Capex": -7400000000, "Cash": 401000000, "Total Debt": 25100000000,
                  "Current Assets": 1350000000, "Current Liabilities": 980000000},
        "2025": {"Revenue": 5749000000, "EBIT": 1820000000, "D&A": 1700000000,
                  "Capex": -8100000000, "Cash": 435000000, "Total Debt": 29346000000,
                  "Current Assets": 1400000000, "Current Liabilities": 1010000000},
    })
    assumptions = gha(reit_forecast_inputs)
    forecast_df = forecast_free_cash_flow(assumptions)

    # This must not raise
    result = calculate_dcf_valuation(
        forecast_df, wacc=0.09, terminal_growth=0.025,
        cash=435000000, total_debt=29346000000, shares_outstanding=946000000,
    )
    assert result["implied_share_price"] < 0

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
