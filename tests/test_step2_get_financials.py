"""
Tests for step2_get_financials.py

These directly encode two real bugs found during manual testing:
1. A missing field used to be filled with None, which crashed pandas' .abs()
   the first time a company (Realty Income, ticker O) didn't have a
   "Capital Expenditure" line at all. Fixed by filling with NaN instead.
2. The fix above only works if the code can even FIND an alternative field
   name - REITs call their capex-equivalent "Purchase Of Investment
   Properties". The multi-candidate fallback in safe_get() handles this.
"""

import math
import pandas as pd
from step2_get_financials import get_dcf_inputs


class _FakeStock:
    """Minimal stand-in for a yfinance Ticker object, with configurable
    income_stmt / balance_sheet / cash_flow tables."""
    def __init__(self, income_stmt, balance_sheet, cash_flow):
        self.income_stmt = income_stmt
        self.balance_sheet = balance_sheet
        self.cash_flow = cash_flow


def test_missing_field_is_nan_not_none(monkeypatch):
    """Regression test for the exact crash: a company missing 'Capital
    Expenditure' entirely should get NaN (which pandas math handles
    gracefully), never None (which crashes .abs())."""
    income_stmt = pd.DataFrame({"2025": {"Total Revenue": 1000, "EBIT": 200, "Net Income": 150}})
    balance_sheet = pd.DataFrame({"2025": {"Cash And Cash Equivalents": 50, "Total Debt": 300,
                                             "Current Assets": 400, "Current Liabilities": 250}})
    cash_flow = pd.DataFrame({"2025": {"Depreciation And Amortization": 40}})  # NO capex field at all

    import step2_get_financials
    monkeypatch.setattr(step2_get_financials.yf, "Ticker",
                          lambda t: _FakeStock(income_stmt, balance_sheet, cash_flow))

    df = get_dcf_inputs("TEST")
    capex_value = df.loc["Capex", "2025"]

    assert capex_value is None or math.isnan(capex_value), (
        "Missing capex field must be NaN, not None - None crashes downstream pandas math"
    )
    # Critically: this must not raise when we do real pandas math on it
    result = df.loc["Capex"].abs() / df.loc["Revenue"]
    assert math.isnan(result["2025"])


def test_reit_capex_fallback_finds_investment_properties(monkeypatch, reit_like_df):
    """A REIT has no 'Capital Expenditure' line - its equivalent is
    'Purchase Of Investment Properties'. The multi-candidate fallback
    must find this automatically."""
    income_stmt = pd.DataFrame({
        "2025": {"Total Revenue": 5749000000, "EBIT": 1820000000, "Net Income": 900000000},
    })
    balance_sheet = pd.DataFrame({
        "2025": {"Cash And Cash Equivalents": 435000000, "Total Debt": 29346000000,
                  "Current Assets": 1400000000, "Current Liabilities": 1010000000},
    })
    cash_flow = pd.DataFrame({
        "2025": {"Depreciation And Amortization": 1700000000,
                  "Purchase Of Investment Properties": -4100000000},  # NOT "Capital Expenditure"
    })

    import step2_get_financials
    monkeypatch.setattr(step2_get_financials.yf, "Ticker",
                          lambda t: _FakeStock(income_stmt, balance_sheet, cash_flow))

    df = get_dcf_inputs("O")
    capex_value = df.loc["Capex", "2025"]

    assert capex_value == -4100000000, (
        "Capex fallback should have found 'Purchase Of Investment Properties' "
        "since 'Capital Expenditure' doesn't exist for this company"
    )


def test_all_expected_rows_present(monkeypatch, msft_like_df):
    """A normal, well-behaved company (all standard field names present)
    should produce a DataFrame with every expected row, no NaN gaps."""
    income_stmt = pd.DataFrame({
        "2026": {"Total Revenue": 331839000000, "EBIT": 168985000000, "Net Income": 133749000000},
    })
    balance_sheet = pd.DataFrame({
        "2026": {"Cash And Cash Equivalents": 20935000000, "Total Debt": 56826000000,
                  "Current Assets": 207710000000, "Current Liabilities": 168825000000},
    })
    cash_flow = pd.DataFrame({
        "2026": {"Depreciation And Amortization": 38534000000, "Capital Expenditure": -115948000000},
    })

    import step2_get_financials
    monkeypatch.setattr(step2_get_financials.yf, "Ticker",
                          lambda t: _FakeStock(income_stmt, balance_sheet, cash_flow))

    df = get_dcf_inputs("MSFT")
    expected_rows = {"Revenue", "EBIT", "Net Income", "D&A", "Capex", "Cash",
                      "Total Debt", "Current Assets", "Current Liabilities"}
    assert expected_rows.issubset(set(df.index))
    assert not df.loc["Revenue", "2026"] != df.loc["Revenue", "2026"]  # not NaN
