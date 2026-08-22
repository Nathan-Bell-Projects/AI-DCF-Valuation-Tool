"""
Tests for comps_valuation.py

test_ev_ebitda_and_pe_regression locks in the exact hand-calculated values
verified when this module was first built (peer set: GOOGL, ORCL, CRM -
the same real comps listed for MSFT in the Morningstar report analyzed at
the very start of this project).
"""

import pytest
from unittest.mock import MagicMock
from comps_valuation import compute_comps_valuation


MOCK_DATA = {
    "MSFT": {"longName": "Microsoft Corp", "enterpriseToEbitda": 22.6, "trailingPE": 39.4,
              "marketCap": 3596000000000, "ebitda": 168315000000, "trailingEps": 13.36},
    "GOOGL": {"longName": "Alphabet Inc", "enterpriseToEbitda": 18.0, "trailingPE": 23.1,
               "marketCap": 2377000000000, "ebitda": 130000000000, "trailingEps": 8.50},
    "ORCL": {"longName": "Oracle Corp", "enterpriseToEbitda": 25.7, "trailingPE": 54.5,
              "marketCap": 704000000000, "ebitda": 27000000000, "trailingEps": 4.60},
    "CRM": {"longName": "Salesforce Inc", "enterpriseToEbitda": 21.0, "trailingPE": 38.2,
             "marketCap": 253000000000, "ebitda": 12000000000, "trailingEps": 6.93},
}


def _fake_ticker_factory(data):
    def fake_ticker(t):
        fake = MagicMock()
        fake.info = data[t]
        return fake
    return fake_ticker


def test_ev_ebitda_and_pe_regression(monkeypatch):
    """Regression test locking in the exact known-correct values from
    manual verification: peer median EV/EBITDA = 21.0 (median of 18.0,
    25.7, 21.0), implied price = $471.17; peer median P/E = 38.2, implied
    price = $510.35."""
    import comps_valuation
    monkeypatch.setattr(comps_valuation.yf, "Ticker", _fake_ticker_factory(MOCK_DATA))

    result = compute_comps_valuation(
        "MSFT", ["GOOGL", "ORCL", "CRM"],
        target_shares_outstanding=7425545491, target_cash=20935000000, target_debt=56826000000,
    )

    assert result["peer_median_ev_ebitda"] == pytest.approx(21.0, abs=0.01)
    assert result["peer_median_pe"] == pytest.approx(38.2, abs=0.01)
    assert result["implied_price_ev_ebitda"] == pytest.approx(471.17, abs=0.5)
    assert result["implied_price_pe"] == pytest.approx(510.35, abs=0.5)


def test_peer_missing_multiple_is_excluded_from_median(monkeypatch):
    """A peer with no EV/EBITDA or P/E data at all should be silently
    excluded from the median calculation, not crash or poison it with NaN."""
    import comps_valuation
    data_with_gap = dict(MOCK_DATA)
    data_with_gap["WEIRD"] = {"longName": "Weird Co", "enterpriseToEbitda": None,
                                "trailingPE": None, "marketCap": 1000000000,
                                "ebitda": None, "trailingEps": None}
    monkeypatch.setattr(comps_valuation.yf, "Ticker", _fake_ticker_factory(data_with_gap))

    result = compute_comps_valuation(
        "MSFT", ["GOOGL", "WEIRD"],
        target_shares_outstanding=7425545491, target_cash=20935000000, target_debt=56826000000,
    )

    # Only GOOGL has real data, so the median should just be GOOGL's own multiple
    assert result["peer_median_ev_ebitda"] == pytest.approx(18.0, abs=0.01)
    assert result["peer_median_pe"] == pytest.approx(23.1, abs=0.01)


def test_range_low_high_bracket_the_median(monkeypatch):
    """The low/high implied price range should genuinely bracket the
    median implied price - i.e. low <= median <= high, sanity-checking the
    min/max multiple logic isn't inverted."""
    import comps_valuation
    monkeypatch.setattr(comps_valuation.yf, "Ticker", _fake_ticker_factory(MOCK_DATA))

    result = compute_comps_valuation(
        "MSFT", ["GOOGL", "ORCL", "CRM"],
        target_shares_outstanding=7425545491, target_cash=20935000000, target_debt=56826000000,
    )

    assert result["implied_price_ev_ebitda_low"] <= result["implied_price_ev_ebitda"] <= result["implied_price_ev_ebitda_high"]
    assert result["implied_price_pe_low"] <= result["implied_price_pe"] <= result["implied_price_pe_high"]
