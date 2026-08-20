"""
Diagnostic tool: list every available financial statement field for a ticker.

Use this whenever get_dcf_inputs() reports a '[!] not found' warning - it'll
show you what the company's data is ACTUALLY called, so you can add the
correct field name (or an alias) to step2_get_financials.py.
"""

import sys
import yfinance as yf


def inspect_fields(ticker: str):
    stock = yf.Ticker(ticker)

    print(f"=== {ticker}: Income Statement fields ===")
    print(list(stock.income_stmt.index))

    print(f"\n=== {ticker}: Balance Sheet fields ===")
    print(list(stock.balance_sheet.index))

    print(f"\n=== {ticker}: Cash Flow fields ===")
    print(list(stock.cash_flow.index))


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "O"
    inspect_fields(ticker)
