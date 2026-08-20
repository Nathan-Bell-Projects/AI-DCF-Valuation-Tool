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
    }

    df = pd.DataFrame(data)
    # yfinance gives years as rows here after this construction - flip so
    # metrics are rows and years are columns, which is more natural to read
    df = df.T
    # Clean up column headers to just show the year, not full timestamps
    df.columns = [str(col)[:4] for col in df.columns]

    return df


if __name__ == "__main__":
    ticker = "MSFT"
    print(f"Pulling financial data for {ticker}...\n")
    df = get_dcf_inputs(ticker)
    print(df)