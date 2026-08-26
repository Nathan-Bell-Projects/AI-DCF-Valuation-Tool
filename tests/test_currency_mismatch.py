"""
Tests for check_currency_mismatch() in step2_get_financials.py

Regression test for a real bug found via manual testing: running the tool
on SONY (a USD-traded ADR whose underlying financials are reported in JPY)
produced a "+25,400% upside" - not a valuation finding, a pure unit error.
The DCF's enterprise/equity value was calculated in JPY, then divided by a
USD-based share count as if they were the same currency.
"""

import pandas as pd
from step2_get_financials import check_currency_mismatch
from fx_conversion import convert_financial_statements


def test_sony_like_mismatch_detected():
    """The exact real-world scenario that surfaced this bug."""
    sony_like = {"currency": "USD", "financialCurrency": "JPY"}
    result = check_currency_mismatch(sony_like)
    assert result["mismatch"] is True
    assert result["trading_currency"] == "USD"
    assert result["financial_currency"] == "JPY"


def test_matching_currencies_no_false_positive():
    """A normal US company (MSFT) must NOT trigger the warning."""
    msft_like = {"currency": "USD", "financialCurrency": "USD"}
    result = check_currency_mismatch(msft_like)
    assert result["mismatch"] is False


def test_missing_currency_data_does_not_crash():
    """Some tickers may not have one or both currency fields populated -
    must degrade gracefully (no mismatch flagged) rather than raise."""
    assert check_currency_mismatch({})["mismatch"] is False
    assert check_currency_mismatch({"currency": "USD"})["mismatch"] is False
    assert check_currency_mismatch({"financialCurrency": "EUR"})["mismatch"] is False


def test_ab_inbev_like_mismatch_is_recoverable_via_conversion():
    """Real bug reported via manual testing: AB InBev (ABI.BR) trades in
    EUR but reports consolidated financials in USD - a genuine mismatch,
    unlike Sony's, but still a real, valid company. The app used to hard-
    block this case entirely. It should now detect the mismatch and be
    able to convert the USD-denominated financials into EUR before the
    DCF runs, rather than refusing to show a number at all."""
    ab_inbev_like = {"currency": "EUR", "financialCurrency": "USD"}
    check = check_currency_mismatch(ab_inbev_like)
    assert check["mismatch"] is True

    usd_financials = pd.DataFrame({"2025": {"Revenue": 1000.0, "Cash": 50.0, "Total Debt": 300.0}})
    eur_rate = 0.92  # illustrative USD->EUR rate
    eur_financials = convert_financial_statements(usd_financials, eur_rate)

    assert eur_financials.loc["Revenue", "2025"] == 920.0
    assert eur_financials.loc["Cash", "2025"] == 46.0
    assert eur_financials.loc["Total Debt", "2025"] == 276.0
