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
8. Exports a multi-sheet Excel workbook: Cover, Summary, Analyst Insights, AI Valuation Summary (optional), DCF Forecast, Sensitivity, and Scenario Comparison

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
- **No explicit WACC calculation (CAPM).** WACC is a user input tested via sensitivity analysis, rather than derived from cost of equity/debt — a reasonable simplification for v1, and arguably more honest than a false-precision CAPM calculation with its own embedded assumptions.
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
inspect_fields.py         # Diagnostic tool: lists a ticker's actual yfinance field names
```

## Tested on

Beyond the primary MSFT walkthrough above, the pipeline has been run end-to-end on:
- **O (Realty Income, REIT)** — surfaced and fixed a real crash bug (missing-field handling), added multi-sector field-name fallbacks, and added a guardrail that flags when a negative implied price signals a poor methodology fit (common for REITs) rather than a code error.
- **PG (Procter & Gamble, mature/low-growth)** — confirmed the model handles low-growth, negative-NWC companies correctly; the WACC-vs-market-price sensitivity pattern held here too.
- **CAT (Caterpillar, cyclical industrial)** — confirmed the "historical-median growth lags a fast-moving narrative" pattern generalizes beyond MSFT (CAT's AI-power-demand-driven re-rating shows the same dynamic as MSFT's AI capex story).
- **TSLA (Tesla, extreme growth/optionality stock)** — the largest gap observed (~95%, implied $16.94 vs. market ~$343), driven by revenue growth: Tesla's 2025 revenue actually contracted, so the historical-median assumption (0.9%) is far below the market's forward growth expectation (25.5%). This confirmed the AI explanation layer correctly attributes gap magnitude to the right driver on a case-by-case basis - it identified growth (not WACC or capex) as dominant here, the opposite conclusion from the MSFT run, showing the prompt reasons from each case's actual numbers rather than defaulting to one explanation pattern. Also a clean illustration of DCF's structural limits: a cash-flow-based model cannot capture value the market assigns to future optionality (e.g. robotaxis, autonomy licensing) not yet reflected in financial statements.

## Roadmap

- [x] AI-assisted gap explanation — Step 6 takes the DCF output plus forward-looking analyst estimates and generates a plain-English explanation of why the implied price differs from the market price, grounded strictly in the model's own numbers (WACC, capex assumptions, growth assumptions vs. analyst forward estimates). It never generates or overrides the DCF's own figures.
- [ ] Analyst consensus comparison surfaced directly in the Excel output (currently used only inside the Step 6 prompt)
- [ ] Tested against a broader, more varied set of companies beyond the five covered so far
