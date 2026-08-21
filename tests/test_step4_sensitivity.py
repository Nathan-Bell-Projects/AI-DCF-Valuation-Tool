"""
Tests for step4_sensitivity.py
"""

import math
from step3_dcf_engine import get_historical_assumptions, forecast_free_cash_flow
from step4_sensitivity import build_sensitivity_table


def test_growth_equal_or_above_wacc_is_skipped_not_crashed(msft_like_df):
    """The Gordon Growth terminal value formula breaks (divide by zero or
    negative denominator) if terminal growth >= WACC. The sensitivity table
    must skip these combinations gracefully (NaN/None), never crash."""
    assumptions = get_historical_assumptions(msft_like_df)
    forecast_df = forecast_free_cash_flow(assumptions)

    # Intentionally include a growth rate EQUAL to a WACC value in the grid
    table = build_sensitivity_table(
        forecast_df, cash=20935000000, total_debt=56826000000, shares_outstanding=7425545491,
        wacc_range=[0.07, 0.09], growth_range=[0.07, 0.02],  # 0.07 growth == 0.07 WACC
    )
    # The cell where growth (0.07) equals WACC (0.07) should be NaN, not a crash
    assert table.loc[0.07, 0.07] is None or math.isnan(table.loc[0.07, 0.07])
    # A normal, valid combination should still produce a real number
    assert table.loc[0.09, 0.02] > 0


def test_sensitivity_grid_matches_direct_calculation(msft_like_df):
    """The value in a specific sensitivity table cell should exactly match
    calling calculate_dcf_valuation directly with the same WACC/growth -
    i.e. the table isn't computing something subtly different."""
    from step3_dcf_engine import calculate_dcf_valuation
    import pytest

    assumptions = get_historical_assumptions(msft_like_df)
    forecast_df = forecast_free_cash_flow(assumptions)

    direct_result = calculate_dcf_valuation(
        forecast_df, wacc=0.09, terminal_growth=0.025,
        cash=20935000000, total_debt=56826000000, shares_outstanding=7425545491,
    )

    table = build_sensitivity_table(
        forecast_df, cash=20935000000, total_debt=56826000000, shares_outstanding=7425545491,
        wacc_range=[0.09], growth_range=[0.025],
    )

    assert table.loc[0.09, 0.025] == pytest.approx(direct_result["implied_share_price"], abs=0.01)
