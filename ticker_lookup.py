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

# A ticker symbol is short, has no spaces, and is built from letters,
# digits, dots (e.g. BRK.B) or hyphens - a company name virtually never
# matches this (it has spaces, or is longer than a handful of characters).
_TICKER_LIKE = re.compile(r"^[A-Za-z0-9.\-]{1,6}$")


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

    try:
        from yfinance import Search
        quotes = Search(query, max_results=max_results).quotes
    except Exception as e:
        print(f"  [!] Ticker search failed for '{query}': {e}")
        return []

    candidates = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol:
            continue
        name = q.get("shortname") or q.get("longname") or symbol
        candidates.append({"symbol": symbol, "name": name})
    return candidates
