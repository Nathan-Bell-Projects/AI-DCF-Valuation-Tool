"""
Ticker lookup: resolve a company name to its ticker symbol
------------------------------------------------------------------
Lets a Streamlit user type a company name (e.g. "Microsoft") instead of
needing to already know its ticker (e.g. "MSFT"). Uses yfinance's own
`Search` wrapper around Yahoo Finance's search endpoint - free, no API
key, same data source as the rest of this project.

Only engaged for input that doesn't already look like a ticker symbol
(short, no spaces) - the common case of a user who already knows the
ticker never pays for an extra network round-trip or risks a search
hiccup blocking them. Same "degrade gracefully, never crash" philosophy
as step2_get_financials.py: a failed or empty search just means the
caller falls back to treating the raw input as a ticker directly.
"""

import re
import time

# A ticker symbol is short, has no spaces, and is built from letters,
# digits, dots (e.g. BRK.B) or hyphens - a company name virtually never
# matches this (it has spaces, or is longer than a handful of characters).
_TICKER_LIKE = re.compile(r"^[A-Za-z0-9.\-]{1,6}$")

# Yahoo Finance's search endpoint occasionally fails with a transient
# connection or rate-limit error even for a perfectly normal query - more
# likely on shared-IP hosting like Streamlit Community Cloud, where many
# unrelated visitors' traffic can trip Yahoo's rate limiting. One short
# retry turns a one-off hiccup into a successful lookup instead of a false
# "no match found" for a real, valid company name.
_SEARCH_RETRY_ATTEMPTS = 2
_SEARCH_RETRY_DELAY_SECONDS = 1.5


def looks_like_ticker(query: str) -> bool:
    """True if the input already looks like a ticker symbol rather than a
    company name - used to skip the search lookup entirely for the common
    case where the user already knows the ticker."""
    return bool(_TICKER_LIKE.match(query.strip()))


def resolve_ticker_candidates(query: str, max_results: int = 5) -> list:
    """Search Yahoo Finance for tickers matching a company name (or partial
    ticker). Returns a list of {"symbol": ..., "name": ...} dicts, most
    relevant first. Returns an empty list (never raises) if the search
    fails or matches nothing - callers should fall back to treating the
    raw input as a ticker directly in that case."""
    query = query.strip()
    if not query:
        return []

    from yfinance import Search
    quotes = None
    last_error = None
    for attempt in range(_SEARCH_RETRY_ATTEMPTS):
        try:
            # enable_fuzzy_query lets Yahoo's search match approximate/
            # partial spellings - without it (yfinance's own default),
            # an accented official name like "Hermès International" can
            # fail to match the plain-ASCII "Hermes" a user actually types.
            quotes = Search(query, max_results=max_results, enable_fuzzy_query=True).quotes
            break
        except Exception as e:
            last_error = e
            if attempt < _SEARCH_RETRY_ATTEMPTS - 1:
                time.sleep(_SEARCH_RETRY_DELAY_SECONDS)

    if quotes is None:
        print(f"  [!] Ticker search failed for '{query}' after "
              f"{_SEARCH_RETRY_ATTEMPTS} attempts: {last_error}")
        return []

    candidates = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol:
            continue
        name = q.get("shortname") or q.get("longname") or symbol
        candidates.append({"symbol": symbol, "name": name})
    return candidates
