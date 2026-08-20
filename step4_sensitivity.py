"""
Step 4: Sensitivity table
------------------------------
The classic analyst move: instead of trusting one single WACC and one
single terminal growth assumption, show how the implied share price
changes across a reasonable RANGE of both. This is what makes a DCF
defensible in a real conversation - "here's my base case, and here's
how sensitive it is to my assumptions."

We just loop calculate_dcf_valuation() over a grid of WACC and terminal
growth combinations and collect the resulting share price for each.
"""

import pandas as pd
from step3_dcf_engine import (
    get_dcf_inputs,
    get_historical_assumptions,
    forecast_free_cash_flow,
    calculate_dcf_valuation,
)


def build_sensitivity_table(forecast_df: pd.DataFrame, cash: float,
                              total_debt: float, shares_outstanding: float,
                              wacc_range: list, growth_range: list) -> pd.DataFrame:
    """Returns a grid: rows = WACC values, columns = terminal growth values,
    cells = implied share price for that combination."""

    table = pd.DataFrame(index=wacc_range, columns=growth_range, dtype=float)

    for wacc in wacc_range:
        for growth in growth_range:
            # Guard: terminal growth must be lower than WACC, or the Gordon
            # Growth formula breaks (division by zero or negative denominator)
            if growth >= wacc:
                table.loc[wacc, growth] = None
                continue

            result = calculate_dcf_valuation(
                forecast_df, wacc=wacc, terminal_growth=growth,
                cash=cash, total_debt=total_debt,
                shares_outstanding=shares_outstanding,
            )
            table.loc[wacc, growth] = result["implied_share_price"]

    table.index.name = "WACC"
    table.columns.name = "Terminal Growth"
    return table


if __name__ == "__main__":
    import argparse
    import yfinance as yf

    parser = argparse.ArgumentParser(description="Build a WACC/terminal growth sensitivity table.")
    parser.add_argument("--ticker", default="MSFT", help="Stock ticker, e.g. MSFT")
    parser.add_argument("--capex-override", type=float, default=None, dest="capex_override",
                         help="Manually set capex as %% of revenue, overriding the historical median.")
    args = parser.parse_args()

    df = get_dcf_inputs(args.ticker)

    overrides = {"avg_capex_pct_revenue": args.capex_override} if args.capex_override is not None else None
    assumptions = get_historical_assumptions(df, overrides=overrides)
    forecast_df = forecast_free_cash_flow(assumptions)

    latest_year = assumptions["latest_year"]
    cash = df.loc["Cash", latest_year]
    total_debt = df.loc["Total Debt", latest_year]
    shares_outstanding = yf.Ticker(args.ticker).info.get("sharesOutstanding")

    # A reasonable range around your base-case assumptions
    wacc_range = [0.07, 0.08, 0.09, 0.10, 0.11]
    growth_range = [0.015, 0.02, 0.025, 0.03, 0.035]

    sensitivity = build_sensitivity_table(
        forecast_df, cash, total_debt, shares_outstanding,
        wacc_range, growth_range,
    )

    print(f"Sensitivity Table - Implied Share Price ({args.ticker})")
    print(sensitivity.round(2))
