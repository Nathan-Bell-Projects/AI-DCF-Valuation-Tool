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
import unicodedata

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

# Confirmed real case (manual testing): searching "Hermes" - the plain-
# ASCII spelling anyone would actually type - returns no match at all,
# even with enable_fuzzy_query=True. The company's officially listed name
# is "Hermès International" (with the accent), and a few other famous
# global brands have the same accented-legal-name vs. plain-English-brand
# gap. Rather than being at the mercy of Yahoo's search relevance for a
# handful of household names someone evaluating this tool is very likely
# to try, this is a small manual override, checked first and merged ahead
# of whatever the live search returns (never instead of it, so a genuine
# improvement in Yahoo's own search still surfaces additional matches).
#
# Also covers a broader, confirmed-real pattern: a company's common name
# is often short enough to itself pass looks_like_ticker() (<=6 letters,
# no spaces) while NOT being its actual ticker - "Tesla" (5 letters) is
# not "TESLA", it's TSLA; "Nvidia" (6 letters) is not "NVIDIA", it's
# NVDA. app.py now also self-heals this generally (see the fallback in
# app.py's run_button handler: if the literal input pulls no data, it
# retries as a company-name search automatically) - these entries are a
# faster, no-network-round-trip path for the specific names already
# confirmed to trip this, including a common misspelling.
_MANUAL_ALIASES = {
    "hermes": ("RMS.PA", "Hermès International"),
    "loreal": ("OR.PA", "L'Oréal S.A."),
    "lvmh": ("MC.PA", "LVMH Moët Hennessy Louis Vuitton"),
    "nestle": ("NESN.SW", "Nestlé S.A."),
    "tesla": ("TSLA", "Tesla, Inc."),
    "nvidia": ("NVDA", "NVIDIA Corporation"),
    "nvidea": ("NVDA", "NVIDIA Corporation"),  # confirmed real misspelling
}


def _normalize(text: str) -> str:
    """Lowercases, strips accents (so 'Hermès' and 'Hermes' both become
    'hermes'), and drops everything but letters/digits - so 'Hermès',
    'hermes', and 'HERMES!' all key into the same alias entry."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


def looks_like_ticker(query: str) -> bool:
    """True if the input already looks like a ticker symbol rather than a
    company name - used to skip the search lookup entirely for the common
    case where the user already knows the ticker."""
    return bool(_TICKER_LIKE.match(query.strip()))


def has_manual_alias(query: str) -> bool:
    """True if this input matches a known manual override (see
    _MANUAL_ALIASES above).

    Confirmed real bug: 'LVMH' and 'Hermes' are both short enough (4 and
    exactly 6 characters) to pass looks_like_ticker() and get treated as a
    literal ticker symbol - skipping the lookup entirely, even though
    neither is actually a valid Yahoo Finance symbol (LVMH's real ticker
    is MC.PA; 'HERMES' isn't a symbol at all). The caller needs to check
    this BEFORE deciding to skip the lookup based on looks_like_ticker()
    alone, or these known-good aliases never get a chance to run."""
    return _normalize(query) in _MANUAL_ALIASES


def resolve_ticker_candidates(query: str, max_results: int = 5) -> list:
    """Search Yahoo Finance for tickers matching a company name (or partial
    ticker). Returns a list of {"symbol": ..., "name": ...} dicts, most
    relevant first. Returns an empty list (never raises) if the search
    fails or matches nothing - callers should fall back to treating the
    raw input as a ticker directly in that case."""
    query = query.strip()
    if not query:
        return []

    candidates = []
    seen_symbols = set()

    alias = _MANUAL_ALIASES.get(_normalize(query))
    if alias:
        symbol, name = alias
        candidates.append({"symbol": symbol, "name": name})
        seen_symbols.add(symbol)

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
        if not candidates:
            print(f"  [!] Ticker search failed for '{query}' after "
                  f"{_SEARCH_RETRY_ATTEMPTS} attempts: {last_error}")
        return candidates

    for q in quotes:
        symbol = q.get("symbol")
        if not symbol or symbol in seen_symbols:
            continue
        name = q.get("shortname") or q.get("longname") or symbol
        candidates.append({"symbol": symbol, "name": name})
        seen_symbols.add(symbol)
    return candidates
