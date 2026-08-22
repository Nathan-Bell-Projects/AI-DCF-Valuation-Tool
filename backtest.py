"""
Backtesting: does the core assumption methodology actually work?
------------------------------------------------------------------------
Every forecast in this project is built on one core idea: historical
median growth/margin is a reasonable starting point for future assumptions.
This module tests that idea directly, using leave-future-out validation -
for each historical year, predict it using ONLY the years before it, then
compare the prediction to what actually happened. No lookahead bias.

Scope note: this deliberately does NOT attempt to reconstruct historical
stock prices or period-accurate WACC/beta at past dates - yfinance's
~4-year financial statement history isn't enough data to do that reliably,
and getting it wrong silently would be worse than not building it. This
tests the ASSUMPTION methodology itself, which is arguably the more
fundamental thing to validate anyway - if historical medians don't predict
future performance well, that matters more than any single price comparison.
"""

import pandas as pd


def backtest_margin_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """For each year (except the first, which has no prior history), predict
    its EBIT margin using the median of ALL PRIOR years' margins, then
    compare to the actual realized margin that year."""
    years = sorted(df.dropna(axis=1, how="all").columns)
    revenues = df.loc["Revenue", years]
    ebit = df.loc["EBIT", years]
    margins = ebit / revenues

    rows = []
    for i in range(1, len(years)):  # skip the first year - no prior history to predict from
        year = years[i]
        prior_margins = margins.iloc[:i]  # strictly before this year
        predicted = prior_margins.median()
        actual = margins.iloc[i]
        rows.append({
            "Year": year,
            "Predicted Margin": predicted,
            "Actual Margin": actual,
            "Error": predicted - actual,
        })
    return pd.DataFrame(rows)


def backtest_growth_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """Same idea, for revenue growth. Growth rates require two consecutive
    years to compute, so the first testable prediction is one year later
    than for margin."""
    years = sorted(df.dropna(axis=1, how="all").columns)
    revenues = df.loc["Revenue", years]
    growth_rates = revenues.pct_change().dropna()  # indexed by year, one fewer than years
    growth_years = list(growth_rates.index)

    rows = []
    for i in range(1, len(growth_years)):  # skip the first growth rate - no prior growth history
        year = growth_years[i]
        prior_growth = growth_rates.iloc[:i]
        predicted = prior_growth.median()
        actual = growth_rates.iloc[i]
        rows.append({
            "Year": year,
            "Predicted Growth": predicted,
            "Actual Growth": actual,
            "Error": predicted - actual,
        })
    return pd.DataFrame(rows)


def run_backtest(df: pd.DataFrame) -> dict:
    """Runs both backtests and computes summary accuracy statistics."""
    margin_results = backtest_margin_accuracy(df)
    growth_results = backtest_growth_accuracy(df)

    summary = {
        "margin_results": margin_results,
        "growth_results": growth_results,
        "margin_mae": margin_results["Error"].abs().mean() if len(margin_results) > 0 else None,
        "growth_mae": growth_results["Error"].abs().mean() if len(growth_results) > 0 else None,
        # Mean (not absolute) error shows systematic bias direction - negative
        # means the model tends to UNDER-predict (actual came in higher than
        # predicted), positive means it tends to OVER-predict.
        "margin_bias": margin_results["Error"].mean() if len(margin_results) > 0 else None,
        "growth_bias": growth_results["Error"].mean() if len(growth_results) > 0 else None,
        "n_margin_tests": len(margin_results),
        "n_growth_tests": len(growth_results),
    }
    return summary


if __name__ == "__main__":
    import sys
    from step2_get_financials import get_dcf_inputs

    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    print(f"Backtesting assumption methodology for {ticker}...\n")

    df = get_dcf_inputs(ticker)
    result = run_backtest(df)

    print("--- Margin Predictions ---")
    print(result["margin_results"].to_string(index=False))
    print(f"\nMargin MAE: {result['margin_mae']:.2%}")
    print(f"Margin bias: {result['margin_bias']:+.2%} "
          f"({'under-predicts' if result['margin_bias'] < 0 else 'over-predicts'})")

    print("\n--- Growth Predictions ---")
    print(result["growth_results"].to_string(index=False))
    print(f"\nGrowth MAE: {result['growth_mae']:.2%}")
    print(f"Growth bias: {result['growth_bias']:+.2%} "
          f"({'under-predicts' if result['growth_bias'] < 0 else 'over-predicts'})")

    print(f"\nNote: only {result['n_margin_tests']} margin and {result['n_growth_tests']} "
          f"growth test points available, limited by yfinance's ~4-year financial "
          f"statement history. Directionally informative, not statistically robust.")
