# AI-Assisted DCF Valuation Tool

A Python tool that pulls live financial data for any public company, builds an automated discounted cash flow (DCF) valuation, tests that valuation's sensitivity to key assumptions, and exports everything into a polished Excel workbook.

Built as a portfolio project to apply valuation work from my investment internship (BNP Paribas Fortis) in a reproducible, auditable, code-based form — rather than a one-off Excel file.

## What it does

1. Pulls historical financial statements (income statement, balance sheet, cash flow) for a given ticker via [yfinance](https://github.com/ranaroussi/yfinance)
2. Derives forecast assumptions (revenue growth, EBIT margin, capex, D&A, net working capital) from historical medians
3. Forecasts 5 years of unlevered free cash flow
4. Discounts those cash flows to a present value using a chosen WACC, with a Gordon Growth terminal value
5. Bridges Enterprise Value → Equity Value → implied share price
6. Runs a WACC / terminal growth sensitivity grid
7. Pulls independent analyst price targets, recommendation trends, and recent rating actions (free, no API key)
8. Runs a comparable-company (comps) valuation - EV/EBITDA and P/E multiples vs. user-specified peers - as a second, independent valuation method alongside the DCF (free, no API key)
9. Runs a Monte Carlo simulation (thousands of randomized DCF runs) to show a full probability distribution of outcomes instead of one point estimate - the quantitative version of Morningstar's Uncertainty Rating concept (free, no API key)
10. Backtests the core assumption methodology itself - does historical-median growth/margin actually predict what happens next? Uses leave-future-out validation against the company's own real history (free, no API key)
10. Exports a multi-sheet Excel workbook: Cover, Summary, Live DCF, Analyst Insights, AI Valuation Summary (optional), Comps Valuation, Football Field (chart), Monte Carlo (chart, optional), DCF Forecast, Sensitivity, and Scenario Comparison

## Example output: Microsoft (MSFT)

| Scenario | Capex Assumption | WACC | Terminal Growth | Implied Price |
|---|---|---|---|---|
| **Base case** | Historical median | 9.0% | 2.5% | **$281.19** |
| Capex treated as partly temporary (AI buildout) | 15.0% | 9.0% | 2.5% | $348.44 |
| Market-implied discount rate | Historical median | 7.0% | 2.0% | $378.62 |
| Combined | 15.0% | 7.0% | 2.0% | $468.73 |
| *Actual market price (for reference)* | | | | *~$484* |

**Why the base case is lower than the market price, and why that's the right way to report it:** Microsoft's FY2026 capex spiked sharply (AI/datacenter buildout), which pulls the historical-median capex assumption up and suppresses forecasted free cash flow. Rather than tuning assumptions until the model matches the market price — which would be circular reasoning — the base case uses unadjusted historical medians, and the scenario table shows *how* sensitive the valuation is to specific, named judgment calls (is the capex surge temporary? does Microsoft's wide moat justify a lower discount rate?). The gap itself is the analytical finding, not a bug to be closed.

## Methodology notes & known simplifications

- **Median, not mean, for historical assumptions.** A single anomalous year (like the 2026 capex spike) skews a mean far more than a median.
- **Net working capital is included** (Current Assets − Cash) − Current Liabilities, forecast as a constant % of revenue, with the *change* in NWC subtracted from FCF each year. This was added after benchmarking against a Corporate Finance Institute DCF template, which flagged it as a standard adjustment an earlier version of this tool was missing.
- **Assumptions are overridable via command-line arguments** (`--capex-override`, `--wacc`, `--terminal-growth`), not hardcoded, so every judgment call is explicit and auditable rather than silently baked in.
- **CAPM-based WACC is a suggestion, not an automatic override.** `capm_wacc.py` computes Cost of Equity (Risk-Free Rate + Beta × Equity Risk Premium), an estimated after-tax Cost of Debt (from interest expense / total debt, with a fallback credit-spread if unavailable), and blends them by capital structure weight into a suggested WACC - shown on the Summary and Live DCF sheets alongside, never replacing, the WACC actually used in the valuation. Testing this against real data caught a real bug (an incorrect scaling assumption on the Treasury yield ticker, `^TNX`, that silently produced a ~0.5% risk-free rate instead of ~4.7%) - now guarded with a sanity-bounds check. Testing on PG also surfaced a genuine limitation of CAPM itself: see the PG entry under "Tested on" below.
- **Comps valuation uses user-specified peers, not auto-detection.** Auto-detecting "similar" companies is unreliable; the peer list is an explicit `--peers` argument, same "auditable input over black-box automation" philosophy as everything else in this project. EV/EBITDA and P/E multiples come from yfinance's own pre-computed figures rather than being re-derived. A peer missing a multiple is excluded from that specific median rather than crashing the comparison.
- **The football field chart (openpyxl) needed hand-debugging against real Excel rendering, not just the automated formula-recalc check.** `recalc.py`'s LibreOffice round-trip verifies formulas evaluate correctly, but it does NOT guarantee chart layout/formatting survives identically - in practice it silently altered axis title placement and even swapped explicit `axPos` settings between axes during testing. The chart's category-vs-value axis semantics in openpyxl were also a real source of a bug: `x_axis` is always the category axis and `y_axis` is always the value axis, regardless of visual bar orientation - counter to what the visual layout suggests. Getting this chart right took three rounds of real-Excel-screenshot verification, not just a clean recalc pass.
- **Monte Carlo simulation randomizes revenue growth, WACC, and terminal growth only** (a documented v1 scope decision - these are the DCF's biggest value drivers, per the sensitivity table). EBIT margin, capex %, D&A %, and NWC % stay fixed at their historical-median values. Revenue growth's standard deviation is derived from the company's own historical year-over-year variance, not an arbitrary guess. A real bug was found and fixed here too: an early version printed a debug line every time an override was applied - fine for a single DCF run, but it flooded the terminal with thousands of unreadable lines across a batch of simulations. Fixed with a `verbose` parameter (now threaded through `get_historical_assumptions` and `run_dcf_scenario`), and locked in with a dedicated regression test.
- **Backtesting deliberately does NOT reconstruct historical stock prices or period-accurate WACC/beta.** yfinance's ~4-year financial statement history isn't enough to do that reliably, and a plausible-looking but unverifiable historical price comparison would be worse than not building it. Instead, it tests the assumption methodology directly: does historical-median growth/margin actually predict what happens next, using leave-future-out validation against the company's own real history. **Running this on MSFT independently rediscovered a finding this project already made manually** - the model's bias is negative (it systematically under-predicts) and the error is largest in exactly the year (the most recent one) where the AI-driven capex/growth acceleration outpaced historical trends. Two completely different methods, built weeks apart, arriving at the same conclusion.
- **Not validated for companies with structurally negative growth**, where a perpetuity-growth terminal value is a poor fit regardless of implementation.
- **Single currency assumption.** Financials are used as reported by yfinance; no currency conversion is applied, so non-USD-reporting companies would need manual handling.

## Tech stack

`Python` · `yfinance` · `pandas` · `openpyxl` · `Anthropic Claude API`

## Setup

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**API key requirement — read this before running with `--with-ai`.** Steps 1-5, the base Excel export, and the Analyst Insights data all require **no API key at all** and are free to run. Only the AI Valuation Summary sheet (`--with-ai` flag, or running `step6_ai_summary.py` directly) calls the Anthropic API and requires **your own** Anthropic API key, set as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-key-here"   # Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key-here"
```

This project never embeds or transmits any API key belonging to the original author — each user runs Step 6 against their own Anthropic account and is billed only for their own usage (a handful of cents per run). Get a key at [console.anthropic.com](https://console.anthropic.com) (separate from a claude.ai subscription; a small prepaid credit purchase is required, $5 minimum).

## Usage

```bash
# Base case
python3 step3_dcf_engine.py --ticker MSFT

# With a manual capex override
python3 step3_dcf_engine.py --ticker MSFT --capex-override 0.15

# Custom WACC / terminal growth
python3 step3_dcf_engine.py --ticker MSFT --wacc 0.07 --terminal-growth 0.02

# WACC / terminal growth sensitivity table
python3 step4_sensitivity.py --ticker MSFT

# Generate the full Excel workbook (Summary, Analyst Insights, Forecast, Sensitivity, Scenarios) - no API key needed
python3 step5_excel_export.py --ticker MSFT --wacc 0.09

# Same, but also include the AI Valuation Summary sheet - REQUIRES your own ANTHROPIC_API_KEY
python3 step5_excel_export.py --ticker MSFT --wacc 0.09 --with-ai

# Add comps valuation + football field chart vs. named peers - free, no API key needed
python3 step5_excel_export.py --ticker MSFT --peers GOOGL,ORCL,CRM

# Add a Monte Carlo simulation (distribution of outcomes, not one point estimate) - free, no API key needed
python3 step5_excel_export.py --ticker MSFT --monte-carlo 2000

# Add a backtest of the assumption methodology itself - free, no API key needed
python3 step5_excel_export.py --ticker MSFT --backtest

# AI-generated explanation of the implied-vs-market price gap - REQUIRES your own ANTHROPIC_API_KEY
python3 step6_ai_summary.py --ticker MSFT
```

## Project structure

```
step1_test_setup.py       # Environment/connection test
step2_get_financials.py   # Pull & clean financial statements
step3_dcf_engine.py       # Core DCF: assumptions, forecast, discounting, valuation
step4_sensitivity.py      # WACC / terminal growth sensitivity grid
step5_excel_export.py     # Formatted Excel workbook export (no API key needed; --with-ai adds the AI sheet)
step6_ai_summary.py       # AI-generated explanation of valuation gaps (requires ANTHROPIC_API_KEY)
analyst_data.py           # Free analyst price targets, recommendations, rating actions (no API key)
comps_valuation.py         # EV/EBITDA and P/E comps valuation vs. user-specified peers (no API key)
monte_carlo.py             # Monte Carlo simulation of DCF outcomes (no API key)
backtest.py                 # Tests whether historical-median assumptions actually predict outcomes (no API key)
capm_wacc.py               # CAPM-based suggested WACC calculation (no API key)
inspect_fields.py         # Diagnostic tool: lists a ticker's actual yfinance field names
```

## Tested on

Beyond the primary MSFT walkthrough above, the pipeline has been run end-to-end on:
- **O (Realty Income, REIT)** — surfaced and fixed a real crash bug (missing-field handling), added multi-sector field-name fallbacks, and added a guardrail that flags when a negative implied price signals a poor methodology fit (common for REITs) rather than a code error.
- **PG (Procter & Gamble, mature/low-growth)** — confirmed the model handles low-growth, negative-NWC companies correctly; the WACC-vs-market-price sensitivity pattern held here too. After adding CAPM-based WACC, PG's real beta (0.377) produced a suggested WACC of 6.1% - still below the ~7% found manually to best match the market price. This is consistent with the well-documented "low-beta anomaly" in finance literature: low-beta "quality" stocks like PG tend to trade as if the market requires a higher return than a linear CAPM formula predicts, meaning even a rigorous, data-driven WACC estimate doesn't fully close the gap for this type of company - a genuine limitation of CAPM itself, not just of this implementation.
- **CAT (Caterpillar, cyclical industrial)** — confirmed the "historical-median growth lags a fast-moving narrative" pattern generalizes beyond MSFT (CAT's AI-power-demand-driven re-rating shows the same dynamic as MSFT's AI capex story).
- **TSLA (Tesla, extreme growth/optionality stock)** — the largest gap observed (~95%, implied $16.94 vs. market ~$343), driven by revenue growth: Tesla's 2025 revenue actually contracted, so the historical-median assumption (0.9%) is far below the market's forward growth expectation (25.5%). This confirmed the AI explanation layer correctly attributes gap magnitude to the right driver on a case-by-case basis - it identified growth (not WACC or capex) as dominant here, the opposite conclusion from the MSFT run, showing the prompt reasons from each case's actual numbers rather than defaulting to one explanation pattern. Also a clean illustration of DCF's structural limits: a cash-flow-based model cannot capture value the market assigns to future optionality (e.g. robotaxis, autonomy licensing) not yet reflected in financial statements.

## Testing

A `pytest` suite covers the core valuation logic, and is deliberately built as a record of this project's actual debugging history rather than generic sanity checks - each test is tied to a real bug found and fixed during development (the `None`-vs-`NaN` crash, the REIT capex field-name fallback, the median-vs-mean outlier resistance, the `^TNX` risk-free-rate scaling bug, and a full regression test locking in the known-correct MSFT base-case valuation).

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

All tests run fully offline (no API key, no live network calls - external data sources are mocked) and complete in under a second.

## Roadmap

- [x] AI-assisted gap explanation — Step 6 takes the DCF output plus forward-looking analyst estimates and generates a plain-English explanation of why the implied price differs from the market price, grounded strictly in the model's own numbers (WACC, capex assumptions, growth assumptions vs. analyst forward estimates). It never generates or overrides the DCF's own figures.
- [x] Automated test suite (`pytest`) covering core valuation logic and known past bugs
- [ ] Analyst consensus comparison surfaced directly in the Excel output (currently used only inside the Step 6 prompt)
- [ ] Tested against a broader, more varied set of companies beyond the five covered so far
