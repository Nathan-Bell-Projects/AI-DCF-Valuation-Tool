"""
Scenario planning: Base / Upside / Downside, grounded in real historical data
------------------------------------------------------------------------------------
Repositions the DCF's core assumption philosophy: historical data is a
STARTING POINT for judgment, not automatically the forecast itself. This is
standard corporate finance / FP&A practice (as opposed to the pure
investment-analysis framing the rest of this project's DCF machinery uses).

Critically, Upside and Downside are NOT arbitrary percentages picked to look
plausible - they're derived directly from the company's own actual
historical range:
  - Base case = historical median (unchanged from the rest of the project)
  - Upside = the company's own best historical year (highest growth/margin,
    lowest capex intensity)
  - Downside = the company's own worst historical year (lowest growth/
    margin, highest capex intensity)

Every number in every scenario is something that actually happened to this
company - nothing here is fabricated, consistent with this project's
existing standard of using only real, verifiable data.
"""

import pandas as pd
from step3_dcf_engine import get_historical_assumptions, run_dcf_scenario


def build_scenario_assumptions(df: pd.DataFrame) -> dict:
    """Returns Base/Upside/Downside assumption sets, each derived from real
    historical data - plus the underlying historical range, so the
    methodology is fully auditable (not a black box)."""

    years = sorted(df.dropna(axis=1, how="all").columns)
    revenues = df.loc["Revenue", years]
    ebit = df.loc["EBIT", years]
    capex = df.loc["Capex", years]

    growth_rates = revenues.pct_change().dropna()
    margins = ebit / revenues
    capex_pct = capex.abs() / revenues

    base_assumptions = get_historical_assumptions(df, method="median")

    # Upside: this company's own best historical year on each metric -
    # higher growth, higher margin, LOWER capex intensity (capex is a cash
    # outflow, so "optimistic" means less of it, not more).
    upside_assumptions = dict(base_assumptions)
    upside_assumptions["avg_revenue_growth"] = growth_rates.max()
    upside_assumptions["avg_ebit_margin"] = margins.max()
    upside_assumptions["avg_capex_pct_revenue"] = capex_pct.min()

    # Downside: this company's own worst historical year on each metric.
    downside_assumptions = dict(base_assumptions)
    downside_assumptions["avg_revenue_growth"] = growth_rates.min()
    downside_assumptions["avg_ebit_margin"] = margins.min()
    downside_assumptions["avg_capex_pct_revenue"] = capex_pct.max()

    return {
        "base": base_assumptions,
        "upside": upside_assumptions,
        "downside": downside_assumptions,
        # The underlying historical range, kept for display - so a reader
        # can see exactly which real year each scenario's numbers came from,
        # not just trust the labels.
        "historical_range": {
            "growth_min": growth_rates.min(), "growth_median": growth_rates.median(), "growth_max": growth_rates.max(),
            "margin_min": margins.min(), "margin_median": margins.median(), "margin_max": margins.max(),
            "capex_pct_min": capex_pct.min(), "capex_pct_median": capex_pct.median(), "capex_pct_max": capex_pct.max(),
        },
    }


def run_scenario_valuations(df: pd.DataFrame, cash: float, total_debt: float,
                              shares_outstanding: float, wacc: float, terminal_growth: float) -> dict:
    """Runs the full DCF under all three scenarios and returns the implied
    share price for each, using the SAME WACC/terminal growth across all
    three - isolating the effect of the operating assumptions themselves,
    not conflating it with a different discount rate per scenario."""

    scenarios = build_scenario_assumptions(df)
    results = {}

    for label in ["base", "upside", "downside"]:
        assumptions = scenarios[label]
        overrides = {
            "avg_revenue_growth": assumptions["avg_revenue_growth"],
            "avg_ebit_margin": assumptions["avg_ebit_margin"],
            "avg_capex_pct_revenue": assumptions["avg_capex_pct_revenue"],
        }
        run = run_dcf_scenario(
            df, cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
            wacc=wacc, terminal_growth=terminal_growth, overrides=overrides, verbose=False,
        )
        results[label] = {
            "assumptions": assumptions,
            "implied_price": run["result"]["implied_share_price"],
        }

    results["historical_range"] = scenarios["historical_range"]
    return results


if __name__ == "__main__":
    import sys
    from step2_get_financials import get_dcf_inputs
    import yfinance as yf

    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    print(f"Building data-driven scenarios for {ticker}...\n")

    df = get_dcf_inputs(ticker)
    stock_info = yf.Ticker(ticker).info
    shares_outstanding = stock_info.get("sharesOutstanding")
    current_price = stock_info.get("currentPrice")

    assumptions = get_historical_assumptions(df)
    latest_year = assumptions["latest_year"]
    cash = df.loc["Cash", latest_year]
    total_debt = df.loc["Total Debt", latest_year]

    results = run_scenario_valuations(df, cash, total_debt, shares_outstanding, wacc=0.09, terminal_growth=0.025)

    for label in ["downside", "base", "upside"]:
        a = results[label]["assumptions"]
        print(f"--- {label.upper()} ---")
        print(f"  Growth: {a['avg_revenue_growth']:.1%}, Margin: {a['avg_ebit_margin']:.1%}, "
              f"Capex: {a['avg_capex_pct_revenue']:.1%}")
        print(f"  Implied price: ${results[label]['implied_price']:.2f}")
    print(f"\nCurrent market price: ${current_price:.2f}")
