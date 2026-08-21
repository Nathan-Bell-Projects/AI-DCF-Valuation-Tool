"""
Tests for capm_wacc.py

test_bad_risk_free_rate_triggers_fallback is a direct regression test for a
real bug found during manual testing: an earlier version of get_risk_free_rate
applied an incorrect extra /10 scaling to the ^TNX ticker's value, silently
producing a ~0.5% risk-free rate instead of ~4.7%. This test locks in the
fix (a sanity-bounds check) so that specific failure mode can never return
undetected.
"""

import pytest
import pandas as pd
from capm_wacc import compute_capm_wacc, get_risk_free_rate, DEFAULT_RISK_FREE_RATE


class _FakeTNX:
    def __init__(self, price):
        self.info = {"regularMarketPrice": price}


def test_bad_risk_free_rate_triggers_fallback(monkeypatch):
    """Regression test for the real scaling bug: if ^TNX's value, once
    divided by 100, falls outside a sane range for a risk-free rate
    (0.5% to 15%), the function must fall back to the safe default instead
    of silently returning a nonsense value."""
    import capm_wacc

    # Simulates the exact bug scenario: this would have produced ~0.047%
    # under the old buggy logic - clearly outside any sane range.
    monkeypatch.setattr(capm_wacc.yf, "Ticker", lambda t: _FakeTNX(0.047))
    rate = get_risk_free_rate()
    assert rate == DEFAULT_RISK_FREE_RATE, (
        "An out-of-range ^TNX pull must fall back to the default rate, "
        "not silently propagate a nonsense value into every WACC calculation"
    )


def test_sane_risk_free_rate_is_used_directly(monkeypatch):
    """A realistic ^TNX value (e.g. 4.70, meaning 4.70%) should be used
    as-is, not overridden by the fallback."""
    import capm_wacc

    monkeypatch.setattr(capm_wacc.yf, "Ticker", lambda t: _FakeTNX(4.70))
    rate = get_risk_free_rate()
    assert rate == pytest.approx(0.047, abs=0.001)


def test_capm_formula_matches_hand_calculation():
    """Cost of Equity = Risk-Free Rate + Beta x Equity Risk Premium.
    Verify against a hand-calculated value using MSFT's real beta."""
    df = pd.DataFrame({
        "2026": {"Total Debt": 56826000000, "Interest Expense": 2400000000},
    })
    stock_info = {"beta": 1.099, "marketCap": 3596000000000}

    result = compute_capm_wacc("MSFT", df, stock_info, tax_rate=0.21, risk_free_rate=0.047)

    expected_cost_of_equity = 0.047 + 1.099 * 0.05  # rf + beta * ERP
    assert result["cost_of_equity"] == pytest.approx(expected_cost_of_equity, abs=0.0001)


def test_missing_beta_falls_back_to_market_average():
    """If beta is None (some tickers lack it), the function should use a
    market-average beta of 1.0 rather than crashing or propagating None
    into arithmetic."""
    df = pd.DataFrame({"2026": {"Total Debt": 1000000000, "Interest Expense": 50000000}})
    stock_info = {"beta": None, "marketCap": 5000000000}

    result = compute_capm_wacc("XYZ", df, stock_info, risk_free_rate=0.047)
    assert result["beta"] == 1.0
    assert result["beta_was_missing"] is True


def test_missing_interest_expense_falls_back_to_credit_spread():
    """If interest expense data isn't available, cost of debt should fall
    back to a risk-free-rate-plus-spread proxy, not crash on a NaN divide."""
    df = pd.DataFrame({"2026": {"Total Debt": 1000000000, "Interest Expense": float("nan")}})
    stock_info = {"beta": 1.0, "marketCap": 5000000000}

    result = compute_capm_wacc("XYZ", df, stock_info, risk_free_rate=0.047)
    assert "fallback" in result["cost_of_debt_source"]
    assert result["cost_of_debt_pretax"] > 0
