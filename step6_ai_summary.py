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
                    wacc: float, terminal_growth: float,
                    analyst_info: dict = None) -> dict:
    """Collect the specific numbers the AI needs to ground its explanation -
    both the historical/backward-looking numbers already in the model, and
    forward-looking numbers (analyst estimates) NOT currently used anywhere
    else in the DCF, which is exactly what's missing when historical
    averages lag a fast-moving narrative (as we found with MSFT and CAT).

    Also includes the WACC/capex assumptions actually used, and the spread
    (min-max) of historical capex ratios - because our own manual testing
    found that for MSFT, the real driver of the price gap was an anomalous
    capex year and the WACC choice, NOT revenue growth.

    analyst_info (from analyst_data.py) adds the fuller recommendation
    breakdown and its recent trend, so the AI can also reason about WHY
    analysts lean bullish/bearish - not just explain the model's own gap."""

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
        "analyst_target_price": stock_info.get("targetMeanPrice"),
        "analyst_revenue_growth_estimate": stock_info.get("revenueGrowth"),
        "analyst_recommendation": stock_info.get("recommendationKey"),
        # New: fuller recommendation breakdown + trend, and price target range
        "recommendation_breakdown": None,
        "recommendation_trend_note": None,
        "target_price_range": None,
    }

    if analyst_info:
        targets = analyst_info.get("price_targets")
        if targets:
            context["target_price_range"] = (
                f"low ${targets.get('low'):.2f} / mean ${targets.get('mean'):.2f} / "
                f"high ${targets.get('high'):.2f}" if targets.get("low") is not None else None
            )

        recs = analyst_info.get("recommendations")
        if recs is not None and len(recs) > 0:
            latest = recs.iloc[0]
            context["recommendation_breakdown"] = (
                f"Strong Buy: {int(latest.get('strongBuy', 0))}, Buy: {int(latest.get('buy', 0))}, "
                f"Hold: {int(latest.get('hold', 0))}, Sell: {int(latest.get('sell', 0))}, "
                f"Strong Sell: {int(latest.get('strongSell', 0))}"
            )
            # Trend: compare most recent period to 3 months ago, if available
            if len(recs) >= 4:
                past = recs.iloc[3]
                buy_now = latest.get("strongBuy", 0) + latest.get("buy", 0)
                buy_past = past.get("strongBuy", 0) + past.get("buy", 0)
                if buy_now != buy_past:
                    direction = "increased" if buy_now > buy_past else "decreased"
                    context["recommendation_trend_note"] = (
                        f"Combined Buy+Strong Buy count has {direction} from {buy_past} to {buy_now} "
                        f"over roughly the last 3 months"
                    )

    return context


def compute_valuation_rating(gap_pct: float) -> dict:
    """A deterministic, rule-based rating derived directly from the DCF's
    own output - NOT generated or judged by the LLM. This mirrors how
    professional research (e.g. Morningstar's star rating) works: the
    rating is a transparent function of Price/Fair Value, and analyst
    commentary explains it rather than replaces it. Keeping this rule-based
    means the rating is fully auditable and never subject to LLM
    hallucination or inconsistency between runs."""
    if gap_pct > 0.30:
        return {"stars": 5, "label": "Strongly Undervalued (model)"}
    elif gap_pct > 0.10:
        return {"stars": 4, "label": "Undervalued (model)"}
    elif gap_pct > -0.10:
        return {"stars": 3, "label": "Fairly Valued (model)"}
    elif gap_pct > -0.30:
        return {"stars": 2, "label": "Overvalued (model)"}
    else:
        return {"stars": 1, "label": "Strongly Overvalued (model)"}


def build_prompt(context: dict, rating: dict) -> str:
    return f"""You are a financial analyst assistant. You have been given
the output of a DCF (discounted cash flow) valuation model for {context['ticker']},
along with some market context and a rule-based valuation rating that has
ALREADY been computed (you are not generating this rating - explain it).

Write a 6-8 sentence plain-English explanation covering:
1. State the rating ({rating['stars']}/5 stars, "{rating['label']}") and what it means in one sentence.
2. Explain the most likely reason(s) for the gap between the model's implied
   share price and the actual market price (this is about the MODEL's own view).
3. Separately, explain what in the provided data might plausibly explain why
   sell-side analysts lean toward their current recommendation (this is about
   the STREET's view, not the model's) - e.g. does the forward growth estimate
   exceed historical growth, has the recommendation mix shifted recently, does
   the price target range suggest confidence or wide disagreement among analysts.
   Only reason from the specific data given - if nothing in the data clearly
   explains analyst sentiment, say so rather than guessing.
4. Close with one sentence putting this in context for the reader (e.g. what
   would need to be true for the model's view vs. the market's view to be right).

CRITICAL RULES:
- Only reason from the numbers provided below. Do not invent company news,
  events, or explanations not supported by this data.
- You are given THREE candidate drivers of the model's gap: (1) revenue growth
  assumption, (2) WACC/discount rate, (3) capex assumption. Explicitly
  consider all three before writing your explanation - do not default to
  whichever one has the most readily available narrative (e.g. analyst
  growth estimates) if the magnitude of that factor's plausible impact is
  small relative to the others. Use the historical capex range and the
  size of each percentage gap to judge which factor(s) most plausibly
  explain a gap of this magnitude, and say so explicitly - e.g. if the
  growth assumption gap is only 1-2 percentage points, that alone is
  unlikely to explain a 40%+ price gap, and you should say the WACC or
  capex assumption is the more likely primary driver instead.
- For part 3 (analyst sentiment), do NOT invent qualitative narratives (e.g.
  specific products, competitive dynamics, management actions) that are not
  present in the data below. Stick to what the numbers themselves suggest.
- If the data does not clearly explain something, say so explicitly rather
  than guessing.
- Do not state or imply the model is "wrong" or the market is "wrong" -
  explain both as different, internally consistent views based on different
  methodologies and information, not an error on either side.
- Do not generate or suggest specific new numeric assumptions, and do not
  issue your own independent buy/hold/sell recommendation beyond restating
  the rule-based rating already provided - your role is to explain, not to
  recalculate or advise.
- End with a one-line disclaimer: this is a model output based on specific
  assumptions, not investment advice.

DATA:
- Implied share price (DCF, historical-median-based assumptions): ${context['implied_share_price']:.2f}
- Current market price: ${context['current_market_price']:.2f}
- Gap: {context['gap_pct']:+.1%}
- Rule-based rating: {rating['stars']}/5 stars ({rating['label']})
- WACC (discount rate) used in this run: {context['wacc_used']:.1%}
- Terminal growth rate used: {context['terminal_growth_used']:.1%}
- Historical median revenue growth used in the model: {context['historical_median_growth']:.1%}
- Most recent single-year revenue growth (actual): {context['most_recent_year_growth']:.1%}
- Capex assumption used (% of revenue): {context['capex_pct_used']:.1%}
- Historical capex range across recent years (% of revenue): {context['capex_pct_historical_min']:.1%} to {context['capex_pct_historical_max']:.1%}
- Analyst mean target price: {f"${context['analyst_target_price']:.2f}" if context['analyst_target_price'] else "Not available"}
- Analyst target price range: {context['target_price_range'] or "Not available"}
- Analyst forward revenue growth estimate: {f"{context['analyst_revenue_growth_estimate']:.1%}" if context['analyst_revenue_growth_estimate'] else "Not available"}
- Analyst consensus recommendation: {context['analyst_recommendation'] or "Not available"}
- Analyst recommendation breakdown (most recent period): {context['recommendation_breakdown'] or "Not available"}
- Recommendation trend: {context['recommendation_trend_note'] or "Not available / no significant change"}

Write the explanation now, as plain prose (no headers, no bullet points)."""


def generate_gap_explanation(ticker: str, df, assumptions: dict, result: dict,
                               current_price: float, stock_info: dict,
                               wacc: float, terminal_growth: float,
                               analyst_info: dict = None) -> dict:
    context = gather_context(ticker, df, assumptions, result, current_price,
                              stock_info, wacc, terminal_growth, analyst_info)
    rating = compute_valuation_rating(context["gap_pct"])
    prompt = build_prompt(context, rating)

    client = Anthropic()  # reads ANTHROPIC_API_KEY from environment
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=650,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "rating": rating,
        "explanation": response.content[0].text.strip(),
    }


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

    from analyst_data import get_analyst_data
    analyst_info = get_analyst_data(args.ticker)

    output = generate_gap_explanation(args.ticker, df, assumptions, result,
                                        current_price, stock_info,
                                        args.wacc, args.terminal_growth,
                                        analyst_info=analyst_info)
    rating = output["rating"]
    stars_display = "\u2605" * rating["stars"] + "\u2606" * (5 - rating["stars"])
    print(f"--- Valuation Rating (rule-based, from gap %) ---")
    print(f"{stars_display}  {rating['label']}")
    print(f"\n--- AI Explanation ---")
    print(output["explanation"])
