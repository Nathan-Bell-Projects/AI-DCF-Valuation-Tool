"""
Step 6: AI assumption-check & gap explanation layer
--------------------------------------------------------
Takes the DCF output (implied price, assumptions) plus some forward-looking
market data, and asks Claude to explain WHY the implied price differs from
the current market price - in plain English, grounded only in the actual
numbers provided.

Critical design principle: the AI never generates or overrides any number
the DCF engine calculated. It only comments on numbers that already exist.
It's explicitly instructed not to invent explanations beyond what the data
supports - if the data doesn't clearly explain the gap, it should say so.
"""

import os
from anthropic import Anthropic


def gather_context(ticker: str, df, assumptions: dict, result: dict,
                    current_price: float, stock_info: dict,
                    wacc: float, terminal_growth: float) -> dict:
    """Collect the specific numbers the AI needs to ground its explanation -
    both the historical/backward-looking numbers already in the model, and
    forward-looking numbers (analyst estimates) NOT currently used anywhere
    else in the DCF, which is exactly what's missing when historical
    averages lag a fast-moving narrative (as we found with MSFT and CAT).

    Also includes the WACC/capex assumptions actually used, and the spread
    (min-max) of historical capex ratios - because our own manual testing
    found that for MSFT, the real driver of the price gap was an anomalous
    capex year and the WACC choice, NOT revenue growth. An earlier version
    of this function only passed growth-related context, which would have
    led the AI to reason about the wrong thing."""

    years = sorted(df.dropna(axis=1, how="all").columns)
    revenues = df.loc["Revenue", years]
    yoy_growth = revenues.pct_change().dropna()
    capex_pct_series = df.loc["Capex", years].abs() / revenues

    context = {
        "ticker": ticker,
        "historical_median_growth": assumptions["avg_revenue_growth"],
        "most_recent_year_growth": yoy_growth.iloc[-1] if len(yoy_growth) > 0 else None,
        "implied_share_price": result["implied_share_price"],
        "current_market_price": current_price,
        "gap_pct": (result["implied_share_price"] / current_price - 1),
        "wacc_used": wacc,
        "terminal_growth_used": terminal_growth,
        "capex_pct_used": assumptions["avg_capex_pct_revenue"],
        "capex_pct_historical_min": capex_pct_series.min(),
        "capex_pct_historical_max": capex_pct_series.max(),
        # Forward-looking data yfinance provides but the DCF engine doesn't
        # use anywhere else - analyst consensus estimates
        "analyst_target_price": stock_info.get("targetMeanPrice"),
        "analyst_revenue_growth_estimate": stock_info.get("revenueGrowth"),
        "analyst_recommendation": stock_info.get("recommendationKey"),
    }
    return context


def build_prompt(context: dict) -> str:
    return f"""You are a financial analyst assistant. You have been given
the output of a DCF (discounted cash flow) valuation model for {context['ticker']},
along with some market context. Explain, in 3-4 sentences of plain English,
the most likely reason(s) for the gap between the model's implied share price
and the actual market price.

CRITICAL RULES:
- Only reason from the numbers provided below. Do not invent company news,
  events, or explanations not supported by this data.
- If the data does not clearly explain the gap, say so explicitly rather
  than guessing.
- Do not state or imply the model is "wrong" or the market is "wrong" -
  explain the gap as a difference in assumptions/perspective, not an error.
- Do not generate or suggest specific new numeric assumptions - your role
  is to explain, not to recalculate.

DATA:
- Implied share price (DCF, historical-median-based assumptions): ${context['implied_share_price']:.2f}
- Current market price: ${context['current_market_price']:.2f}
- Gap: {context['gap_pct']:+.1%}
- WACC (discount rate) used in this run: {context['wacc_used']:.1%}
- Terminal growth rate used: {context['terminal_growth_used']:.1%}
- Historical median revenue growth used in the model: {context['historical_median_growth']:.1%}
- Most recent single-year revenue growth (actual): {context['most_recent_year_growth']:.1%}
- Capex assumption used (% of revenue): {context['capex_pct_used']:.1%}
- Historical capex range across recent years (% of revenue): {context['capex_pct_historical_min']:.1%} to {context['capex_pct_historical_max']:.1%}
- Analyst mean target price: {f"${context['analyst_target_price']:.2f}" if context['analyst_target_price'] else "Not available"}
- Analyst forward revenue growth estimate: {f"{context['analyst_revenue_growth_estimate']:.1%}" if context['analyst_revenue_growth_estimate'] else "Not available"}
- Analyst consensus recommendation: {context['analyst_recommendation'] or "Not available"}

Write the explanation now, as plain prose (no headers, no bullet points)."""


def generate_gap_explanation(ticker: str, df, assumptions: dict, result: dict,
                               current_price: float, stock_info: dict,
                               wacc: float, terminal_growth: float) -> str:
    context = gather_context(ticker, df, assumptions, result, current_price,
                              stock_info, wacc, terminal_growth)
    prompt = build_prompt(context)

    client = Anthropic()  # reads ANTHROPIC_API_KEY from environment
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


if __name__ == "__main__":
    import argparse
    import yfinance as yf
    from step3_dcf_engine import get_dcf_inputs, get_historical_assumptions, forecast_free_cash_flow, calculate_dcf_valuation

    parser = argparse.ArgumentParser(description="Generate an AI explanation of the DCF vs market price gap.")
    parser.add_argument("--ticker", default="MSFT")
    parser.add_argument("--wacc", type=float, default=0.09)
    parser.add_argument("--terminal-growth", type=float, default=0.025, dest="terminal_growth")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY environment variable first.")
        exit(1)

    df = get_dcf_inputs(args.ticker)
    assumptions = get_historical_assumptions(df)
    forecast_df = forecast_free_cash_flow(assumptions)

    latest_year = assumptions["latest_year"]
    cash = df.loc["Cash", latest_year]
    total_debt = df.loc["Total Debt", latest_year]
    stock_info = yf.Ticker(args.ticker).info
    shares_outstanding = stock_info.get("sharesOutstanding")
    current_price = stock_info.get("currentPrice")

    result = calculate_dcf_valuation(
        forecast_df, wacc=args.wacc, terminal_growth=args.terminal_growth,
        cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
    )

    print(f"Implied price: ${result['implied_share_price']:.2f} | Market price: ${current_price:.2f}\n")
    print("Generating AI explanation...\n")

    explanation = generate_gap_explanation(args.ticker, df, assumptions, result,
                                             current_price, stock_info,
                                             args.wacc, args.terminal_growth)
    print("--- AI Explanation ---")
    print(explanation)
