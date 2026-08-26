"""
Currency conversion via Frankfurter (free, no API key, ECB-sourced rates)
------------------------------------------------------------------------------------
STATUS: standalone module, NOT yet wired into app.py or step5_excel_export.py.

This exists to extend check_currency_mismatch() (step2_get_financials.py) -
currently, a mismatch (e.g. SONY: USD-traded, JPY-reported) causes the tool
to safely REFUSE to show a number. This module is the next step: actually
converting the JPY-denominated financials to USD before running the DCF,
so a currency mismatch becomes usable instead of blocked.

Deliberately built and tested in isolation, not connected to the live
Streamlit app in this same session - wiring this in means changing how
check_currency_mismatch()'s result is handled (currently: block; would
become: convert and proceed with a disclosure), which touches the same
live, CV-linked app that a same-day untested change already broke once
(the streamlit-extras rollback). That integration deserves its own
focused session, not 30 rushed minutes.

Note: this sandbox's network access does not include api.frankfurter.dev,
so the live API call itself could not be tested end-to-end from here -
verified instead against Frankfurter's documented response format with a
mocked test. Run test_fx_conversion.py yourself with real network access
to confirm the live call actually works before relying on it.
"""

import requests

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1/latest"


def fetch_fx_rate(from_currency: str, to_currency: str) -> float:
    """Fetches the current exchange rate to convert an amount FROM
    from_currency TO to_currency (i.e. multiply a from_currency amount by
    this rate to get the to_currency equivalent). No API key needed."""
    if from_currency == to_currency:
        return 1.0

    response = requests.get(
        FRANKFURTER_BASE_URL,
        params={"base": from_currency, "symbols": to_currency},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if "rates" not in data or to_currency not in data["rates"]:
        raise ValueError(
            f"Frankfurter response missing expected rate for {from_currency}->{to_currency}: {data}"
        )
    return data["rates"][to_currency]


def convert_financial_statements(df, rate: float):
    """Converts every numeric value in the financial statements DataFrame
    by the given rate. Used to convert e.g. JPY-denominated revenue/EBIT/
    cash/debt figures into the trading currency (USD) before running the
    DCF, so per-share math (which uses a trading-currency share count and
    price) stays internally consistent.

    Deliberately takes a pre-fetched rate rather than fetching it itself -
    keeps this function pure and easily testable without network access,
    and avoids a redundant API call if converting multiple things."""
    return df * rate


if __name__ == "__main__":
    import sys
    from step2_get_financials import get_dcf_inputs, check_currency_mismatch
    import yfinance as yf

    ticker = sys.argv[1] if len(sys.argv) > 1 else "SONY"
    print(f"Testing currency conversion for {ticker}...\n")
    print("NOTE: this makes a real network call to api.frankfurter.dev - "
          "requires network access this sandbox doesn't have.\n")

    stock_info = yf.Ticker(ticker).info
    check = check_currency_mismatch(stock_info)
    print(f"Currency check: {check}")

    if check["mismatch"]:
        rate = fetch_fx_rate(check["financial_currency"], check["trading_currency"])
        print(f"Rate ({check['financial_currency']} -> {check['trading_currency']}): {rate}")

        df = get_dcf_inputs(ticker)
        df_converted = convert_financial_statements(df, rate)
        print("\nOriginal (first column):")
        print(df.iloc[:, 0])
        print("\nConverted (first column):")
        print(df_converted.iloc[:, 0])
    else:
        print("No mismatch detected - nothing to convert.")
