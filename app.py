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
import io
import tempfile
import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt

from step2_get_financials import (
    get_dcf_inputs, check_currency_mismatch, get_current_price_and_shares, currency_symbol,
)
from fx_conversion import fetch_fx_rate, convert_financial_statements
from step3_dcf_engine import run_dcf_scenario
from step4_sensitivity import build_sensitivity_table
from step5_excel_export import export_to_excel
from analyst_data import get_analyst_data
from capm_wacc import compute_capm_wacc
from step6_ai_summary import compute_valuation_rating
from ticker_lookup import looks_like_ticker, resolve_ticker_candidates
from config import DEFAULT_WACC, DEFAULT_TERMINAL_GROWTH, DEFAULT_SENSITIVITY_WACC_RANGE, DEFAULT_SENSITIVITY_GROWTH_RANGE

st.set_page_config(page_title="AI-Assisted DCF Valuation Tool", layout="wide", page_icon="📈")

# Subtle drop shadow on every bordered container (headline metrics, valuation
# composition, forecast/sensitivity, etc.) - the white/navy color scheme itself
# comes from .streamlit/config.toml, which also fixes every visitor seeing a
# consistent theme regardless of their own light/dark system setting (previously
# this app inherited whichever theme the visitor's OS was set to). A soft, low-
# opacity shadow (rather than the heavier one a dark background can carry) is
# what keeps a white card from just looking outlined against a white page.
st.markdown(
    """
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AI-Assisted DCF Valuation Tool")
st.caption(
    "A personal portfolio project. Not investment advice - see the generated workbook's "
    "Cover sheet for the full disclaimer."
)

# ---------------------------------------------------------------
# Sidebar: all inputs live here
# ---------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:1rem;">'
        '<span style="font-size:1.4rem;line-height:1;">📈</span>'
        '<span style="font-weight:700;letter-spacing:0.04em;font-size:0.95rem;'
        'color:#0B2545;">DCF ENGINE</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.header("Inputs")
    ticker_query = st.text_input(
        "Ticker or company name", value="MSFT",
        help="Know the ticker? Type it directly (e.g. MSFT). Don't know it? "
             "Type the company name instead (e.g. Microsoft) and pick it from the list.",
    ).strip()

    # Fast path: input already looks like a ticker (the common case for
    # anyone who already knows what they want to run) - skip the network
    # round-trip entirely and use it exactly as typed, same behavior as
    # before this lookup existed.
    ticker = ticker_query.upper()
    if ticker_query and not looks_like_ticker(ticker_query):
        with st.spinner(f"Looking up '{ticker_query}'..."):
            candidates = resolve_ticker_candidates(ticker_query)
        if candidates:
            options = [f'{c["symbol"]} — {c["name"]}' for c in candidates]
            choice = st.selectbox("Select the company:", options, key="ticker_candidate_choice")
            ticker = choice.split(" — ")[0]
        else:
            st.caption(
                f"No ticker match found for '{ticker_query}'. This can happen for "
                f"non-US companies (Yahoo Finance's search sometimes needs the "
                f"exchange-listed name, e.g. 'Hermes International' or its ticker "
                f"'RMS.PA' directly) or during a brief Yahoo Finance hiccup - try "
                f"again, try adding the country/exchange, or type the ticker "
                f"symbol directly instead (e.g. MSFT)."
            )

    wacc = st.slider("WACC (discount rate)", 0.03, 0.15, DEFAULT_WACC, 0.005, format="%.3f")
    terminal_growth = st.slider("Terminal growth rate", 0.0, 0.05, DEFAULT_TERMINAL_GROWTH, 0.0025, format="%.4f")

    use_capex_override = st.checkbox("Override capex assumption")
    capex_override = None
    if use_capex_override:
        capex_override = st.slider("Capex override (% of revenue)", 0.0, 0.5, 0.15, 0.01, format="%.2f")

    st.divider()
    st.subheader("Optional add-ons (all free, no API key)")
    include_scenarios = st.checkbox("Management Assumptions (Base/Upside/Downside)")
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

    st.divider()
    st.caption(
        "Built by [Nathan Bellekens](https://www.linkedin.com/in/nathanbellekens) · "
        "[View source on GitHub](https://github.com/Nathan-Bell-Projects/AI-DCF-Valuation-Tool)"
    )


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
            current_price, shares_outstanding = get_current_price_and_shares(stock_info)
            company_name = stock_info.get("longName", ticker)

        if current_price is None or shares_outstanding is None:
            st.error(
                f"Couldn't pull a current price and/or share count for '{ticker}' from "
                f"Yahoo Finance. This is usually a **temporary hiccup on Yahoo's end** "
                f"rather than a problem with the ticker itself - wait a few seconds and "
                f"click **Run Analysis** again. If it keeps failing specifically for this "
                f"ticker, it may not have complete data available through Yahoo Finance."
            )
            st.stop()

        currency_check = check_currency_mismatch(stock_info)
        if currency_check["mismatch"]:
            # Companies like AB InBev trade in one currency (EUR, on
            # Euronext Brussels) but report consolidated financials in
            # another (USD) - a genuine, real-world mismatch, not a data
            # error. Rather than blocking outright (the original,
            # conservative behavior - safe, but meant every non-US company
            # reporting in a foreign currency was simply unusable), convert
            # the financials into the trading currency at the current spot
            # rate and proceed, with a clear disclosure of what was done.
            try:
                with st.spinner(
                    f"Currency mismatch detected ({currency_check['financial_currency']} "
                    f"reported vs {currency_check['trading_currency']} traded) - converting..."
                ):
                    fx_rate = fetch_fx_rate(
                        currency_check["financial_currency"], currency_check["trading_currency"]
                    )
                    df = convert_financial_statements(df, fx_rate)
                st.info(
                    f"**Currency conversion applied for {ticker}.** This stock trades in "
                    f"**{currency_check['trading_currency']}**, but its financial statements are "
                    f"reported in **{currency_check['financial_currency']}**. The financials were "
                    f"converted to {currency_check['trading_currency']} at today's spot rate "
                    f"(1 {currency_check['financial_currency']} = {fx_rate:.4f} "
                    f"{currency_check['trading_currency']}) before running the DCF. This applies "
                    f"one current rate across all historical years rather than each year's own "
                    f"average rate, so treat the result as directionally correct, not "
                    f"to-the-cent precise."
                )
            except Exception as e:
                st.error(
                    f"**Currency mismatch detected for {ticker}** (trades in "
                    f"{currency_check['trading_currency']}, reports in "
                    f"{currency_check['financial_currency']}), and the live currency conversion "
                    f"failed: {e}. This is usually a temporary issue with the free FX rate "
                    f"service - wait a moment and click **Run Analysis** again."
                )
                st.stop()

        sym = currency_symbol(stock_info.get("currency"))

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
        rating = compute_valuation_rating(gap_pct)  # free, rule-based - no API key needed

        # --- Headline metrics, in a bordered card for visual grouping ---
        with st.container(border=True):
            st.subheader(f"{company_name} ({ticker})")
            # Using color instead of the filled/empty star glyph distinction -
            # the outline star character (U+2606) renders visually almost
            # identical to the filled one (U+2605) in Streamlit's bold header
            # font, making "1 star" look like "5 stars" at a glance. Solid
            # gold vs. dim grey stars removes that ambiguity entirely.
            filled_stars = "\u2605" * rating["stars"]
            empty_stars = "\u2605" * (5 - rating["stars"])
            stars_html = (
                f'<span style="color:#C9A227; font-size:1.4rem;">{filled_stars}</span>'
                f'<span style="color:#3A4356; font-size:1.4rem;">{empty_stars}</span>'
            )
            st.markdown(f"#### {stars_html}  {rating['label']}", unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("Current Price", f"{sym}{current_price:,.2f}")
            m2.metric("Implied Price (DCF)", f"{sym}{result['implied_share_price']:,.2f}")
            # Positive gap = DCF implies the stock is worth MORE than the
            # current price (undervalued signal) - Streamlit's default
            # "normal" delta coloring (positive=green) already matches this
            # correctly, no need to invert it.
            m3.metric("Upside / (Downside)", f"{gap_pct:+.1%}", delta=f"{gap_pct:+.1%}")
            st.caption("Rating reflects ONLY this model's own DCF, using conservative "
                       "historical-median assumptions - see Cover sheet in the Excel export "
                       "for the full disclaimer.")

        # Custom styling for the download button - navy fill matches this
        # app's brand palette (same colors used throughout the Excel
        # export). No border at all - a gold border was tried first but
        # read as too decorative/attention-grabbing for a financial tool;
        # a clean solid fill looks more professional.
        st.markdown("""
            <style>
            div[data-testid="stDownloadButton"] button {
                background-color: #0B2545;
                color: white;
                border: none;
                font-size: 1.05rem;
                font-weight: 600;
                padding: 0.7rem 1.5rem;
            }
            div[data-testid="stDownloadButton"] button:hover {
                background-color: #13315C;
                color: #9DBCF2;
            }
            </style>
        """, unsafe_allow_html=True)

        # A placeholder reserves this visual position (right after the
        # headline metrics, before any of the detail sections below) - the
        # actual button gets filled in here later, once the Excel file is
        # ready, using Streamlit's placeholder pattern. This lets the button
        # appear near the top of the page even though building the workbook
        # is one of the last things this script does.
        top_download_placeholder = st.empty()

        with st.spinner("Pulling price history..."):
            try:
                price_history = yf.Ticker(ticker).history(period="1y")["Close"]
                if len(price_history) > 0:
                    # Resample to weekly - a full year of daily closes crams
                    # ~250 x-axis labels into the chart, making them
                    # unreadable. Weekly keeps the trend clear with a clean axis.
                    price_history_weekly = price_history.resample("W").last()
                    st.line_chart(price_history_weekly, use_container_width=True, color="#5B8DEF")
            except Exception:
                pass  # price history is a nice-to-have, never block the rest of the analysis on it

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

        # --- Donut charts: capital structure + analyst recommendations ---
        with st.container(border=True):
            st.markdown("##### Valuation Composition")
            # Detect the actual active theme rather than hardcoding a text
            # color - a fixed white fill is invisible on a light theme
            # (confirmed via testing), and an outline-only workaround looks
            # thin/weak compared to a genuine solid fill. This picks a bold,
            # correctly-contrasting solid color for whichever theme is live.
            try:
                is_dark_theme = st.context.theme.type == "dark"
            except Exception:
                is_dark_theme = True  # sensible fallback matching this app's default palette
            chart_text_color = "white" if is_dark_theme else "#1F2937"
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.caption("Capital Structure (Market Value)")
                fig1, ax1 = plt.subplots(figsize=(3, 3))
                fig1.patch.set_alpha(0)   # fully transparent - blends into the page background
                ax1.patch.set_alpha(0)
                weights = [capm_info["weight_equity"], capm_info["weight_debt"]]
                labels = [f"Equity ({weights[0]:.0%})", f"Debt ({weights[1]:.0%})"]
                ax1.pie(weights, labels=labels, colors=["#5B8DEF", "#C9A227"],
                        wedgeprops=dict(width=0.42), startangle=90,
                        textprops={"color": chart_text_color, "fontsize": 9, "weight": "medium"})
                # Streamlit deprecated passing savefig kwargs (like transparent=True)
                # straight through st.pyplot() - the currently-recommended pattern is
                # to save to an in-memory buffer ourselves and render with st.image().
                buf1 = io.BytesIO()
                fig1.savefig(buf1, format="png", transparent=True, dpi=150, bbox_inches="tight")
                st.image(buf1)

            with chart_col2:
                recs = analyst_info.get("recommendations")
                if recs is not None and len(recs) > 0:
                    st.caption("Analyst Recommendations")
                    latest = recs.iloc[0]
                    categories = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]
                    keys = ["strongBuy", "buy", "hold", "sell", "strongSell"]
                    counts = [int(latest.get(k, 0)) for k in keys]
                    colors = ["#2E7D32", "#5B8DEF", "#C9A227", "#B45309", "#B91C1C"]
                    nonzero_labels = [f"{c} ({v})" for c, v in zip(categories, counts) if v > 0]
                    nonzero_counts = [v for v in counts if v > 0]
                    nonzero_colors = [c for c, v in zip(colors, counts) if v > 0]
                    if nonzero_counts:
                        fig2, ax2 = plt.subplots(figsize=(3, 3))
                        fig2.patch.set_alpha(0)
                        ax2.patch.set_alpha(0)
                        ax2.pie(nonzero_counts, labels=nonzero_labels, colors=nonzero_colors,
                                wedgeprops=dict(width=0.42), startangle=90,
                                textprops={"color": chart_text_color, "fontsize": 9, "weight": "medium"})
                        buf2 = io.BytesIO()
                        fig2.savefig(buf2, format="png", transparent=True, dpi=150, bbox_inches="tight")
                        st.image(buf2)

            if analyst_info.get("price_targets"):
                st.divider()
                st.caption("Analyst Consensus")
                targets = analyst_info["price_targets"]
                a1, a2, a3 = st.columns(3)
                a1.metric("Analyst Low", f"{sym}{targets.get('low', 0):,.2f}")
                a2.metric("Analyst Mean", f"{sym}{targets.get('mean', 0):,.2f}")
                a3.metric("Analyst High", f"{sym}{targets.get('high', 0):,.2f}")

        # --- Forecast & sensitivity, grouped together ---
        with st.container(border=True):
            st.markdown("##### 5-Year Forecast")
            # Display in $ millions with comma separators - raw dollar figures
            # (hundreds of billions for a company like MSFT) are unreadable as
            # plain numbers. Pre-formatting as strings here (rather than relying
            # on a Streamlit NumberColumn format flag for comma-grouping, which
            # isn't guaranteed to behave the same across versions) means the
            # exact displayed text can be verified directly, not assumed.
            display_forecast_df = forecast_df.copy()
            for col in display_forecast_df.columns:
                if col != "Year":
                    display_forecast_df[col] = (display_forecast_df[col] / 1_000_000).apply(
                        lambda v: f"{sym}{v:,.0f}"
                    )
            display_forecast_df = display_forecast_df.rename(
                columns={col: f"{col} ({sym}M)" for col in display_forecast_df.columns if col != "Year"}
            )
            st.dataframe(display_forecast_df, use_container_width=True)

            st.markdown("##### WACC / Terminal Growth Sensitivity")
            st.caption("Colored red-to-green from lowest to highest implied price - matches the "
                       "conditional formatting in the downloaded Excel workbook.")
            # Red-yellow-green heatmap via pandas Styler, matching the Excel
            # sensitivity sheet's conditional formatting - keeps the two
            # outputs visually consistent rather than looking like different
            # tools. background_gradient works on the numeric data; .format()
            # controls the DISPLAYED text without altering the underlying
            # values used for the color scale.
            styled_sensitivity = (
                sensitivity_df.style
                .background_gradient(cmap="RdYlGn", axis=None)
                .format(sym + "{:,.2f}")
            )
            st.dataframe(styled_sensitivity, use_container_width=True)

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
                c1.metric("Implied Price (EV/EBITDA)", f"{sym}{comps_info['implied_price_ev_ebitda']:,.2f}"
                          if comps_info['implied_price_ev_ebitda'] else "N/A")
                c2.metric("Implied Price (P/E)", f"{sym}{comps_info['implied_price_pe']:,.2f}"
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
                mc1.metric("Mean Implied Price", f"{sym}{monte_carlo_info['mean']:,.2f}")
                mc2.metric("5th-95th Percentile", f"{sym}{monte_carlo_info['p5']:,.0f} - {sym}{monte_carlo_info['p95']:,.0f}")
                prob = float((monte_carlo_info["prices"] > current_price).mean())
                mc3.metric("Prob. DCF Exceeds Market Price", f"{prob:.1%}")

        mgmt_scenario_results = None
        if include_scenarios:
            with st.spinner("Building Base/Upside/Downside scenarios from real historical data..."):
                from scenario_planning import run_scenario_valuations
                mgmt_scenario_results = run_scenario_valuations(
                    df, cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
                    wacc=wacc, terminal_growth=terminal_growth,
                )
                st.subheader("Management Assumptions: Base / Upside / Downside")
                st.caption("Upside/Downside are this company's own real best/worst historical years - "
                           "not fabricated percentages.")
                s1, s2, s3 = st.columns(3)
                s1.metric("Downside", f"{sym}{mgmt_scenario_results['downside']['implied_price']:,.2f}")
                s2.metric("Base", f"{sym}{mgmt_scenario_results['base']['implied_price']:,.2f}")
                s3.metric("Upside", f"{sym}{mgmt_scenario_results['upside']['implied_price']:,.2f}")

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
                    scenario_results=mgmt_scenario_results,
                    wacc=wacc, terminal_growth=terminal_growth,
                    output_path=output_path,
                )
                with open(output_path, "rb") as f:
                    excel_bytes = f.read()

        st.success("Analysis complete.")
        # Fill the placeholder reserved near the top of the page, right
        # after the headline metrics - not a new button here, this call
        # updates that earlier-reserved slot so the button visually appears
        # up top, even though the file itself was only just finished building.
        top_download_placeholder.download_button(
            "Download Full Excel Workbook",
            data=excel_bytes,
            file_name=f"{ticker}_dcf_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
            icon=":material/download:",  # clean line icon instead of a colorful emoji -
                                          # reads more professional next to a navy/gold financial tool
        )

    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.exception(e)

else:
    st.markdown("#### Get started")
    st.write(
        "This tool pulls live financial data for any public company and builds a full "
        "DCF valuation - scenario planning, a WACC/growth sensitivity grid, comps, Monte "
        "Carlo simulation, and a backtest of the forecasting methodology itself - then "
        "exports everything into a polished, formula-driven Excel workbook."
    )
    st.caption(
        "Don't have a ticker in mind? Try **MSFT**, **AAPL**, **PG**, or **O** (Realty Income) - "
        "or just type a company name in the sidebar and pick it from the list."
    )
    st.info("Set your inputs in the sidebar, then click **Run Analysis**.")
