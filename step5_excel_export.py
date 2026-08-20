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
    for label in ["Summary", "AI Valuation Summary", "DCF Forecast",
                  "Sensitivity", "Scenarios"]:
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
                          cash, total_debt, shares_outstanding):
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

    _autofit_columns(ws)


# ---------------------------------------------------------------
# AI Valuation Summary sheet
# ---------------------------------------------------------------
def build_ai_summary_sheet(ws, ticker, company_name, result, current_price,
                             gap_pct, rating, explanation):
    _draw_banner(ws, f"{ticker} \u2014 AI Valuation Summary", company_name)

    r = 4
    stars_display = "\u2605" * rating["stars"] + "\u2606" * (5 - rating["stars"])
    ws.cell(row=r, column=1, value=stars_display).font = Font(name=FONT_NAME, size=24, color=GOLD, bold=True)
    ws.cell(row=r, column=4, value=rating["label"]).font = Font(name=FONT_NAME, size=16, bold=True, color=NAVY)
    ws.row_dimensions[r].height = 32
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

    ws.cell(row=r, column=1, value="AI-Generated Explanation").font = SECTION_FONT
    for c in range(1, 9):
        ws.cell(row=r, column=c).fill = SECTION_FILL
    r += 1
    r = _draw_wrapped_box(ws, r, explanation, chars_per_line=100)
    r += 1

    r = _draw_wrapped_box(ws, r,
        "Not investment advice. See the Cover sheet for the full disclaimer.",
        fill=AMBER_FILL_STYLE, border=GOLD_BORDER, font=DISCLAIMER_FONT, chars_per_line=95)

    for col_letter, width in zip("ABCDEFGH", [22, 16, 14, 14, 14, 14, 14, 14]):
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
# Assemble workbook
# ---------------------------------------------------------------
def export_to_excel(ticker, company_name, current_price, result, assumptions, forecast_df,
                     sensitivity_df, cash, total_debt, shares_outstanding,
                     scenarios=None, ai_output=None, gap_pct=None,
                     output_path="dcf_output.xlsx"):
    wb = Workbook()

    cover_ws = wb.active
    cover_ws.title = "Cover"
    build_cover_sheet(cover_ws, ticker, company_name)

    summary_ws = wb.create_sheet("Summary")
    build_summary_sheet(summary_ws, ticker, company_name, current_price, result,
                         assumptions, cash, total_debt, shares_outstanding)

    if ai_output is not None:
        ai_ws = wb.create_sheet("AI Valuation Summary")
        build_ai_summary_sheet(ai_ws, ticker, company_name, result, current_price,
                                 gap_pct, ai_output["rating"], ai_output["explanation"])

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

    ai_output = None
    if args.with_ai:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("--with-ai was set but ANTHROPIC_API_KEY is not set. Skipping AI sheet.")
        else:
            from step6_ai_summary import generate_gap_explanation
            print("Generating AI valuation summary (this calls the Anthropic API)...")
            ai_output = generate_gap_explanation(
                ticker, df, assumptions, result, current_price, stock_info,
                args.wacc, args.terminal_growth,
            )

    export_to_excel(ticker, company_name, current_price, result, assumptions, forecast_df,
                     sensitivity_df, cash, total_debt, shares_outstanding,
                     scenarios=scenarios, ai_output=ai_output, gap_pct=gap_pct,
                     output_path=f"{ticker}_dcf_output.xlsx")
