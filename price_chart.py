"""
Price history chart helpers
------------------------------------------------------------------
Pure, testable logic behind the YTD price chart: computing the change/
color info a Yahoo-Finance-style chart header shows (current value,
absolute and percent change, and whether it's a net gain - which drives
the red/green line color), plus a defensive trim that keeps the chart
locked to the current calendar year.

This module used to back a 1M/6M/YTD/1Y/5Y range selector in the
sidebar. That was dropped in favor of a single, fixed YTD view: every
range change re-ran the whole analysis anyway (Streamlit only applies a
sidebar input on the next "Run Analysis" click, not instantly like
Yahoo's own toggle), so the picker added a sidebar control that looked
like a live toggle but wasn't, without actually saving anything - and an
instant, session-state-backed version would have meant a much bigger
change to app.py's structure for a "nice to have" this close to a
deadline. A single always-YTD view keeps the visual upgrade (colored
trend line, gradient fill, current value with delta) with nothing to
toggle and nothing to break, and it's the fastest option to load too:
app.py asks yfinance for exactly a "ytd" window instead of a full year
or more of daily data.

Intraday ranges (1D / 5D) were never in scope for the same reason they
still aren't: minute-level data is far less reliable via yfinance's free
intraday endpoint than the daily closes used here.
"""

import pandas as pd


def filter_to_ytd(history: pd.Series) -> pd.Series:
    """Defensive trim, not the primary mechanism: app.py already asks
    yfinance for period="ytd" directly, which should return only this
    calendar year's daily closes. This just guards against yfinance
    handing back a stray extra row by trimming to the latest date's own
    calendar year - measured from the series' own last date (not
    "today"), so it stays correct even on slightly stale data."""
    if history.empty:
        return history
    end = history.index.max()
    start = pd.Timestamp(year=end.year, month=1, day=1, tz=end.tz)
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
