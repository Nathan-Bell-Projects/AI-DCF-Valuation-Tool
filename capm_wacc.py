"""
CAPM-based WACC estimation
-------------------------------
Derives a company-specific SUGGESTED WACC using the standard formula real
analysts use, instead of the flat 9% default the DCF engine has used so
far. This directly explains something found through manual testing earlier
in this project: PG (low-beta, ~0.24) needed a much lower WACC than MSFT
to produce a sensible valuation - CAPM derives that starting point
automatically instead of hunting for it by trial and error.

WACC = (Weight of Equity x Cost of Equity) + (Weight of Debt x After-Tax Cost of Debt)

Cost of Equity (CAPM) = Risk-Free Rate + Beta x Equity Risk Premium
Cost of Debt (pre-tax, estimated) = Interest Expense / Total Debt
After-Tax Cost of Debt = Pre-Tax Cost of Debt x (1 - Tax Rate)

This is a SUGGESTION, not an automatic override - the DCF engine's --wacc
argument still defaults to a flat rate unless the user explicitly chooses
to use this value instead. Every component is returned so the reasoning
is fully visible and auditable, not a black-box single number.
"""

import yfinance as yf

DEFAULT_RISK_FREE_RATE = 0.04       # fallback if the live Treasury yield pull fails
DEFAULT_EQUITY_RISK_PREMIUM = 0.05  # standard, widely-used long-run market risk premium
DEFAULT_CREDIT_SPREAD = 0.015       # fallback pre-tax cost of debt = risk-free rate + this, if
                                     # interest expense / debt can't be computed


def get_risk_free_rate() -> float:
    """Pulls the 10-year US Treasury yield via the ^TNX ticker, which
    returns the yield directly as a percentage (e.g. a value of 4.696
    means 4.696%) - divide by 100 to get a decimal rate. Falls back to a
    fixed default if the pull fails OR if the result is outside a sane
    range for a risk-free rate (guards against a bad/misread data pull
    silently corrupting every downstream calculation - exactly what
    happened during testing when an earlier version of this function
    applied an incorrect extra /10 scaling and produced a ~0.5% rate)."""
    try:
        tnx = yf.Ticker("^TNX")
        rate = tnx.info.get("regularMarketPrice") or tnx.info.get("previousClose")
        if rate:
            decimal_rate = rate / 100
            if 0.005 <= decimal_rate <= 0.15:  # sane bounds: 0.5% to 15%
                return decimal_rate
            print(f"  [!] ^TNX pull ({rate}) produced an out-of-range rate "
                  f"({decimal_rate:.2%}) - using default {DEFAULT_RISK_FREE_RATE:.2%} instead")
        return DEFAULT_RISK_FREE_RATE
    except Exception:
        return DEFAULT_RISK_FREE_RATE


def compute_capm_wacc(ticker: str, df, stock_info: dict, tax_rate: float = 0.21,
                        equity_risk_premium: float = DEFAULT_EQUITY_RISK_PREMIUM,
                        risk_free_rate: float = None) -> dict:
    """Returns a dict with every component of the calculation, not just the
    final number, so the reasoning stays fully visible."""

    beta = stock_info.get("beta")
    market_cap = stock_info.get("marketCap")

    if risk_free_rate is None:
        risk_free_rate = get_risk_free_rate()

    # Cost of equity - if beta is missing (rare, but some tickers lack it),
    # fall back to a market-average beta of 1.0 rather than crashing.
    beta_used = beta if beta is not None else 1.0
    cost_of_equity = risk_free_rate + beta_used * equity_risk_premium

    # Cost of debt - estimated from the most recent year's interest expense
    # relative to total debt. Falls back to a flat credit spread over the
    # risk-free rate if interest expense data isn't available or debt is
    # zero (can't divide by zero).
    years = sorted(df.dropna(axis=1, how="all").columns)
    latest_year = years[-1] if years else None
    total_debt = df.loc["Total Debt", latest_year] if latest_year else None
    interest_expense = df.loc["Interest Expense", latest_year] if latest_year else None

    cost_of_debt_source = "estimated from interest expense / total debt"
    if total_debt and total_debt > 0 and interest_expense is not None and interest_expense == interest_expense:  # NaN check
        cost_of_debt_pretax = abs(interest_expense) / total_debt
        # Sanity guard: an unreasonable estimate (e.g. from noisy data) falls
        # back to the credit-spread proxy rather than feeding a wild number
        # into WACC silently.
        if cost_of_debt_pretax <= 0 or cost_of_debt_pretax > 0.25:
            cost_of_debt_pretax = risk_free_rate + DEFAULT_CREDIT_SPREAD
            cost_of_debt_source = "fallback credit spread (interest expense estimate was out of a sane range)"
    else:
        cost_of_debt_pretax = risk_free_rate + DEFAULT_CREDIT_SPREAD
        cost_of_debt_source = "fallback credit spread (interest expense data not available)"

    cost_of_debt_aftertax = cost_of_debt_pretax * (1 - tax_rate)

    # Capital structure weights, using market value of equity (market cap)
    # and book value of debt (standard practice - market value of debt is
    # rarely directly observable).
    if market_cap and total_debt is not None:
        total_capital = market_cap + total_debt
        weight_equity = market_cap / total_capital
        weight_debt = total_debt / total_capital
    else:
        # If market cap is unavailable, fall back to 100% equity-financed
        # assumption rather than crashing.
        weight_equity, weight_debt = 1.0, 0.0

    wacc = weight_equity * cost_of_equity + weight_debt * cost_of_debt_aftertax

    return {
        "beta": beta_used,
        "beta_was_missing": beta is None,
        "risk_free_rate": risk_free_rate,
        "equity_risk_premium": equity_risk_premium,
        "cost_of_equity": cost_of_equity,
        "cost_of_debt_pretax": cost_of_debt_pretax,
        "cost_of_debt_aftertax": cost_of_debt_aftertax,
        "cost_of_debt_source": cost_of_debt_source,
        "market_cap": market_cap,
        "total_debt": total_debt,
        "weight_equity": weight_equity,
        "weight_debt": weight_debt,
        "wacc": wacc,
    }


if __name__ == "__main__":
    import sys
    from step2_get_financials import get_dcf_inputs

    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    print(f"Computing CAPM-based WACC for {ticker}...\n")

    stock = yf.Ticker(ticker)
    stock_info = stock.info
    df = get_dcf_inputs(ticker)

    result = compute_capm_wacc(ticker, df, stock_info)
    for k, v in result.items():
        print(f"  {k}: {v}")
