"""
Analyst data pull
----------------------
Pulls analyst price targets, recommendation trend, and the most recent
individual rating actions (upgrades/downgrades) via yfinance - all free,
no API key needed. This is separate market-context data, distinct from
the AI Valuation Summary (which explains the DCF's OWN output) - this
shows what professional sell-side analysts think, as an independent
reference point.

Same defensive philosophy as step2_get_financials.py: not every ticker
has every field, so each pull is wrapped and degrades gracefully to
"not available" rather than crashing.
"""

import yfinance as yf


def get_analyst_data(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    data = {"price_targets": None, "recommendations": None, "latest_ratings": None}

    try:
        targets = stock.analyst_price_targets
        if targets:
            data["price_targets"] = targets  # dict: current, low, high, mean (median in some versions)
    except Exception as e:
        print(f"  [!] analyst_price_targets not available: {e}")

    try:
        recs = stock.recommendations
        if recs is not None and not recs.empty:
            data["recommendations"] = recs  # DataFrame: period, strongBuy, buy, hold, sell, strongSell
    except Exception as e:
        print(f"  [!] recommendations not available: {e}")

    try:
        upgrades = stock.upgrades_downgrades
        if upgrades is not None and not upgrades.empty:
            # Most recent 5 actions, most recent first
            data["latest_ratings"] = upgrades.sort_index(ascending=False).head(5)
    except Exception as e:
        print(f"  [!] upgrades_downgrades not available: {e}")

    return data


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    print(f"Pulling analyst data for {ticker}...\n")
    result = get_analyst_data(ticker)

    print("--- Price Targets ---")
    print(result["price_targets"])

    print("\n--- Recommendations (most recent rows) ---")
    if result["recommendations"] is not None:
        print(result["recommendations"].head())
    else:
        print("Not available")

    print("\n--- Latest Rating Actions ---")
    if result["latest_ratings"] is not None:
        print(result["latest_ratings"])
    else:
        print("Not available")
