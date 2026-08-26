"""
Tests for ticker_lookup.py
"""

from unittest.mock import patch, MagicMock
from ticker_lookup import looks_like_ticker, resolve_ticker_candidates


def test_short_alnum_input_looks_like_ticker():
    assert looks_like_ticker("MSFT")
    assert looks_like_ticker("BRK.B")
    assert looks_like_ticker("msft")


def test_company_name_does_not_look_like_ticker():
    """Company names have spaces or run longer than a real-world ticker -
    both should route to the search lookup instead of being used directly."""
    assert not looks_like_ticker("Microsoft")
    assert not looks_like_ticker("Procter and Gamble")
    assert not looks_like_ticker("")


def test_resolve_ticker_candidates_parses_quotes():
    """Only quotes with a symbol are kept (mirrors yfinance's own Search,
    which already filters out symbol-less entries); name falls back from
    shortname to longname to the symbol itself."""
    mock_search = MagicMock()
    mock_search.quotes = [
        {"symbol": "MSFT", "shortname": "Microsoft Corporation"},
        {"symbol": "MSF.DE", "longname": "Microsoft Corp (XETRA)"},
        {"symbol": "WEIRD"},  # no name field at all - should fall back to the symbol
    ]
    with patch("yfinance.Search", return_value=mock_search):
        candidates = resolve_ticker_candidates("Microsoft")

    assert candidates == [
        {"symbol": "MSFT", "name": "Microsoft Corporation"},
        {"symbol": "MSF.DE", "name": "Microsoft Corp (XETRA)"},
        {"symbol": "WEIRD", "name": "WEIRD"},
    ]


def test_resolve_ticker_candidates_empty_query_returns_empty_without_network_call():
    with patch("yfinance.Search") as mock_search_cls:
        assert resolve_ticker_candidates("") == []
        assert resolve_ticker_candidates("   ") == []
        mock_search_cls.assert_not_called()


def test_resolve_ticker_candidates_handles_search_failure_gracefully():
    """A network error or bad response must not crash the caller - same
    defensive contract as the rest of this project's data-pulling code."""
    with patch("yfinance.Search", side_effect=Exception("network error")):
        candidates = resolve_ticker_candidates("Microsoft")
    assert candidates == []
