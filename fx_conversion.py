"""
Currency conversion via Frankfurter (free, no API key, ECB-sourced rates)
------------------------------------------------------------------------------------
Wired into app.py: when check_currency_mismatch() (step2_get_financials.py)
detects a mismatch (e.g. AB InBev: EUR-traded, USD-reported; SONY: USD-
traded, JPY-reported), the app fetches the current spot rate and converts
the financials into the trading currency before running the DCF - shown to
the user as a disclosed conversion, rather than a hard block. If the live
FX call itself fails, the app surfaces that as a retry-able error instead
of silently proceeding on unconverted figures.

Note: this project's development sandbox's network access does not
include api.frankfurter.dev, so the live API call itself could not be
tested end-to-end from there - verified instead against Frankfurter's
documented response format with a mocked test. If this ever needs
re-verifying end-to-end, run test_fx_conversion.py with real network
access, or just watch it work live in the deployed app (AB InBev is a
reliable real-world trigger for this path).
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
