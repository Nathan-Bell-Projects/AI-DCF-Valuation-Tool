"""
Step 2: Pull & clean financial data
---------------------------------------
yfinance gives you three separate statements, each as its own table
(technically a pandas DataFrame): income statement, balance sheet, and
cash flow statement. Each one has years as columns and line items as rows.

Our job here is simple: pull out ONLY the specific lines the DCF actually
needs, and put them together in one clean, readable table.
"""

import yfinance as yf
import pandas as pd


def get_dcf_inputs(ticker: str) -> pd.DataFrame:
    """Pull the financial statement lines needed for a DCF, for one ticker.
    Returns a DataFrame with years as columns and metrics as rows."""

    stock = yf.Ticker(ticker)

    # Each of these is a separate table, most recent year first (column 0)
    income_stmt = stock.income_stmt
    balance_sheet = stock.balance_sheet
    cash_flow = stock.cash_flow

    # Helper to safely pull a row by name, and handle it if yfinance
    # doesn't have that exact line item for this company (common - not
    # every company reports every line the same way)
    def safe_get(df: pd.DataFrame, row_names) -> pd.Series:
        """Accepts either a single field name (str) or a list of candidate
        names to try in order - useful because different companies/sectors
        use different terminology for economically similar line items (e.g.
        a REIT's 'Purchase Of Investment Properties' is its version of
        'Capital Expenditure'). Returns the first match found."""
        if isinstance(row_names, str):
            row_names = [row_names]

        for name in row_names:
            if name in df.index:
                return df.loc[name]

        print(f"  [!] None of {row_names} found - filling with NaN")
        return pd.Series([float("nan")] * len(df.columns), index=df.columns)

    # Pull exactly the lines a basic DCF needs
    data = {
        "Revenue": safe_get(income_stmt, "Total Revenue"),
        "EBIT": safe_get(income_stmt, "EBIT"),
        "Net Income": safe_get(income_stmt, "Net Income"),
        "D&A": safe_get(cash_flow, "Depreciation And Amortization"),
        # Capex has different names across sectors - a REIT (e.g. Realty
        # Income) doesn't have "Capital Expenditure" at all; its equivalent
        # is buying real estate. Try the standard name first, fall back to
        # sector-specific alternatives.
        "Capex": safe_get(cash_flow, [
            "Capital Expenditure",
            "Purchase Of Investment Properties",
            "Purchase Of Business",
        ]),
        "Cash": safe_get(balance_sheet, "Cash And Cash Equivalents"),
        "Total Debt": safe_get(balance_sheet, "Total Debt"),
        # Added for net working capital (NWC), per the CFI template comparison -
        # NWC = (Current Assets - Cash) - Current Liabilities
        "Current Assets": safe_get(balance_sheet, "Current Assets"),
        "Current Liabilities": safe_get(balance_sheet, "Current Liabilities"),
        # Added for CAPM-based WACC: used to estimate pre-tax cost of debt
        # (Interest Expense / Total Debt)
        "Interest Expense": safe_get(income_stmt, [
            "Interest Expense",
            "Interest Expense Non Operating",
            "Net Interest Income",
        ]),
    }

    df = pd.DataFrame(data)
    # yfinance gives years as rows here after this construction - flip so
    # metrics are rows and years are columns, which is more natural to read
    df = df.T
    # Clean up column headers to just show the year, not full timestamps
    df.columns = [str(col)[:4] for col in df.columns]

    return df


def check_currency_mismatch(stock_info: dict) -> dict:
    """yfinance separates a company's TRADING currency (what the stock price
    is quoted in, e.g. USD for a US-listed ADR) from its FINANCIAL currency
    (what the underlying financial statements are reported in, e.g. JPY for
    Sony Group). When these differ, the DCF's enterprise/equity value is
    calculated in one currency and then divided by a share count implicitly
    tied to the other - producing a wildly wrong implied price with no
    error, no crash, just a silently nonsensical number.

    This was found in exactly this form when testing SONY: implied price
    came back at 25,000%+ "upside" versus the real market price, because
    revenue/EBIT were in JPY while shares outstanding/current price were
    USD-based. Unlike the REIT negative-price case (a genuine methodology
    mismatch), this is a pure unit error - the fix is to detect and warn,
    not to explain away."""
    trading_currency = stock_info.get("currency")
    financial_currency = stock_info.get("financialCurrency")
    mismatch = (
        trading_currency is not None
        and financial_currency is not None
        and trading_currency != financial_currency
    )
    return {
        "mismatch": mismatch,
        "trading_currency": trading_currency,
        "financial_currency": financial_currency,
    }


def get_current_price_and_shares(stock_info: dict) -> tuple:
    """Pull current share price and shares outstanding from yfinance's
    `.info` dict, with fallbacks.

    'currentPrice' is really a "real-time US-listed quote" field - it's
    commonly left unpopulated for a lot of otherwise perfectly valid,
    liquid tickers (most non-US primary listings such as Euronext or the
    LSE, and occasionally even a US ticker during a temporary Yahoo
    Finance API hiccup). Falling back to 'regularMarketPrice' and then
    'previousClose' means a real ticker with real financial data isn't
    treated as unsupported just because that one specific field wasn't
    populated on this particular call.

    Same idea for share count: 'impliedSharesOutstanding' is a reasonable
    fallback when 'sharesOutstanding' itself is missing."""
    price = (
        stock_info.get("currentPrice")
        or stock_info.get("regularMarketPrice")
        or stock_info.get("previousClose")
    )
    shares = (
        stock_info.get("sharesOutstanding")
        or stock_info.get("impliedSharesOutstanding")
    )
    return price, shares


_CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CNY": "¥", "CHF": "CHF ", "CAD": "C$", "AUD": "A$", "HKD": "HK$",
    "SEK": "kr ", "NOK": "kr ", "DKK": "kr ", "INR": "₹", "KRW": "₩",
    "BRL": "R$", "SGD": "S$",
}


def currency_symbol(currency_code: str) -> str:
    """Best-effort display symbol for a currency code, for showing prices
    in the currency the DCF was actually computed in (the ticker's trading
    currency) rather than always hardcoding '$'. Falls back to the raw
    code plus a space for anything not in the common list - still
    unambiguous, just less pretty than a native symbol."""
    if not currency_code:
        return "$"
    return _CURRENCY_SYMBOLS.get(currency_code, f"{currency_code} ")


if __name__ == "__main__":
    ticker = "MSFT"
    print(f"Pulling financial data for {ticker}...\n")
    df = get_dcf_inputs(ticker)
    print(df)
