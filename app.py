"""
Streamlit interface for the AI-Assisted DCF Valuation Tool
------------------------------------------------------------------
This file contains NO new financial logic - it's purely a UI layer over
the same functions already built and tested throughout this project
(step2-step6, analyst_data, capm_wacc, comps_valuation, monte_carlo,
backtest). If a number looks wrong here, the bug is in one of those
modules, not this one - this file just calls them and displays results.

Run with: streamlit run app.py
"""

import os
import tempfile
import streamlit as st
import yfinance as yf

from step2_get_financials import get_dcf_inputs
from step3_dcf_engine import run_dcf_scenario
from step4_sensitivity import build_sensitivity_table
from step5_excel_export import export_to_excel
from analyst_data import get_analyst_data
from capm_wacc import compute_capm_wacc
from config import DEFAULT_WACC, DEFAULT_TERMINAL_GROWTH, DEFAULT_SENSITIVITY_WACC_RANGE, DEFAULT_SENSITIVITY_GROWTH_RANGE

st.set_page_config(page_title="AI-Assisted DCF Valuation Tool", layout="wide")

st.title("AI-Assisted DCF Valuation Tool")
st.caption(
    "A personal portfolio project. Not investment advice - see the generated workbook's "
    "Cover sheet for the full disclaimer."
)

# ---------------------------------------------------------------
# Sidebar: all inputs live here
# ---------------------------------------------------------------
with st.sidebar:
    st.header("Inputs")
    ticker = st.text_input("Ticker", value="MSFT").strip().upper()
    wacc = st.slider("WACC (discount rate)", 0.03, 0.15, DEFAULT_WACC, 0.005, format="%.3f")
    terminal_growth = st.slider("Terminal growth rate", 0.0, 0.05, DEFAULT_TERMINAL_GROWTH, 0.0025, format="%.4f")

    use_capex_override = st.checkbox("Override capex assumption")
    capex_override = None
    if use_capex_override:
        capex_override = st.slider("Capex override (% of revenue)", 0.0, 0.5, 0.15, 0.01, format="%.2f")

    st.divider()
    st.subheader("Optional add-ons (all free, no API key)")
    include_peers = st.checkbox("Comps valuation + Football Field chart")
    peers_input = ""
    if include_peers:
        peers_input = st.text_input("Peer tickers (comma-separated)", value="GOOGL,ORCL,CRM")

    include_monte_carlo = st.checkbox("Monte Carlo simulation")
    n_simulations = 1000
    if include_monte_carlo:
        n_simulations = st.slider("Number of simulations", 100, 5000, 1000, 100)

    include_backtest = st.checkbox("Backtest assumption methodology")

    st.divider()
    st.subheader("AI Valuation Summary (optional)")
    include_ai = st.checkbox("Include AI-generated explanation")
    api_key = None
    if include_ai:
        st.caption(
            "Requires your own Anthropic API key. Entered here, it's used only for this "
            "session's requests and never saved to disk or sent anywhere else."
        )
        api_key = st.text_input("Anthropic API key", type="password")

    run_button = st.button("Run Analysis", type="primary", use_container_width=True)


# ---------------------------------------------------------------
# Main area: run the pipeline and display results
# ---------------------------------------------------------------
if run_button:
    if not ticker:
        st.error("Enter a ticker first.")
        st.stop()

    try:
        with st.spinner(f"Pulling financial data for {ticker}..."):
            df = get_dcf_inputs(ticker)
            stock_info = yf.Ticker(ticker).info
            current_price = stock_info.get("currentPrice")
            shares_outstanding = stock_info.get("sharesOutstanding")
            company_name = stock_info.get("longName", ticker)

        if current_price is None or shares_outstanding is None:
            st.error(f"Couldn't pull required data for '{ticker}' - check the ticker is valid.")
            st.stop()

        overrides = {"avg_capex_pct_revenue": capex_override} if capex_override is not None else None

        latest_year = sorted(df.dropna(axis=1, how="all").columns)[-1]
        cash = df.loc["Cash", latest_year]
        total_debt = df.loc["Total Debt", latest_year]

        with st.spinner("Running DCF valuation..."):
            scenario = run_dcf_scenario(
                df, cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
                wacc=wacc, terminal_growth=terminal_growth, overrides=overrides,
            )
            assumptions = scenario["assumptions"]
            forecast_df = scenario["forecast_df"]
            result = scenario["result"]

        gap_pct = result["implied_share_price"] / current_price - 1

        # --- Headline metrics ---
        st.subheader(f"{company_name} ({ticker})")
        m1, m2, m3 = st.columns(3)
        m1.metric("Current Price", f"${current_price:,.2f}")
        m2.metric("Implied Price (DCF)", f"${result['implied_share_price']:,.2f}")
        m3.metric("Upside / (Downside)", f"{gap_pct:+.1%}")

        with st.spinner("Building sensitivity table..."):
            sensitivity_df = build_sensitivity_table(
                forecast_df, cash, total_debt, shares_outstanding,
                wacc_range=DEFAULT_SENSITIVITY_WACC_RANGE,
                growth_range=DEFAULT_SENSITIVITY_GROWTH_RANGE,
            )

        with st.spinner("Computing suggested WACC via CAPM..."):
            capm_info = compute_capm_wacc(ticker, df, stock_info)

        with st.spinner("Pulling analyst insights..."):
            analyst_info = get_analyst_data(ticker)
            if analyst_info.get("price_targets"):
                st.subheader("Analyst Consensus")
                targets = analyst_info["price_targets"]
                a1, a2, a3 = st.columns(3)
                a1.metric("Analyst Low", f"${targets.get('low', 0):,.2f}")
                a2.metric("Analyst Mean", f"${targets.get('mean', 0):,.2f}")
                a3.metric("Analyst High", f"${targets.get('high', 0):,.2f}")

        st.subheader("5-Year Forecast")
        st.dataframe(forecast_df.round(0), use_container_width=True)

        st.subheader("WACC / Terminal Growth Sensitivity")
        st.dataframe(sensitivity_df.round(2), use_container_width=True)

        scenarios = [{
            "label": "Base case", "capex_label": "Historical median" if capex_override is None else f"{capex_override:.0%}",
            "wacc": wacc, "terminal_growth": terminal_growth,
            "implied_price": result["implied_share_price"],
        }]

        comps_info = None
        if include_peers and peers_input:
            with st.spinner("Pulling comps data..."):
                from comps_valuation import compute_comps_valuation
                peer_tickers = [p.strip().upper() for p in peers_input.split(",") if p.strip()]
                comps_info = compute_comps_valuation(ticker, peer_tickers, shares_outstanding, cash, total_debt)
                st.subheader("Comps Valuation")
                c1, c2 = st.columns(2)
                c1.metric("Implied Price (EV/EBITDA)", f"${comps_info['implied_price_ev_ebitda']:,.2f}"
                          if comps_info['implied_price_ev_ebitda'] else "N/A")
                c2.metric("Implied Price (P/E)", f"${comps_info['implied_price_pe']:,.2f}"
                          if comps_info['implied_price_pe'] else "N/A")

        monte_carlo_info = None
        if include_monte_carlo:
            with st.spinner(f"Running {n_simulations} Monte Carlo simulations..."):
                from monte_carlo import run_monte_carlo
                monte_carlo_info = run_monte_carlo(
                    df, cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
                    wacc_base=wacc, terminal_growth_base=terminal_growth, n_simulations=n_simulations,
                )
                st.subheader("Monte Carlo Simulation")
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Mean Implied Price", f"${monte_carlo_info['mean']:,.2f}")
                mc2.metric("5th-95th Percentile", f"${monte_carlo_info['p5']:,.0f} - ${monte_carlo_info['p95']:,.0f}")
                prob = float((monte_carlo_info["prices"] > current_price).mean())
                mc3.metric("Prob. DCF Exceeds Market Price", f"{prob:.1%}")

        backtest_info = None
        if include_backtest:
            with st.spinner("Running backtest..."):
                from backtest import run_backtest
                backtest_info = run_backtest(df)
                if backtest_info["margin_mae"] is not None:
                    st.subheader("Backtest: Assumption Accuracy")
                    b1, b2 = st.columns(2)
                    b1.metric("Margin Prediction MAE", f"{backtest_info['margin_mae']:.2%}")
                    b2.metric("Growth Prediction MAE", f"{backtest_info['growth_mae']:.2%}")

        ai_output = None
        if include_ai:
            if not api_key:
                st.warning("AI explanation skipped - no API key entered.")
            else:
                with st.spinner("Generating AI valuation summary..."):
                    os.environ["ANTHROPIC_API_KEY"] = api_key  # session-only, never written to disk
                    from step6_ai_summary import generate_gap_explanation
                    ai_output = generate_gap_explanation(
                        ticker, df, assumptions, result, current_price, stock_info,
                        wacc, terminal_growth, analyst_info=analyst_info,
                    )
                    st.subheader("AI Valuation Summary")
                    stars = "\u2605" * ai_output["rating"]["stars"] + "\u2606" * (5 - ai_output["rating"]["stars"])
                    st.markdown(f"### {stars}  {ai_output['rating']['label']}")
                    st.write(ai_output["explanation"])

        # --- Build the full Excel workbook and offer it for download ---
        with st.spinner("Building Excel workbook..."):
            with tempfile.TemporaryDirectory() as tmp_dir:
                output_path = os.path.join(tmp_dir, f"{ticker}_dcf_output.xlsx")
                export_to_excel(
                    ticker, company_name, current_price, result, assumptions, forecast_df,
                    sensitivity_df, cash, total_debt, shares_outstanding,
                    scenarios=scenarios, ai_output=ai_output, gap_pct=gap_pct,
                    analyst_info=analyst_info, capm_info=capm_info, comps_info=comps_info,
                    monte_carlo_info=monte_carlo_info, backtest_info=backtest_info,
                    wacc=wacc, terminal_growth=terminal_growth,
                    output_path=output_path,
                )
                with open(output_path, "rb") as f:
                    excel_bytes = f.read()

        st.success("Analysis complete.")
        st.download_button(
            "Download Full Excel Workbook",
            data=excel_bytes,
            file_name=f"{ticker}_dcf_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.exception(e)

else:
    st.info("Set your inputs in the sidebar, then click **Run Analysis**.")
