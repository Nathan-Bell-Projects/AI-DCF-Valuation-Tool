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
7. Exports a 4-tab Excel workbook: Summary, DCF Forecast, Sensitivity, and Scenario Comparison

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

`Python` · `yfinance` · `pandas` · `openpyxl` · (Claude API integration planned)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
# Base case
python3 step3_dcf_engine.py --ticker MSFT

# With a manual capex override
python3 step3_dcf_engine.py --ticker MSFT --capex-override 0.15

# Custom WACC / terminal growth
python3 step3_dcf_engine.py --ticker MSFT --wacc 0.07 --terminal-growth 0.02

# Generate the full Excel workbook (Summary, Forecast, Sensitivity, Scenarios)
python3 step5_excel_export.py
```

## Project structure

```
step1_test_setup.py       # Environment/connection test
step2_get_financials.py   # Pull & clean financial statements
step3_dcf_engine.py       # Core DCF: assumptions, forecast, discounting, valuation
step4_sensitivity.py      # WACC / terminal growth sensitivity grid
step5_excel_export.py     # Formatted Excel workbook export
```

## Roadmap

- [ ] AI-assisted assumption checking — flag anomalous historical inputs (e.g. the capex spike) automatically, and generate a plain-English summary of the valuation output. The AI layer will comment on numbers the DCF engine has already calculated; it will not generate the financial figures themselves.
- [ ] Analyst consensus comparison — benchmark the model's derived growth assumption against Wall Street forward estimates (available via yfinance)
- [ ] Tested against a broader, more varied set of companies beyond large-cap tech
