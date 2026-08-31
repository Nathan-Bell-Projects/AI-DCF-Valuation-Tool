"""
Price history chart helpers
------------------------------------------------------------------
Pure, testable logic behind the price chart's range selector (1M / 6M /
YTD / 1Y / 5Y): slicing an already-fetched daily price series down to the
requested window, and computing the change/color info a Yahoo-Finance-
style chart header shows (current value, absolute and percent change, and
whether it's a net gain - which drives the red/green line color).

Deliberately kept intraday ranges (1D / 5D) OUT of scope. Those need
minute-level data, which is far less reliable via yfinance's free
intraday endpoint than the daily closes used here - it can come back
empty outside market hours, on weekends, or for illiquid/foreign-listed
tickers, and gets rate-limited more aggressively than daily data. Every
range below reuses the exact same daily-close data source the rest of
this app already depends on, so it doesn't introduce a new failure mode.

app.py fetches ONE 5-year daily history per "Run Analysis" click (cheap,
one API call) and this module just slices/summarizes it - changing the
selected range re-runs the whole analysis (same interaction model as
every other sidebar control, e.g. the WACC slider) rather than updating
instantly like Yahoo's own chart. That's a deliberate trade: an instant
in-place toggle needs Streamlit session-state plumbing across the whole
results section, which is a much bigger change with more surface area
for something to break - not worth the risk this close to a deadline.
"""

import pandas as pd

PERIOD_OPTIONS = ["1M", "6M", "YTD", "1Y", "5Y"]
DEFAULT_PERIOD = "1Y"

_PERIOD_LOOKBACK_DAYS = {
    "1M": 30,
    "6M": 182,
    "1Y": 365,
    "5Y": 365 * 5,
}


def filter_history_by_period(history: pd.Series, period: str) -> pd.Series:
    """Slice a daily price history (DatetimeIndex) down to the requested
    display window. YTD is calendar-year-to-date; every other range is a
    fixed lookback in calendar days, measured from the series' own last
    date (not "today") so this still works correctly on slightly stale
    data. Unknown periods fall back to a 1-year lookback rather than
    raising, matching this project's "degrade gracefully" convention."""
    if history.empty:
        return history
    end = history.index.max()
    if period == "YTD":
        start = pd.Timestamp(year=end.year, month=1, day=1, tz=end.tz)
    else:
        days = _PERIOD_LOOKBACK_DAYS.get(period, 365)
        start = end - pd.Timedelta(days=days)
    return history[history.index >= start]


def compute_price_change(history: pd.Series) -> dict:
    """First/last price and the absolute + percent change between them
    over the given series - the numbers a Yahoo-Finance-style header
    (current value, colored delta) needs.

    'positive' drives the red/green line color; a flat/zero change counts
    as positive (green), matching this app's existing upside/downside
    metric convention elsewhere. With fewer than 2 points there's no
    "change" to compute - returns whatever single price is available
    (for display) with change/pct_change as None, rather than raising or
    dividing by zero."""
    if history.empty:
        return {"first": None, "last": None, "change": None, "pct_change": None, "positive": True}
    if len(history) < 2:
        return {"first": None, "last": float(history.iloc[-1]),
                 "change": None, "pct_change": None, "positive": True}
    first = float(history.iloc[0])
    last = float(history.iloc[-1])
    change = last - first
    pct_change = (change / first) if first else None
    return {"first": first, "last": last, "change": change, "pct_change": pct_change, "positive": change >= 0}
