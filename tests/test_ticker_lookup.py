"""
Tests for ticker_lookup.py
"""

from unittest.mock import patch, MagicMock
from ticker_lookup import looks_like_ticker, resolve_ticker_candidates, has_manual_alias


def test_short_alnum_input_looks_like_ticker():
    assert looks_like_ticker("MSFT")
    assert looks_like_ticker("BRK.B")
    assert looks_like_ticker("msft")


def test_looks_like_ticker_false_positives_confirmed_real_bug():
    """Real bug: both 'LVMH' (4 chars) and 'Hermes' (exactly 6 chars, the
    upper bound of the ticker-shaped regex) pass looks_like_ticker() even
    though neither is a real Yahoo Finance symbol. This is exactly why the
    caller (app.py) must also check has_manual_alias() before deciding to
    skip the search lookup - looks_like_ticker() alone isn't enough."""
    assert looks_like_ticker("LVMH")
    assert looks_like_ticker("Hermes")


def test_has_manual_alias_catches_known_false_positive_tickers():
    assert has_manual_alias("LVMH")
    assert has_manual_alias("Hermes")
    assert has_manual_alias("  hermès  ")
    assert not has_manual_alias("MSFT")
    assert not has_manual_alias("Procter and Gamble")


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
    with patch("ticker_lookup.time.sleep"), \
         patch("yfinance.Search", side_effect=Exception("network error")):
        candidates = resolve_ticker_candidates("Microsoft")
    assert candidates == []


def test_resolve_ticker_candidates_retries_once_after_transient_failure():
    """A one-off connection hiccup (common on Yahoo Finance's search
    endpoint, especially from shared-IP hosting) shouldn't produce a false
    'no match found' for a real company - one retry should recover it."""
    mock_search = MagicMock()
    mock_search.quotes = [{"symbol": "MSFT", "shortname": "Microsoft Corporation"}]
    with patch("ticker_lookup.time.sleep"), \
         patch("yfinance.Search", side_effect=[Exception("transient error"), mock_search]):
        candidates = resolve_ticker_candidates("Microsoft")
    assert candidates == [{"symbol": "MSFT", "name": "Microsoft Corporation"}]


def test_resolve_ticker_candidates_gives_up_after_exhausting_retries():
    """A persistent failure (not just one-off) should still degrade to an
    empty list rather than retry forever or raise."""
    with patch("ticker_lookup.time.sleep"), \
         patch("yfinance.Search", side_effect=Exception("still down")) as mock_search_cls:
        candidates = resolve_ticker_candidates("Microsoft")
    assert candidates == []
    assert mock_search_cls.call_count == 2  # attempted twice, then gave up


def test_resolve_ticker_candidates_enables_fuzzy_matching():
    """Real bug reported via manual testing: searching 'Hermes' (plain
    ASCII, as any user would type it) returned zero matches, even though
    the company's official name is 'Hermès International' (with the
    accent). yfinance's Search defaults to enable_fuzzy_query=False -
    without it, an exact/literal match against the accented official name
    can fail. This must be explicitly turned on."""
    mock_search = MagicMock()
    mock_search.quotes = [{"symbol": "RMS.PA", "shortname": "Hermès International"}]
    with patch("yfinance.Search", return_value=mock_search) as mock_search_cls:
        resolve_ticker_candidates("Hermes")
    _, kwargs = mock_search_cls.call_args
    assert kwargs.get("enable_fuzzy_query") is True


def test_manual_alias_resolves_hermes_even_if_live_search_fails():
    """Confirmed real-world case (still failing even with fuzzy matching
    enabled): Yahoo's search just doesn't reliably surface Hermès
    International under the common English spelling 'Hermes'. The manual
    alias table guarantees this well-known name resolves regardless of
    what Yahoo's search returns - even a total search failure."""
    with patch("ticker_lookup.time.sleep"), \
         patch("yfinance.Search", side_effect=Exception("still no match")):
        candidates = resolve_ticker_candidates("Hermes")
    assert {"symbol": "RMS.PA", "name": "Hermès International"} in candidates


def test_manual_alias_lookup_is_case_and_accent_insensitive():
    with patch("yfinance.Search", side_effect=Exception("down")):
        assert resolve_ticker_candidates("  HERMES  ")[0]["symbol"] == "RMS.PA"
        assert resolve_ticker_candidates("Hermès")[0]["symbol"] == "RMS.PA"


def test_manual_alias_does_not_duplicate_when_search_also_returns_it():
    """If Yahoo's own search does return the same symbol, it should be
    merged, not duplicated."""
    mock_search = MagicMock()
    mock_search.quotes = [{"symbol": "RMS.PA", "shortname": "Hermès International"}]
    with patch("yfinance.Search", return_value=mock_search):
        candidates = resolve_ticker_candidates("Hermes")
    assert len([c for c in candidates if c["symbol"] == "RMS.PA"]) == 1


def test_manual_alias_resolves_lvmh_by_symbol_lookup_too():
    """LVMH is the second confirmed real case: 'LVMH' is 4 characters, so
    it also passes looks_like_ticker() as a false positive, but MC.PA (not
    'LVMH') is the actual Yahoo Finance symbol."""
    with patch("yfinance.Search", side_effect=Exception("down")):
        candidates = resolve_ticker_candidates("LVMH")
    assert candidates[0] == {"symbol": "MC.PA", "name": "LVMH Moët Hennessy Louis Vuitton"}


def test_manual_alias_does_not_apply_to_unrelated_queries():
    """The alias table must not shadow a genuine, unrelated live search
    result for anything not explicitly in the list."""
    mock_search = MagicMock()
    mock_search.quotes = [{"symbol": "MSFT", "shortname": "Microsoft Corporation"}]
    with patch("yfinance.Search", return_value=mock_search):
        candidates = resolve_ticker_candidates("Microsoft")
    assert candidates == [{"symbol": "MSFT", "name": "Microsoft Corporation"}]
