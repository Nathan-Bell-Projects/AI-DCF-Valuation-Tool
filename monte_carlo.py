"""
Monte Carlo simulation
----------------------------
Instead of one implied share price, run the DCF thousands of times with
randomized inputs and see the full distribution of outcomes. This is the
quantitative version of Morningstar's "Uncertainty Rating" concept (from
the very first report analyzed in this project) - a range of confidence,
not a single number pretending to be precise.

Scope, deliberately limited for v1: only revenue growth, WACC, and terminal
growth are randomized - these are the three biggest value drivers. EBIT
margin, capex %, D&A %, and NWC % stay fixed at their historical-median
values. This is a documented simplification, not an oversight - randomizing
every input would make the results harder to interpret without adding much
insight, since growth and WACC dominate the DCF's sensitivity (as our own
sensitivity table already showed).

Reuses run_dcf_scenario() from step3_dcf_engine.py - the exact function
introduced during the refactor specifically so a pattern like "run the full
DCF under a given set of overrides" only has one implementation.
"""

import numpy as np
import pandas as pd
from step3_dcf_engine import get_historical_assumptions, run_dcf_scenario


def _historical_std(df: pd.DataFrame, row_name: str) -> float:
    """Standard deviation of a metric's year-over-year values (or, for
    growth, of the growth rates themselves) - a data-driven estimate of
    how much this input has actually varied historically, rather than an
    arbitrary guessed uncertainty."""
    years = sorted(df.dropna(axis=1, how="all").columns)
    if row_name == "Revenue Growth":
        revenues = df.loc["Revenue", years]
        values = revenues.pct_change().dropna()
    else:
        values = df.loc[row_name, years]
    std = values.std()
    return std if pd.notna(std) and std > 0 else 0.02  # small sane fallback if too little data


def run_monte_carlo(df: pd.DataFrame, cash: float, total_debt: float,
                      shares_outstanding: float, wacc_base: float, terminal_growth_base: float,
                      n_simulations: int = 1000, wacc_std: float = 0.015,
                      terminal_growth_std: float = 0.005, random_seed: int = 42) -> dict:
    """Run the DCF n_simulations times with randomly sampled revenue growth,
    WACC, and terminal growth, and return the distribution of implied share
    prices plus summary statistics.

    random_seed defaults to a fixed value (not None) so results are
    REPRODUCIBLE - the same inputs always produce the same simulated
    distribution, which matters for testing and for being able to say
    "here's what I got" without the number changing every run."""

    rng = np.random.default_rng(random_seed)

    base_assumptions = get_historical_assumptions(df, method="median")
    growth_std = _historical_std(df, "Revenue Growth")

    implied_prices = []
    sampled_growth, sampled_wacc, sampled_terminal_growth = [], [], []

    max_attempts_per_draw = 10  # guard against pathological resampling loops
    for _ in range(n_simulations):
        for _attempt in range(max_attempts_per_draw):
            growth = rng.normal(base_assumptions["avg_revenue_growth"], growth_std)
            wacc = rng.normal(wacc_base, wacc_std)
            terminal_growth = rng.normal(terminal_growth_base, terminal_growth_std)

            # Reject economically nonsensical draws: WACC must be positive
            # and strictly greater than terminal growth (same guard rail
            # already used in the sensitivity table - the Gordon Growth
            # formula breaks otherwise).
            if wacc > 0.01 and terminal_growth < wacc - 0.005:
                break
        else:
            continue  # skip this simulation if no valid draw found in the attempt budget

        scenario = run_dcf_scenario(
            df, cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
            wacc=wacc, terminal_growth=terminal_growth,
            overrides={"avg_revenue_growth": growth},
            verbose=False,  # essential here - this runs thousands of times per simulation
        )
        implied_prices.append(scenario["result"]["implied_share_price"])
        sampled_growth.append(growth)
        sampled_wacc.append(wacc)
        sampled_terminal_growth.append(terminal_growth)

    prices = np.array(implied_prices)

    return {
        "n_simulations_requested": n_simulations,
        "n_simulations_completed": len(prices),
        "prices": prices,
        "mean": float(np.mean(prices)),
        "median": float(np.median(prices)),
        "std": float(np.std(prices)),
        "min": float(np.min(prices)),
        "max": float(np.max(prices)),
        "p5": float(np.percentile(prices, 5)),
        "p25": float(np.percentile(prices, 25)),
        "p50": float(np.percentile(prices, 50)),
        "p75": float(np.percentile(prices, 75)),
        "p95": float(np.percentile(prices, 95)),
        "growth_std_used": growth_std,
        "wacc_std_used": wacc_std,
        "terminal_growth_std_used": terminal_growth_std,
    }


def probability_above_price(mc_result: dict, target_price: float) -> float:
    """What fraction of simulated outcomes exceed a given price (e.g. the
    current market price) - an intuitive 'probability of undervaluation'
    style statistic."""
    prices = mc_result["prices"]
    return float(np.mean(prices > target_price))


if __name__ == "__main__":
    import sys
    from step2_get_financials import get_dcf_inputs
    import yfinance as yf

    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    print(f"Running Monte Carlo simulation for {ticker}...\n")

    df = get_dcf_inputs(ticker)
    assumptions = get_historical_assumptions(df)
    latest_year = assumptions["latest_year"]
    cash = df.loc["Cash", latest_year]
    total_debt = df.loc["Total Debt", latest_year]
    stock_info = yf.Ticker(ticker).info
    shares_outstanding = stock_info.get("sharesOutstanding")
    current_price = stock_info.get("currentPrice")

    result = run_monte_carlo(df, cash, total_debt, shares_outstanding,
                               wacc_base=0.09, terminal_growth_base=0.025, n_simulations=1000)

    print(f"Simulations completed: {result['n_simulations_completed']} / {result['n_simulations_requested']}")
    print(f"Mean implied price: ${result['mean']:.2f}")
    print(f"Median implied price: ${result['median']:.2f}")
    print(f"Std dev: ${result['std']:.2f}")
    print(f"5th-95th percentile range: ${result['p5']:.2f} - ${result['p95']:.2f}")
    if current_price:
        prob = probability_above_price(result, current_price)
        print(f"\nCurrent market price: ${current_price:.2f}")
        print(f"Probability simulated DCF exceeds market price: {prob:.1%}")
