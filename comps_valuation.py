"""
Comparable company ("comps") valuation
--------------------------------------------
A second, independent valuation method sitting alongside the DCF: instead
of forecasting cash flows, this values the company based on what similar
public companies are currently trading at, using EV/EBITDA and P/E
multiples. This is exactly the methodology real Morningstar/CFI reports
use as a cross-check against DCF - see the "Competitors" table in the
Morningstar report analyzed at the very start of this project (which
listed Alphabet, Oracle, and Salesforce as MSFT's own real comps).

Peers are chosen by the USER, not auto-detected - auto-detecting "similar"
companies is unreliable and this project's whole philosophy has been
explicit, auditable inputs over black-box automation.
"""

import yfinance as yf
import pandas as pd


def get_comps_data(tickers: list) -> pd.DataFrame:
    """Pull key multiples for a list of tickers. Uses yfinance's own
    pre-computed multiples where available (enterpriseToEbitda, trailingPE)
    rather than re-deriving them, since Yahoo's own figures are what the
    market actually references. Missing fields become NaN, not None -
    same lesson learned earlier in this project (step2_get_financials.py) -
    so a peer missing one multiple doesn't crash the whole comparison,
    it's just excluded from that specific average/median."""

    rows = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
        except Exception as e:
            print(f"  [!] Could not pull data for {ticker}: {e}")
            info = {}

        rows[ticker] = {
            "Company": info.get("longName", ticker),
            "EV/EBITDA": info.get("enterpriseToEbitda"),
            "P/E": info.get("trailingPE"),
            "Market Cap": info.get("marketCap"),
            "EBITDA": info.get("ebitda"),
            "EPS": info.get("trailingEps"),
        }

    return pd.DataFrame(rows).T  # tickers as rows


def compute_comps_valuation(target_ticker: str, peer_tickers: list,
                              target_shares_outstanding: float,
                              target_cash: float, target_debt: float) -> dict:
    """Pull data for the target + peers, compute peer median multiples
    (excluding the target itself), and derive an implied share price under
    each method. Peers missing a given multiple are excluded from that
    specific median via pandas' built-in NaN handling - never crash the
    whole comparison over one peer's missing data point."""

    all_tickers = [target_ticker] + [t for t in peer_tickers if t != target_ticker]
    comps_df = get_comps_data(all_tickers)

    target_row = comps_df.loc[target_ticker]
    peers_df = comps_df.drop(index=target_ticker)

    peer_median_ev_ebitda = pd.to_numeric(peers_df["EV/EBITDA"], errors="coerce").median()
    peer_median_pe = pd.to_numeric(peers_df["P/E"], errors="coerce").median()
    peer_min_ev_ebitda = pd.to_numeric(peers_df["EV/EBITDA"], errors="coerce").min()
    peer_max_ev_ebitda = pd.to_numeric(peers_df["EV/EBITDA"], errors="coerce").max()
    peer_min_pe = pd.to_numeric(peers_df["P/E"], errors="coerce").min()
    peer_max_pe = pd.to_numeric(peers_df["P/E"], errors="coerce").max()

    target_ebitda = target_row["EBITDA"]
    target_eps = target_row["EPS"]

    def _implied_via_ev_ebitda(multiple):
        if multiple is None or pd.isna(multiple) or target_ebitda is None:
            return None
        implied_ev = target_ebitda * multiple
        implied_equity_value = implied_ev - target_debt + target_cash
        return implied_equity_value / target_shares_outstanding

    def _implied_via_pe(multiple):
        if multiple is None or pd.isna(multiple) or target_eps is None:
            return None
        return target_eps * multiple

    implied_price_ev_ebitda = _implied_via_ev_ebitda(peer_median_ev_ebitda)
    implied_price_pe = _implied_via_pe(peer_median_pe)
    # Range: low multiple -> low implied price, high multiple -> high implied
    # price (assumes positive EBITDA/EPS, true for the vast majority of
    # comps candidates - a company with negative earnings isn't a sensible
    # P/E peer to begin with).
    implied_price_ev_ebitda_low = _implied_via_ev_ebitda(peer_min_ev_ebitda)
    implied_price_ev_ebitda_high = _implied_via_ev_ebitda(peer_max_ev_ebitda)
    implied_price_pe_low = _implied_via_pe(peer_min_pe)
    implied_price_pe_high = _implied_via_pe(peer_max_pe)

    return {
        "comps_table": comps_df,
        "peer_median_ev_ebitda": peer_median_ev_ebitda,
        "peer_median_pe": peer_median_pe,
        "peer_min_ev_ebitda": peer_min_ev_ebitda,
        "peer_max_ev_ebitda": peer_max_ev_ebitda,
        "peer_min_pe": peer_min_pe,
        "peer_max_pe": peer_max_pe,
        "target_ebitda": target_ebitda,
        "target_eps": target_eps,
        "implied_price_ev_ebitda": implied_price_ev_ebitda,
        "implied_price_pe": implied_price_pe,
        "implied_price_ev_ebitda_low": implied_price_ev_ebitda_low,
        "implied_price_ev_ebitda_high": implied_price_ev_ebitda_high,
        "implied_price_pe_low": implied_price_pe_low,
        "implied_price_pe_high": implied_price_pe_high,
    }


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    peers = sys.argv[2].split(",") if len(sys.argv) > 2 else ["GOOGL", "ORCL", "CRM"]

    print(f"Comps valuation for {ticker} vs. peers {peers}...\n")
    stock_info = yf.Ticker(ticker).info
    result = compute_comps_valuation(
        ticker, peers,
        target_shares_outstanding=stock_info.get("sharesOutstanding"),
        target_cash=stock_info.get("totalCash", 0),
        target_debt=stock_info.get("totalDebt", 0),
    )
    print(result["comps_table"])
    print(f"\nPeer median EV/EBITDA: {result['peer_median_ev_ebitda']}")
    print(f"Peer median P/E: {result['peer_median_pe']}")
    print(f"Implied price (EV/EBITDA method): {result['implied_price_ev_ebitda']}")
    print(f"Implied price (P/E method): {result['implied_price_pe']}")
