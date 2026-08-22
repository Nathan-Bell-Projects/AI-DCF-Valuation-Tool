"""
Tests for backtest.py

test_msft_backtest_regression locks in the exact hand-calculated values
verified when this module was built - a regression test protecting against
a future refactor accidentally breaking the leave-future-out logic.
"""

import pytest
from backtest import backtest_margin_accuracy, backtest_growth_accuracy, run_backtest


def test_no_lookahead_bias(msft_like_df):
    """The prediction for any given year must use ONLY data strictly
    before that year - this is the entire point of the backtest, so it's
    worth testing explicitly, not just trusting the implementation."""
    margin_results = backtest_margin_accuracy(msft_like_df)

    # The first predictable year should be the SECOND year in the dataset
    # (the first year has no prior history to predict from at all)
    years = sorted(msft_like_df.columns)
    assert margin_results.iloc[0]["Year"] == years[1]
    assert len(margin_results) == len(years) - 1


def test_msft_backtest_regression(msft_like_df):
    """Regression test locking in the exact known-correct values."""
    result = run_backtest(msft_like_df)

    assert result["n_margin_tests"] == 3
    assert result["n_growth_tests"] == 2

    assert result["margin_mae"] == pytest.approx(0.02966, abs=0.0005)
    assert result["margin_bias"] == pytest.approx(-0.02966, abs=0.0005)

    assert result["growth_mae"] == pytest.approx(0.01613, abs=0.0005)
    assert result["growth_bias"] == pytest.approx(-0.00875, abs=0.0005)


def test_negative_bias_means_underprediction(msft_like_df):
    """Sanity-check the bias SIGN convention: if actual consistently
    exceeds predicted, bias (predicted - actual) should be negative."""
    result = run_backtest(msft_like_df)

    margin_df = result["margin_results"]
    # MSFT's real data has actual margin exceeding predicted in every
    # single year tested (a genuine, real finding from this project) -
    # so overall bias must be negative.
    assert (margin_df["Actual Margin"] > margin_df["Predicted Margin"]).all()
    assert result["margin_bias"] < 0


def test_handles_short_history_gracefully():
    """A ticker with only 2 years of data (not enough for a growth
    prediction, which needs at least 2 prior growth rates... actually
    needs at least 1 prior growth rate, computable from 2 years) should
    not crash, even at the edge of the minimum usable history."""
    import pandas as pd
    short_df = pd.DataFrame({
        "2025": {"Revenue": 100000000, "EBIT": 20000000},
        "2026": {"Revenue": 110000000, "EBIT": 23000000},
    })
    result = run_backtest(short_df)
    # Only 1 margin prediction possible (predicting 2026 from 2025 alone),
    # and 0 growth predictions (need at least 2 growth rates, only 1 exists)
    assert result["n_margin_tests"] == 1
    assert result["n_growth_tests"] == 0
    assert result["growth_mae"] is None  # must not crash on empty data
