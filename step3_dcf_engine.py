"""
Step 3: DCF engine
-----------------------
This is the real financial logic of the project. It takes the historical
data from Step 2 and:
  1. Derives reasonable forecast assumptions from the historical trend
  2. Forecasts 5 years of free cash flow
  3. Discounts those cash flows back to today using WACC
  4. Calculates a terminal value for everything beyond year 5
  5. Converts total firm value into an implied share price

Every formula here should look familiar from your BNP Paribas Fortis DCF
work - we're just writing it as code instead of Excel formulas.
"""

import pandas as pd
from step2_get_financials import get_dcf_inputs
from config import DEFAULT_TAX_RATE, DEFAULT_WACC, DEFAULT_TERMINAL_GROWTH, DEFAULT_FORECAST_YEARS


# ---------------------------------------------------------------
# 1. Derive assumptions from historical data
# ---------------------------------------------------------------
def get_historical_assumptions(df: pd.DataFrame, method: str = "median",
                                 overrides: dict = None, verbose: bool = True) -> dict:
    """Look at the last few actual years and derive reasonable forecast
    assumptions: revenue growth, EBIT margin, capex as % of revenue,
    D&A as % of revenue.

    method: "mean" or "median". Median is the default because a single
    anomalous year (e.g. a capex spike from a one-time AI infrastructure
    buildout) skews a mean much more than a median - this is the fix for
    the distorted capex assumption we found.

    overrides: optional dict to manually force specific assumption values,
    e.g. {"avg_capex_pct_revenue": 0.15}. Anything you pass here wins over
    the historically-derived number. This is also the hook the AI-assisted
    layer will use later - it'll suggest values that get passed in here.

    verbose: set False to suppress the '[override] ...' print line - added
    for Monte Carlo simulation, which calls this thousands of times and
    would otherwise flood the terminal with an unreadable wall of text."""

    df = df.dropna(axis=1, how="all")
    years = sorted(df.columns)

    revenues = df.loc["Revenue", years]
    ebit = df.loc["EBIT", years]
    capex = df.loc["Capex", years]
    da = df.loc["D&A", years]

    # Net Working Capital = (Current Assets - Cash) - Current Liabilities.
    # Added after benchmarking against a CFI DCF template, which flagged this
    # as a standard adjustment our v1 was missing. A growing company usually
    # ties up MORE cash in working capital (receivables, inventory), so this
    # is a real cash outflow that pure NOPAT + D&A - Capex misses.
    current_assets = df.loc["Current Assets", years]
    current_liabilities = df.loc["Current Liabilities", years]
    cash_row = df.loc["Cash", years]
    nwc = (current_assets - cash_row) - current_liabilities
    nwc_pct_revenue = nwc / revenues

    growth_rates = revenues.pct_change().dropna()
    ebit_margins = ebit / revenues
    capex_pct = capex.abs() / revenues
    da_pct = da / revenues

    agg = growth_rates.median if method == "median" else growth_rates.mean

    assumptions = {
        "avg_revenue_growth": agg(),
        "avg_ebit_margin": (ebit_margins.median() if method == "median" else ebit_margins.mean()),
        "avg_capex_pct_revenue": (capex_pct.median() if method == "median" else capex_pct.mean()),
        "avg_da_pct_revenue": (da_pct.median() if method == "median" else da_pct.mean()),
        "avg_nwc_pct_revenue": (nwc_pct_revenue.median() if method == "median" else nwc_pct_revenue.mean()),
        "latest_nwc": nwc.iloc[-1],
        "latest_revenue": revenues.iloc[-1],
        "latest_year": years[-1],
    }

    # Apply any manual overrides on top of the derived values
    if overrides:
        for key, value in overrides.items():
            if verbose:
                print(f"  [override] {key}: {assumptions.get(key)} -> {value}")
            assumptions[key] = value

    return assumptions


# ---------------------------------------------------------------
# 2. Forecast future free cash flow
# ---------------------------------------------------------------
def forecast_free_cash_flow(assumptions: dict, forecast_years: int = DEFAULT_FORECAST_YEARS,
                              tax_rate: float = DEFAULT_TAX_RATE) -> pd.DataFrame:
    """Project revenue, EBIT, and free cash flow forward using the
    assumptions derived above. NOTE: this v1 ignores changes in net
    working capital for simplicity - a documented, defensible
    simplification to mention in your README."""

    rows = []
    revenue = assumptions["latest_revenue"]
    prior_nwc = assumptions["latest_nwc"]  # NWC level at the end of actuals - the
                                             # starting point for measuring change

    for year in range(1, forecast_years + 1):
        revenue = revenue * (1 + assumptions["avg_revenue_growth"])
        ebit = revenue * assumptions["avg_ebit_margin"]
        nopat = ebit * (1 - tax_rate)  # Net Operating Profit After Tax
        da = revenue * assumptions["avg_da_pct_revenue"]
        capex = revenue * assumptions["avg_capex_pct_revenue"]

        # Forecast this year's NWC level, then take the CHANGE vs last year -
        # it's the change (not the level) that represents a cash flow impact
        new_nwc = revenue * assumptions["avg_nwc_pct_revenue"]
        change_in_nwc = new_nwc - prior_nwc
        prior_nwc = new_nwc

        # Free Cash Flow to the Firm = NOPAT + D&A - Capex - Change in NWC
        fcf = nopat + da - capex - change_in_nwc

        rows.append({
            "Year": year,
            "Revenue": revenue,
            "EBIT": ebit,
            "NOPAT": nopat,
            "D&A": da,
            "Capex": capex,
            "Change in NWC": change_in_nwc,
            "FCF": fcf,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------
# 3. Discount cash flows and calculate implied share price
# ---------------------------------------------------------------
def calculate_dcf_valuation(forecast_df: pd.DataFrame, wacc: float,
                              terminal_growth: float, cash: float,
                              total_debt: float, shares_outstanding: float) -> dict:
    """Discount each forecast year's FCF back to present value, add a
    terminal value for everything beyond the forecast period, and derive
    the implied share price."""

    # Present value of each forecasted year's FCF
    forecast_df = forecast_df.copy()
    forecast_df["Discount Factor"] = 1 / (1 + wacc) ** forecast_df["Year"]
    forecast_df["PV of FCF"] = forecast_df["FCF"] * forecast_df["Discount Factor"]

    pv_explicit_period = forecast_df["PV of FCF"].sum()

    # Terminal value: value of all cash flows beyond the forecast period,
    # using the Gordon Growth (perpetuity growth) formula
    final_year_fcf = forecast_df["FCF"].iloc[-1]
    terminal_value = (final_year_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
    pv_terminal_value = terminal_value * forecast_df["Discount Factor"].iloc[-1]

    enterprise_value = pv_explicit_period + pv_terminal_value

    # Bridge from Enterprise Value to Equity Value: add cash, subtract debt
    equity_value = enterprise_value - total_debt + cash

    implied_share_price = equity_value / shares_outstanding

    # Sanity guardrail: a negative implied share price isn't a code bug -
    # it's the model telling you standard DCF likely doesn't fit this
    # company's capital structure (e.g. REITs, whose capex/property
    # purchases are typically funded by debt/equity issuance, not
    # operating cash flow - the core assumption a DCF relies on).
    if implied_share_price < 0:
        print("  [!] WARNING: Negative implied share price. This usually means "
              "capex/investment spending exceeds operating cash flow generation "
              "- common for REITs and other capital-intensive businesses funded "
              "by external financing. Standard DCF may not be the right "
              "valuation method for this company; consider FFO/AFFO multiples "
              "for REITs instead.")

    return {
        "pv_explicit_period": pv_explicit_period,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "implied_share_price": implied_share_price,
        "forecast_detail": forecast_df,
    }


# ---------------------------------------------------------------
# Convenience wrapper: run the full DCF end to end in one call
# ---------------------------------------------------------------
def run_dcf_scenario(df: pd.DataFrame, cash: float, total_debt: float,
                       shares_outstanding: float, wacc: float = DEFAULT_WACC,
                       terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
                       tax_rate: float = DEFAULT_TAX_RATE, method: str = "median",
                       overrides: dict = None, verbose: bool = True) -> dict:
    """Bundles get_historical_assumptions + forecast_free_cash_flow +
    calculate_dcf_valuation into a single call - the single, reusable
    'run a full DCF under these assumptions' entry point. Added during a
    refactor: step5_excel_export.py previously reimplemented this exact
    three-call sequence as a local closure for building its scenario
    comparison table - now both use this one function, so there's a single
    place this logic can be fixed or extended, not two.

    verbose: set False to suppress override print statements - essential
    when this is called in a loop (e.g. Monte Carlo simulation, which
    calls this thousands of times)."""
    assumptions = get_historical_assumptions(df, method=method, overrides=overrides, verbose=verbose)
    forecast_df = forecast_free_cash_flow(assumptions, tax_rate=tax_rate)
    result = calculate_dcf_valuation(
        forecast_df, wacc=wacc, terminal_growth=terminal_growth,
        cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
    )
    return {
        "assumptions": assumptions,
        "forecast_df": forecast_df,
        "result": result,
    }


if __name__ == "__main__":
    import argparse
    import yfinance as yf

    parser = argparse.ArgumentParser(description="Run a DCF valuation for a given ticker.")
    parser.add_argument("--ticker", default="MSFT", help="Stock ticker, e.g. MSFT")
    parser.add_argument("--wacc", type=float, default=DEFAULT_WACC, help="Discount rate, e.g. 0.09 for 9%%")
    parser.add_argument("--terminal-growth", type=float, default=DEFAULT_TERMINAL_GROWTH, dest="terminal_growth",
                         help="Terminal growth rate, e.g. 0.025 for 2.5%%")
    parser.add_argument("--capex-override", type=float, default=None, dest="capex_override",
                         help="Manually set capex as %% of revenue (e.g. 0.15), overriding the "
                              "historical median. Use this to treat an anomalous capex year "
                              "(like a temporary AI infrastructure buildout) as non-recurring.")
    args = parser.parse_args()

    print(f"Running DCF for {args.ticker}...\n")

    df = get_dcf_inputs(args.ticker)

    overrides = {}
    if args.capex_override is not None:
        overrides["avg_capex_pct_revenue"] = args.capex_override

    assumptions = get_historical_assumptions(df, overrides=overrides or None)

    print("--- Derived assumptions ---")
    for k, v in assumptions.items():
        print(f"  {k}: {v}")

    forecast_df = forecast_free_cash_flow(assumptions)
    print("\n--- 5-year forecast ---")
    print(forecast_df.round(0))

    latest_year = assumptions["latest_year"]
    cash = df.loc["Cash", latest_year]
    total_debt = df.loc["Total Debt", latest_year]
    shares_outstanding = yf.Ticker(args.ticker).info.get("sharesOutstanding")

    print("\n--- Pulled real balance sheet figures ---")
    print(f"  Cash: {cash:,.0f}")
    print(f"  Total Debt: {total_debt:,.0f}")
    print(f"  Shares Outstanding: {shares_outstanding:,.0f}")

    result = calculate_dcf_valuation(
        forecast_df,
        wacc=args.wacc,
        terminal_growth=args.terminal_growth,
        cash=cash,
        total_debt=total_debt,
        shares_outstanding=shares_outstanding,
    )

    print("\n--- DCF Result ---")
    print(f"Enterprise Value: {result['enterprise_value']:,.0f}")
    print(f"Equity Value: {result['equity_value']:,.0f}")
    print(f"Implied Share Price: {result['implied_share_price']:,.2f}")
