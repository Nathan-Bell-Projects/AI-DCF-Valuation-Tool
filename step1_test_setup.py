"""
Step 1: Environment setup & first data pull
----------------------------------------------
The goal of this file is ONLY to prove the pipeline works end to end:
ticker in -> real data out. No DCF logic yet, no Excel export yet.
Get this working first - everything else builds on top of it.
"""

import yfinance as yf


def test_connection(ticker: str = "MSFT"):
    """Pull basic info for a ticker and print it, to confirm yfinance works."""
    stock = yf.Ticker(ticker)

    # .info is a dictionary with dozens of fields - company overview,
    # current price, market cap, sector, etc.
    info = stock.info

    print(f"Company: {info.get('longName')}")
    print(f"Sector: {info.get('sector')}")
    print(f"Current price: {info.get('currentPrice')}")
    print(f"Market cap: {info.get('marketCap'):,}")
    print(f"Beta: {info.get('beta')}")


if __name__ == "__main__":
    test_connection("MSFT")