"""
Step 5: Excel export (premium redesign)
--------------------------------------------
Exports the full DCF analysis into a polished, multi-sheet Excel workbook:
Cover, Summary, AI Valuation Summary (optional), DCF Forecast, Sensitivity,
and Scenario Comparison.

Design note: this workbook contains computed VALUES (from Python), not live
Excel formulas - it's a generated report/output, not a fill-in template the
user edits and recalculates. Formatting conventions below (navy/gold accent
palette, professional font, consistent banners) are chosen for a polished
reading experience, not for the "blue=input, black=formula" convention used
in editable financial models.
"""

import math
from datetime import date
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule

# --- Palette: dark navy + gold accent, a "premium research report" feel ---
NAVY = "0B2545"
NAVY_LIGHT = "13315C"
GOLD = "C9A227"
LIGHT_FILL = "EEF2F7"
AMBER_FILL = "FFF6E3"
WHITE = "FFFFFF"
TEXT_DARK = "1F2937"

FONT_NAME = "Arial"

BANNER_FILL = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
BANNER_TITLE_FONT = Font(name=FONT_NAME, color=WHITE, bold=True, size=20)
BANNER_SUBTITLE_FONT = Font(name=FONT_NAME, color=GOLD, bold=False, size=11)

HEADER_FILL = PatternFill(start_color=NAVY_LIGHT, end_color=NAVY_LIGHT, fill_type="solid")
HEADER_FONT = Font(name=FONT_NAME, color=WHITE, bold=True, size=11)
SECTION_FILL = PatternFill(start_color=LIGHT_FILL, end_color=LIGHT_FILL, fill_type="solid")
SECTION_FONT = Font(name=FONT_NAME, color=NAVY, bold=True, size=12)

TITLE_FONT = Font(name=FONT_NAME, bold=True, size=14, color=NAVY)
LABEL_FONT = Font(name=FONT_NAME, bold=True, color=TEXT_DARK)
BODY_FONT = Font(name=FONT_NAME, color=TEXT_DARK, size=10.5)
DISCLAIMER_FONT = Font(name=FONT_NAME, italic=True, color=TEXT_DARK, size=9.5)

THIN_BORDER = Border(*[Side(style="thin", color="D1D5DB")] * 4)
GOLD_BORDER = Border(*[Side(style="thin", color=GOLD)] * 4)
AMBER_FILL_STYLE = PatternFill(start_color=AMBER_FILL, end_color=AMBER_FILL, fill_type="solid")

DISCLAIMER_TEXT = (
    "This workbook is a personal, educational portfolio project. All valuations, ratings, "
    "and AI-generated commentary are outputs of a simplified discounted cash flow model built "
    "on a specific set of assumptions - they are NOT financial advice and should not be relied "
    "upon to make any investment decision. The author accepts no responsibility for decisions "
    "made based on this content. Always consult a licensed financial advisor and conduct your "
    "own research before investing."
)


def _draw_banner(ws, title: str, subtitle: str, num_cols: int = 8, height: int = 42):
    """Full-width dark navy banner with a bold title and a gold subtitle line
    underneath - the visual signature used at the top of every sheet."""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=num_cols)
    for row in (1, 2):
        for col in range(1, num_cols + 1):
            ws.cell(row=row, column=col).fill = BANNER_FILL
    ws.cell(row=1, column=1, value=title).font = BANNER_TITLE_FONT
    ws.cell(row=1, column=1).alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.cell(row=2, column=1, value=subtitle).font = BANNER_SUBTITLE_FONT
    ws.cell(row=2, column=1).alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = height
    ws.row_dimensions[2].height = 20


def _draw_wrapped_box(ws, start_row: int, text: str, num_cols: int = 8,
                       fill=None, border=THIN_BORDER, font=BODY_FONT,
                       chars_per_line: int = 100) -> int:
    """Merge a block of cells, write wrapped text into it, and auto-size the
    row height based on estimated line count. Returns the row AFTER the box."""
    lines = max(2, math.ceil(len(text) / chars_per_line))
    height = lines * 15 + 10
    ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row, end_column=num_cols)
    cell = ws.cell(row=start_row, column=1, value=text)
    cell.font = font
    cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left", indent=1)
    if fill:
        for col in range(1, num_cols + 1):
            ws.cell(row=start_row, column=col).fill = fill
    ws.row_dimensions[start_row].height = height
    return start_row + 1


def _style_header_row(ws, row_num: int, num_cols: int):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER


def _autofit_columns(ws, min_width=10, max_width=30):
    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        col_letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[col_letter].width = min(max(length + 2, min_width), max_width)


# ---------------------------------------------------------------
# Cover sheet
# ---------------------------------------------------------------
def build_cover_sheet(ws, ticker: str, company_name: str):
    ws.sheet_view.showGridLines = False
    _draw_banner(ws, "AI-Assisted DCF Valuation Tool",
                 f"{company_name} ({ticker})  |  Generated {date.today().strftime('%d %B %Y')}",
                 height=54)

    r = 5
    ws.cell(row=r, column=1, value="About this workbook").font = SECTION_FONT
    for c in range(1, 9):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1
    r = _draw_wrapped_box(ws, r,
        "A Python-built pipeline that pulls live financial data, forecasts free cash flow, "
        "runs a discounted cash flow valuation with WACC/terminal-growth sensitivity analysis, "
        "and uses an AI layer to explain (never generate) the resulting numbers. Built as a "
        "personal portfolio project applying valuation methods from an investment analyst "
        "internship in a reproducible, code-based form.")
    r += 1

    ws.cell(row=r, column=1, value="Contents").font = SECTION_FONT
    for c in range(1, 9):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1
    for label in ["Summary", "Live DCF (Editable)", "Analyst Insights", "AI Valuation Summary",
                  "DCF Forecast", "Sensitivity", "Scenarios"]:
        ws.cell(row=r, column=1, value=f"\u2022  {label}").font = BODY_FONT
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="Important Disclaimer").font = SECTION_FONT
    for c in range(1, 9):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1
    r = _draw_wrapped_box(ws, r, DISCLAIMER_TEXT, fill=AMBER_FILL_STYLE,
                           border=GOLD_BORDER, font=DISCLAIMER_FONT, chars_per_line=95)

    for col_letter, width in zip("ABCDEFGH", [4, 16, 16, 16, 16, 16, 16, 16]):
        ws.column_dimensions[col_letter].width = width


# ---------------------------------------------------------------
# Summary sheet
# ---------------------------------------------------------------
def build_summary_sheet(ws, ticker, company_name, current_price, result, assumptions,
                          cash, total_debt, shares_outstanding, capm_info=None):
    _draw_banner(ws, f"{ticker} \u2014 Valuation Summary", company_name)

    upside = (result["implied_share_price"] / current_price - 1) * 100
    rows = [
        ("Current Price", current_price, "$#,##0.00"),
        ("Implied Share Price (DCF)", result["implied_share_price"], "$#,##0.00"),
        ("Upside / (Downside)", upside / 100, "0.0%"),
        ("", None, None),
        ("Enterprise Value", result["enterprise_value"], "$#,##0,,\" M\""),
        ("Equity Value", result["equity_value"], "$#,##0,,\" M\""),
        ("Cash", cash, "$#,##0,,\" M\""),
        ("Total Debt", total_debt, "$#,##0,,\" M\""),
        ("Shares Outstanding", shares_outstanding, "#,##0,,\" M\""),
        ("", None, None),
        ("Key Assumptions", None, None),
        ("Revenue Growth", assumptions["avg_revenue_growth"], "0.0%"),
        ("EBIT Margin", assumptions["avg_ebit_margin"], "0.0%"),
        ("Capex % of Revenue", assumptions["avg_capex_pct_revenue"], "0.0%"),
        ("D&A % of Revenue", assumptions["avg_da_pct_revenue"], "0.0%"),
        ("NWC % of Revenue", assumptions.get("avg_nwc_pct_revenue"), "0.0%"),
    ]

    r = 4
    for label, value, fmt in rows:
        is_section = label == "Key Assumptions"
        cell = ws.cell(row=r, column=1, value=label)
        cell.font = SECTION_FONT if is_section else LABEL_FONT
        if is_section:
            for c in range(1, 4):
                ws.cell(row=r, column=c).fill = SECTION_FILL
        if value is not None:
            vcell = ws.cell(row=r, column=2, value=value)
            if fmt:
                vcell.number_format = fmt
            vcell.font = BODY_FONT
        r += 1

    if capm_info:
        r += 1
        ws.cell(row=r, column=1, value="Suggested WACC (CAPM) \u2014 for reference").font = SECTION_FONT
        for c in range(1, 4):
            ws.cell(row=r, column=c).fill = SECTION_FILL
        r += 1
        ws.cell(row=r, column=1,
                value="This is a data-driven starting point, not an automatic override. "
                      "The WACC actually used in this valuation is shown above under Key Assumptions "
                      "and can be set independently.")
        ws.cell(row=r, column=1).font = DISCLAIMER_FONT
        ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        ws.row_dimensions[r].height = 28
        r += 1

        capm_rows = [
            ("Beta" + (" (default: not available)" if capm_info["beta_was_missing"] else ""),
             capm_info["beta"], "0.00"),
            ("Risk-Free Rate (10Y Treasury)", capm_info["risk_free_rate"], "0.00%"),
            ("Equity Risk Premium", capm_info["equity_risk_premium"], "0.00%"),
            ("Cost of Equity", capm_info["cost_of_equity"], "0.00%"),
            ("Cost of Debt (after-tax)", capm_info["cost_of_debt_aftertax"], "0.00%"),
            ("Weight of Equity", capm_info["weight_equity"], "0.0%"),
            ("Weight of Debt", capm_info["weight_debt"], "0.0%"),
            ("Suggested WACC (CAPM)", capm_info["wacc"], "0.00%"),
        ]
        for label, value, fmt in capm_rows:
            is_result = label == "Suggested WACC (CAPM)"
            ws.cell(row=r, column=1, value=label).font = (
                Font(name=FONT_NAME, bold=True, color=NAVY) if is_result else LABEL_FONT
            )
            vcell = ws.cell(row=r, column=2, value=value)
            vcell.number_format = fmt
            vcell.font = Font(name=FONT_NAME, bold=True, color=NAVY) if is_result else BODY_FONT
            r += 1

    _autofit_columns(ws)


# ---------------------------------------------------------------
# AI Valuation Summary sheet
# ---------------------------------------------------------------
def build_ai_summary_sheet(ws, ticker, company_name, result, current_price,
                             gap_pct, rating, explanation, analyst_info=None):
    _draw_banner(ws, f"{ticker} \u2014 AI Valuation Summary", company_name)

    r = 4
    stars_display = "\u2605" * rating["stars"] + "\u2606" * (5 - rating["stars"])
    ws.cell(row=r, column=1, value=stars_display).font = Font(name=FONT_NAME, size=24, color=GOLD, bold=True)
    ws.cell(row=r, column=4, value=rating["label"]).font = Font(name=FONT_NAME, size=16, bold=True, color=NAVY)
    ws.row_dimensions[r].height = 32
    r += 1
    ws.cell(row=r, column=1,
            value="This rating reflects ONLY this model's own DCF, using conservative unadjusted "
                  "historical-median assumptions - it is a narrower claim than a general investment "
                  "recommendation. See the comparison below.").font = DISCLAIMER_FONT
    ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    ws.row_dimensions[r].height = 28
    r += 2

    metrics = [
        ("Implied Share Price (DCF)", result["implied_share_price"], "$#,##0.00"),
        ("Current Market Price", current_price, "$#,##0.00"),
        ("Gap", gap_pct, "+0.0%;-0.0%"),
    ]
    for label, value, fmt in metrics:
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        vcell = ws.cell(row=r, column=2, value=value)
        vcell.number_format = fmt
        vcell.font = BODY_FONT
        r += 1
    r += 1

    # Model View vs. Street View comparison - makes the divergence between
    # this model's narrow DCF-only claim and broader analyst consensus
    # explicit and intentional, rather than something the reader has to
    # notice and reconcile themselves across separate sheets.
    ws.cell(row=r, column=1, value="Model View vs. Street View").font = SECTION_FONT
    for c in range(1, 6):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1

    headers = ["", "View", "Basis"]
    for col_num, header in enumerate(headers, start=1):
        ws.cell(row=r, column=col_num, value=header)
    _style_header_row(ws, r, 3)
    r += 1

    ws.cell(row=r, column=1, value="Model (this tool)").font = LABEL_FONT
    ws.cell(row=r, column=2, value=f"{rating['stars']}/5 \u2014 {rating['label']}").font = BODY_FONT
    ws.cell(row=r, column=3, value="Unadjusted historical-median DCF only").font = BODY_FONT
    for c in range(1, 4):
        ws.cell(row=r, column=c).border = THIN_BORDER
    r += 1

    street_view, street_basis = "Not available", "\u2014"
    if analyst_info and analyst_info.get("recommendations") is not None:
        try:
            latest = analyst_info["recommendations"].iloc[0]
            counts = {"Strong Buy": latest.get("strongBuy", 0), "Buy": latest.get("buy", 0),
                      "Hold": latest.get("hold", 0), "Sell": latest.get("sell", 0),
                      "Strong Sell": latest.get("strongSell", 0)}
            dominant = max(counts, key=counts.get)
            total = sum(counts.values())
            street_view = f"{dominant} ({counts[dominant]}/{total} analysts)"
            mean_target = analyst_info.get("price_targets", {}).get("mean")
            street_basis = (f"Analyst consensus" + (f", mean target ${mean_target:,.2f}" if mean_target else ""))
        except Exception:
            pass

    ws.cell(row=r, column=1, value="Street (analyst consensus)").font = LABEL_FONT
    ws.cell(row=r, column=2, value=street_view).font = BODY_FONT
    ws.cell(row=r, column=3, value=street_basis).font = BODY_FONT
    for c in range(1, 4):
        ws.cell(row=r, column=c).border = THIN_BORDER
    r += 2

    ws.cell(row=r, column=1, value="AI-Generated Explanation").font = SECTION_FONT
    for c in range(1, 9):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1
    r = _draw_wrapped_box(ws, r, explanation, chars_per_line=100)
    r += 1

    r = _draw_wrapped_box(ws, r,
        "Not investment advice. See the Cover sheet for the full disclaimer.",
        fill=AMBER_FILL_STYLE, border=GOLD_BORDER, font=DISCLAIMER_FONT, chars_per_line=95)

    for col_letter, width in zip("ABCDEFGH", [24, 26, 32, 14, 14, 14, 14, 14]):
        ws.column_dimensions[col_letter].width = width


# ---------------------------------------------------------------
# DCF Forecast sheet
# ---------------------------------------------------------------
def build_forecast_sheet(ws, ticker, company_name, forecast_df: pd.DataFrame):
    _draw_banner(ws, f"{ticker} \u2014 5-Year Free Cash Flow Forecast", company_name)

    headers = list(forecast_df.columns)
    header_row = 4
    for col_num, header in enumerate(headers, start=1):
        ws.cell(row=header_row, column=col_num, value=header)
    _style_header_row(ws, header_row, len(headers))

    for row_num, (_, row) in enumerate(forecast_df.iterrows(), start=header_row + 1):
        for col_num, value in enumerate(row, start=1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            if col_num > 1:
                cell.number_format = "$#,##0,,\" M\""
            cell.font = BODY_FONT
            cell.border = THIN_BORDER

    _autofit_columns(ws)


# ---------------------------------------------------------------
# Sensitivity sheet
# ---------------------------------------------------------------
def build_sensitivity_sheet(ws, ticker, company_name, sensitivity_df: pd.DataFrame, current_price: float):
    _draw_banner(ws, f"{ticker} \u2014 Sensitivity: Implied Price by WACC / Terminal Growth", company_name)

    ws.cell(row=4, column=1, value=f"Current market price: ${current_price:,.2f}").font = LABEL_FONT

    start_row = 6
    ws.cell(row=start_row, column=1, value="WACC \\ Growth").font = HEADER_FONT
    for col_num, growth in enumerate(sensitivity_df.columns, start=2):
        ws.cell(row=start_row, column=col_num, value=f"{growth:.1%}")
    _style_header_row(ws, start_row, len(sensitivity_df.columns) + 1)

    for row_offset, (wacc, row) in enumerate(sensitivity_df.iterrows(), start=1):
        r = start_row + row_offset
        ws.cell(row=r, column=1, value=f"{wacc:.1%}").font = LABEL_FONT
        for col_offset, value in enumerate(row, start=2):
            cell = ws.cell(row=r, column=col_offset, value=value)
            cell.number_format = "$#,##0.00"
            cell.font = BODY_FONT
            cell.border = THIN_BORDER

    last_col_letter = get_column_letter(1 + len(sensitivity_df.columns))
    data_range = f"B{start_row + 1}:{last_col_letter}{start_row + len(sensitivity_df)}"
    rule = ColorScaleRule(
        start_type="min", start_color="F8696B",
        mid_type="percentile", mid_value=50, mid_color="FFEB84",
        end_type="max", end_color="63BE7B",
    )
    ws.conditional_formatting.add(data_range, rule)

    _autofit_columns(ws)


# ---------------------------------------------------------------
# Scenario Comparison sheet
# ---------------------------------------------------------------
def build_scenario_sheet(ws, ticker, company_name, scenarios: list):
    _draw_banner(ws, f"{ticker} \u2014 Scenario Comparison", company_name)

    ws.cell(row=4, column=1,
            value="Base case uses unadjusted historical median assumptions - the most defensible, "
                  "non-circular estimate. Scenarios below show sensitivity to specific, named judgment calls.")
    ws.cell(row=4, column=1).font = DISCLAIMER_FONT
    ws.cell(row=4, column=1).alignment = Alignment(wrap_text=True)
    ws.merge_cells("A4:E4")
    ws.row_dimensions[4].height = 32

    headers = ["Scenario", "Capex Assumption", "WACC", "Terminal Growth", "Implied Share Price"]
    start_row = 6
    for col_num, header in enumerate(headers, start=1):
        ws.cell(row=start_row, column=col_num, value=header)
    _style_header_row(ws, start_row, len(headers))

    for i, sc in enumerate(scenarios, start=1):
        r = start_row + i
        ws.cell(row=r, column=1, value=sc["label"]).font = BODY_FONT
        ws.cell(row=r, column=2, value=sc.get("capex_label", "Historical median")).font = BODY_FONT
        ws.cell(row=r, column=3, value=sc["wacc"]).number_format = "0.0%"
        ws.cell(row=r, column=4, value=sc["terminal_growth"]).number_format = "0.0%"
        price_cell = ws.cell(row=r, column=5, value=sc["implied_price"])
        price_cell.number_format = "$#,##0.00"
        for c in range(1, 6):
            ws.cell(row=r, column=c).border = THIN_BORDER
            ws.cell(row=r, column=c).font = BODY_FONT

    _autofit_columns(ws)


# ---------------------------------------------------------------
# Analyst Insights sheet
# ---------------------------------------------------------------
def build_analyst_sheet(ws, ticker, company_name, analyst_data: dict):
    _draw_banner(ws, f"{ticker} \u2014 Analyst Insights", company_name)

    r = 4
    ws.cell(row=r, column=1, value="Analyst Price Targets").font = SECTION_FONT
    for c in range(1, 6):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1

    targets = analyst_data.get("price_targets")
    if targets:
        labels = [("Low", "low"), ("Mean", "mean"), ("Current", "current"), ("High", "high")]
        for label, key in labels:
            value = targets.get(key)
            ws.cell(row=r, column=1, value=label).font = LABEL_FONT
            if value is not None:
                vcell = ws.cell(row=r, column=2, value=value)
                vcell.number_format = "$#,##0.00"
                vcell.font = BODY_FONT
            r += 1
    else:
        ws.cell(row=r, column=1, value="Not available for this ticker").font = DISCLAIMER_FONT
        r += 1
    r += 1

    ws.cell(row=r, column=1, value="Analyst Recommendations (most recent period)").font = SECTION_FONT
    for c in range(1, 6):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1

    recs = analyst_data.get("recommendations")
    if recs is not None and len(recs) > 0:
        latest = recs.iloc[0]
        headers = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]
        cols = ["strongBuy", "buy", "hold", "sell", "strongSell"]
        for col_num, header in enumerate(headers, start=1):
            ws.cell(row=r, column=col_num, value=header)
        _style_header_row(ws, r, len(headers))
        r += 1
        for col_num, key in enumerate(cols, start=1):
            cell = ws.cell(row=r, column=col_num, value=int(latest.get(key, 0)))
            cell.font = BODY_FONT
            cell.alignment = Alignment(horizontal="center")
            cell.border = THIN_BORDER
        r += 2
    else:
        ws.cell(row=r, column=1, value="Not available for this ticker").font = DISCLAIMER_FONT
        r += 2

    ws.cell(row=r, column=1, value="Latest Rating Actions").font = SECTION_FONT
    for c in range(1, 6):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1

    ratings = analyst_data.get("latest_ratings")
    if ratings is not None and len(ratings) > 0:
        headers = ["Date", "Firm", "From", "To", "Action"]
        for col_num, header in enumerate(headers, start=1):
            ws.cell(row=r, column=col_num, value=header)
        _style_header_row(ws, r, len(headers))
        r += 1
        for idx, row in ratings.iterrows():
            ws.cell(row=r, column=1, value=str(idx.date()) if hasattr(idx, "date") else str(idx)).font = BODY_FONT
            ws.cell(row=r, column=2, value=row.get("Firm", "")).font = BODY_FONT
            ws.cell(row=r, column=3, value=row.get("FromGrade", "")).font = BODY_FONT
            ws.cell(row=r, column=4, value=row.get("ToGrade", "")).font = BODY_FONT
            ws.cell(row=r, column=5, value=row.get("Action", "")).font = BODY_FONT
            for c in range(1, 6):
                ws.cell(row=r, column=c).border = THIN_BORDER
            r += 1
    else:
        ws.cell(row=r, column=1, value="Not available for this ticker").font = DISCLAIMER_FONT
        r += 1
    r += 1

    r = _draw_wrapped_box(ws, r,
        "Sourced from Yahoo Finance analyst coverage data via yfinance. Reflects third-party "
        "sell-side analyst opinions, not this tool's own DCF output, and not investment advice.",
        fill=AMBER_FILL_STYLE, border=GOLD_BORDER, font=DISCLAIMER_FONT, chars_per_line=95)

    _autofit_columns(ws)


# ---------------------------------------------------------------
# Live DCF sheet - genuine editable Excel formulas, not Python values
# ---------------------------------------------------------------
INPUT_FONT = Font(name=FONT_NAME, color="1D4ED8", bold=True, size=10.5)  # blue = input, per standard modeling convention
INPUT_FILL = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
FORMULA_FONT = Font(name=FONT_NAME, color=TEXT_DARK, size=10.5)


def build_live_dcf_sheet(ws, ticker, company_name, assumptions, cash, total_debt,
                           shares_outstanding, current_price, wacc, terminal_growth,
                           tax_rate=0.21, capm_info=None):
    """A genuinely interactive sheet: blue cells are inputs you can type over
    directly in Excel; everything else is a live formula that recalculates
    automatically. Pre-filled with this run's base-case values, but every
    number here is yours to change - unlike the rest of the workbook (which
    holds the audited, Python-computed, tested numbers), this sheet is a
    sandbox for testing your own assumptions."""
    _draw_banner(ws, f"{ticker} \u2014 Live DCF (Editable)", company_name)

    ws.cell(row=3, column=1,
            value="Edit any blue cell below and every downstream number recalculates automatically "
                  "in Excel. This sheet is a sandbox - it starts pre-filled with the same base-case "
                  "assumptions as the Summary sheet, but nothing here is locked.")
    ws.cell(row=3, column=1).font = DISCLAIMER_FONT
    ws.merge_cells("A3:H3")

    def input_cell(row, col, value, fmt=None):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = INPUT_FONT
        cell.fill = INPUT_FILL
        cell.border = THIN_BORDER
        if fmt:
            cell.number_format = fmt
        return cell

    def formula_cell(row, col, formula, fmt=None):
        cell = ws.cell(row=row, column=col, value=formula)
        cell.font = FORMULA_FONT
        cell.border = THIN_BORDER
        if fmt:
            cell.number_format = fmt
        return cell

    # --- Assumptions block (all inputs) ---
    r = 5
    ws.cell(row=r, column=1, value="Key Assumptions (edit the blue cells)").font = SECTION_FONT
    for c in range(1, 4):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1

    input_rows = {
        "revenue_growth": (r, "Revenue Growth", assumptions["avg_revenue_growth"], "0.0%"),
        "ebit_margin": (r + 1, "EBIT Margin", assumptions["avg_ebit_margin"], "0.0%"),
        "capex_pct": (r + 2, "Capex % of Revenue", assumptions["avg_capex_pct_revenue"], "0.0%"),
        "da_pct": (r + 3, "D&A % of Revenue", assumptions["avg_da_pct_revenue"], "0.0%"),
        "nwc_pct": (r + 4, "NWC % of Revenue", assumptions.get("avg_nwc_pct_revenue", 0), "0.0%"),
        "tax_rate": (r + 5, "Tax Rate", tax_rate, "0.0%"),
        "wacc": (r + 6, "WACC (Discount Rate)", wacc, "0.0%"),
        "terminal_growth": (r + 7, "Terminal Growth Rate", terminal_growth, "0.0%"),
    }
    cell_refs = {}
    for key, (row_num, label, value, fmt) in input_rows.items():
        ws.cell(row=row_num, column=1, value=label).font = LABEL_FONT
        input_cell(row_num, 2, value, fmt)
        cell_refs[key] = f"$B${row_num}"

    if capm_info:
        wacc_row = input_rows["wacc"][0]
        note_cell = ws.cell(row=wacc_row, column=4,
                             value=f"Suggested (CAPM): {capm_info['wacc']:.1%}  \u2014  see Summary sheet for the full breakdown")
        note_cell.font = DISCLAIMER_FONT
        ws.merge_cells(start_row=wacc_row, start_column=4, end_row=wacc_row, end_column=8)

    r = input_rows["terminal_growth"][0] + 2

    base_rows = {
        "latest_revenue": (r, "Latest Actual Revenue", assumptions["latest_revenue"], "$#,##0,,\" M\""),
        "latest_nwc": (r + 1, "Latest Actual NWC", assumptions.get("latest_nwc", 0), "$#,##0,,\" M\""),
        "cash": (r + 2, "Cash", cash, "$#,##0,,\" M\""),
        "total_debt": (r + 3, "Total Debt", total_debt, "$#,##0,,\" M\""),
        "shares": (r + 4, "Shares Outstanding", shares_outstanding, "#,##0,,\" M\""),
        "market_price": (r + 5, "Current Market Price (for comparison)", current_price, "$#,##0.00"),
    }
    for key, (row_num, label, value, fmt) in base_rows.items():
        ws.cell(row=row_num, column=1, value=label).font = LABEL_FONT
        input_cell(row_num, 2, value, fmt)
        cell_refs[key] = f"$B${row_num}"
    r = base_rows["market_price"][0] + 2

    # --- 5-year forecast, as live formulas ---
    ws.cell(row=r, column=1, value="5-Year Forecast (all formulas)").font = SECTION_FONT
    for c in range(1, 7):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1
    header_row = r
    ws.cell(row=header_row, column=1, value="Metric")
    for i in range(5):
        ws.cell(row=header_row, column=2 + i, value=f"Year {i + 1}")
    _style_header_row(ws, header_row, 6)

    rev_row = header_row + 1
    ebit_row = rev_row + 1
    nopat_row = ebit_row + 1
    da_row = nopat_row + 1
    capex_row = da_row + 1
    nwc_level_row = capex_row + 1
    nwc_change_row = nwc_level_row + 1
    fcf_row = nwc_change_row + 1
    disc_row = fcf_row + 1
    pv_row = disc_row + 1

    ws.cell(row=rev_row, column=1, value="Revenue").font = LABEL_FONT
    ws.cell(row=ebit_row, column=1, value="EBIT").font = LABEL_FONT
    ws.cell(row=nopat_row, column=1, value="NOPAT").font = LABEL_FONT
    ws.cell(row=da_row, column=1, value="D&A").font = LABEL_FONT
    ws.cell(row=capex_row, column=1, value="Capex").font = LABEL_FONT
    ws.cell(row=nwc_level_row, column=1, value="NWC Level").font = LABEL_FONT
    ws.cell(row=nwc_change_row, column=1, value="Change in NWC").font = LABEL_FONT
    ws.cell(row=fcf_row, column=1, value="Free Cash Flow").font = LABEL_FONT
    ws.cell(row=disc_row, column=1, value="Discount Factor").font = LABEL_FONT
    ws.cell(row=pv_row, column=1, value="PV of FCF").font = LABEL_FONT

    for i in range(5):
        col = 2 + i
        col_letter = get_column_letter(col)
        prev_col_letter = get_column_letter(col - 1)

        rev_formula = (f"={cell_refs['latest_revenue']}*(1+{cell_refs['revenue_growth']})" if i == 0
                        else f"={prev_col_letter}{rev_row}*(1+{cell_refs['revenue_growth']})")
        formula_cell(rev_row, col, rev_formula, "$#,##0,,\" M\"")
        formula_cell(ebit_row, col, f"={col_letter}{rev_row}*{cell_refs['ebit_margin']}", "$#,##0,,\" M\"")
        formula_cell(nopat_row, col, f"={col_letter}{ebit_row}*(1-{cell_refs['tax_rate']})", "$#,##0,,\" M\"")
        formula_cell(da_row, col, f"={col_letter}{rev_row}*{cell_refs['da_pct']}", "$#,##0,,\" M\"")
        formula_cell(capex_row, col, f"={col_letter}{rev_row}*{cell_refs['capex_pct']}", "$#,##0,,\" M\"")
        formula_cell(nwc_level_row, col, f"={col_letter}{rev_row}*{cell_refs['nwc_pct']}", "$#,##0,,\" M\"")

        nwc_change_formula = (f"={col_letter}{nwc_level_row}-{cell_refs['latest_nwc']}" if i == 0
                                else f"={col_letter}{nwc_level_row}-{prev_col_letter}{nwc_level_row}")
        formula_cell(nwc_change_row, col, nwc_change_formula, "$#,##0,,\" M\"")

        formula_cell(fcf_row, col,
                     f"={col_letter}{nopat_row}+{col_letter}{da_row}-{col_letter}{capex_row}-{col_letter}{nwc_change_row}",
                     "$#,##0,,\" M\"")
        formula_cell(disc_row, col, f"=1/(1+{cell_refs['wacc']})^{i + 1}", "0.0000")
        formula_cell(pv_row, col, f"={col_letter}{fcf_row}*{col_letter}{disc_row}", "$#,##0,,\" M\"")

    r = pv_row + 2

    # --- Valuation output, as live formulas ---
    ws.cell(row=r, column=1, value="Valuation (all formulas)").font = SECTION_FONT
    for c in range(1, 3):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1

    last_col_letter = get_column_letter(1 + 5)  # column F = year 5

    pv_explicit_row = r
    ws.cell(row=r, column=1, value="PV of Explicit Period FCFs").font = LABEL_FONT
    formula_cell(r, 2, f"=SUM(B{pv_row}:{last_col_letter}{pv_row})", "$#,##0,,\" M\"")
    r += 1

    tv_row = r
    ws.cell(row=r, column=1, value="Terminal Value").font = LABEL_FONT
    formula_cell(r, 2, f"={last_col_letter}{fcf_row}*(1+{cell_refs['terminal_growth']})/({cell_refs['wacc']}-{cell_refs['terminal_growth']})", "$#,##0,,\" M\"")
    r += 1

    pv_tv_row = r
    ws.cell(row=r, column=1, value="PV of Terminal Value").font = LABEL_FONT
    formula_cell(r, 2, f"=B{tv_row}*{last_col_letter}{disc_row}", "$#,##0,,\" M\"")
    r += 1

    ev_row = r
    ws.cell(row=r, column=1, value="Enterprise Value").font = LABEL_FONT
    formula_cell(r, 2, f"=B{pv_explicit_row}+B{pv_tv_row}", "$#,##0,,\" M\"")
    r += 1

    eq_row = r
    ws.cell(row=r, column=1, value="Equity Value (EV - Debt + Cash)").font = LABEL_FONT
    formula_cell(r, 2, f"=B{ev_row}-{cell_refs['total_debt']}+{cell_refs['cash']}", "$#,##0,,\" M\"")
    r += 2

    price_row = r
    ws.cell(row=r, column=1, value="Implied Share Price").font = Font(name=FONT_NAME, bold=True, size=13, color=NAVY)
    price_cell = formula_cell(r, 2, f"=B{eq_row}/{cell_refs['shares']}", "$#,##0.00")
    price_cell.font = Font(name=FONT_NAME, bold=True, size=13, color=NAVY)
    r += 1

    ws.cell(row=r, column=1, value="vs. Current Market Price").font = LABEL_FONT
    formula_cell(r, 2, f"=B{price_row}/{cell_refs['market_price']}-1", "+0.0%;-0.0%")

    for col_letter, width in zip("ABCDEFGH", [32, 16, 16, 16, 16, 16, 12, 12]):
        ws.column_dimensions[col_letter].width = width
def export_to_excel(ticker, company_name, current_price, result, assumptions, forecast_df,
                     sensitivity_df, cash, total_debt, shares_outstanding,
                     scenarios=None, ai_output=None, gap_pct=None, analyst_info=None,
                     wacc=0.09, terminal_growth=0.025, tax_rate=0.21, capm_info=None,
                     output_path="dcf_output.xlsx"):
    wb = Workbook()

    cover_ws = wb.active
    cover_ws.title = "Cover"
    build_cover_sheet(cover_ws, ticker, company_name)

    summary_ws = wb.create_sheet("Summary")
    build_summary_sheet(summary_ws, ticker, company_name, current_price, result,
                         assumptions, cash, total_debt, shares_outstanding, capm_info=capm_info)

    live_ws = wb.create_sheet("Live DCF")
    build_live_dcf_sheet(live_ws, ticker, company_name, assumptions, cash, total_debt,
                          shares_outstanding, current_price, wacc, terminal_growth, tax_rate,
                          capm_info=capm_info)

    if analyst_info is not None:
        analyst_ws = wb.create_sheet("Analyst Insights")
        build_analyst_sheet(analyst_ws, ticker, company_name, analyst_info)

    if ai_output is not None:
        ai_ws = wb.create_sheet("AI Valuation Summary")
        build_ai_summary_sheet(ai_ws, ticker, company_name, result, current_price,
                                 gap_pct, ai_output["rating"], ai_output["explanation"],
                                 analyst_info=analyst_info)

    forecast_ws = wb.create_sheet("DCF Forecast")
    build_forecast_sheet(forecast_ws, ticker, company_name, forecast_df)

    sensitivity_ws = wb.create_sheet("Sensitivity")
    build_sensitivity_sheet(sensitivity_ws, ticker, company_name, sensitivity_df, current_price)

    if scenarios:
        scenario_ws = wb.create_sheet("Scenarios")
        build_scenario_sheet(scenario_ws, ticker, company_name, scenarios)

    wb.save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    import argparse
    import os
    import yfinance as yf
    from step3_dcf_engine import get_dcf_inputs, get_historical_assumptions, forecast_free_cash_flow, calculate_dcf_valuation
    from step4_sensitivity import build_sensitivity_table

    parser = argparse.ArgumentParser(description="Export a full DCF analysis to Excel.")
    parser.add_argument("--ticker", default="MSFT", help="Stock ticker, e.g. MSFT")
    parser.add_argument("--wacc", type=float, default=0.09, help="Base case discount rate")
    parser.add_argument("--terminal-growth", type=float, default=0.025, dest="terminal_growth",
                         help="Base case terminal growth rate")
    parser.add_argument("--capex-override", type=float, default=None, dest="capex_override",
                         help="Optional: manually set capex as %% of revenue for an alternate scenario.")
    parser.add_argument("--with-ai", action="store_true", dest="with_ai",
                         help="Include the AI Valuation Summary sheet (calls the Anthropic API - "
                              "requires ANTHROPIC_API_KEY to be set, and incurs a small API cost).")
    args = parser.parse_args()

    ticker = args.ticker
    df = get_dcf_inputs(ticker)

    assumptions = get_historical_assumptions(df)
    forecast_df = forecast_free_cash_flow(assumptions)

    latest_year = assumptions["latest_year"]
    cash = df.loc["Cash", latest_year]
    total_debt = df.loc["Total Debt", latest_year]
    stock_info = yf.Ticker(ticker).info
    shares_outstanding = stock_info.get("sharesOutstanding")
    current_price = stock_info.get("currentPrice")
    company_name = stock_info.get("longName", ticker)

    result = calculate_dcf_valuation(
        forecast_df, wacc=args.wacc, terminal_growth=args.terminal_growth,
        cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
    )
    gap_pct = result["implied_share_price"] / current_price - 1

    sensitivity_df = build_sensitivity_table(
        forecast_df, cash, total_debt, shares_outstanding,
        wacc_range=[0.07, 0.08, 0.09, 0.10, 0.11],
        growth_range=[0.015, 0.02, 0.025, 0.03, 0.035],
    )

    def run_scenario(label, wacc, terminal_growth, capex_override=None):
        sc_overrides = {"avg_capex_pct_revenue": capex_override} if capex_override is not None else None
        sc_assumptions = get_historical_assumptions(df, overrides=sc_overrides)
        sc_forecast = forecast_free_cash_flow(sc_assumptions)
        sc_result = calculate_dcf_valuation(
            sc_forecast, wacc=wacc, terminal_growth=terminal_growth,
            cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
        )
        return {
            "label": label,
            "capex_label": f"{capex_override:.0%}" if capex_override is not None else "Historical median",
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "implied_price": sc_result["implied_share_price"],
        }

    scenarios = [
        run_scenario("Base case", args.wacc, args.terminal_growth),
        run_scenario(f"Lower WACC ({args.wacc - 0.02:.1%})", args.wacc - 0.02, args.terminal_growth),
        run_scenario(f"Higher WACC ({args.wacc + 0.02:.1%})", args.wacc + 0.02, args.terminal_growth),
    ]
    if args.capex_override is not None:
        scenarios.append(run_scenario(
            f"Custom capex override ({args.capex_override:.0%} of revenue)",
            args.wacc, args.terminal_growth, capex_override=args.capex_override,
        ))

    from analyst_data import get_analyst_data
    print("Pulling analyst insights (free, no API key needed)...")
    analyst_info = get_analyst_data(ticker)

    from capm_wacc import compute_capm_wacc
    print("Computing suggested WACC via CAPM (free, no API key needed)...")
    capm_info = compute_capm_wacc(ticker, df, stock_info, tax_rate=0.21)

    ai_output = None
    if args.with_ai:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("--with-ai was set but ANTHROPIC_API_KEY is not set. Skipping AI sheet.")
        else:
            from step6_ai_summary import generate_gap_explanation
            print("Generating AI valuation summary (this calls the Anthropic API)...")
            ai_output = generate_gap_explanation(
                ticker, df, assumptions, result, current_price, stock_info,
                args.wacc, args.terminal_growth, analyst_info=analyst_info,
            )

    export_to_excel(ticker, company_name, current_price, result, assumptions, forecast_df,
                     sensitivity_df, cash, total_debt, shares_outstanding,
                     scenarios=scenarios, ai_output=ai_output, gap_pct=gap_pct,
                     analyst_info=analyst_info, capm_info=capm_info,
                     wacc=args.wacc, terminal_growth=args.terminal_growth,
                     output_path=f"{ticker}_dcf_output.xlsx")
