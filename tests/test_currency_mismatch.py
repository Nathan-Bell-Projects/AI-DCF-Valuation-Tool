"""
Tests for check_currency_mismatch() in step2_get_financials.py

Regression test for a real bug found via manual testing: running the tool
on SONY (a USD-traded ADR whose underlying financials are reported in JPY)
produced a "+25,400% upside" - not a valuation finding, a pure unit error.
The DCF's enterprise/equity value was calculated in JPY, then divided by a
USD-based share count as if they were the same currency.
"""

from step2_get_financials import check_currency_mismatch


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
