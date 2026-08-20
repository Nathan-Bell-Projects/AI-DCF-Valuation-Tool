"""
Step 5: Excel export
-------------------------
Takes everything we've built - the assumptions, forecast, DCF result, and
sensitivity table - and writes it into a clean, formatted Excel workbook
with three sheets: Summary, DCF Forecast, and Sensitivity Table.

This is the step that turns your terminal output into something you can
actually hand to someone or open in an interview.
"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule

# --- Reusable style constants, so formatting stays consistent across sheets ---
HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14)
LABEL_FONT = Font(bold=True)
THIN_BORDER = Border(*[Side(style="thin", color="D1D5DB")] * 4)


def _style_header_row(ws, row_num: int, num_cols: int):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER


def _autofit_columns(ws, min_width=10, max_width=28):
    for col_cells in ws.columns:
        length = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
        col_letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[col_letter].width = min(max(length + 2, min_width), max_width)


def build_summary_sheet(ws, ticker, current_price, result, assumptions,
                          cash, total_debt, shares_outstanding):
    ws["A1"] = f"{ticker} — DCF Valuation Summary"
    ws["A1"].font = TITLE_FONT

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
    ]

    r = 3
    for label, value, fmt in rows:
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        if value is not None:
            cell = ws.cell(row=r, column=2, value=value)
            if fmt:
                cell.number_format = fmt
        r += 1

    _autofit_columns(ws)


def build_forecast_sheet(ws, forecast_df: pd.DataFrame):
    ws["A1"] = "5-Year Free Cash Flow Forecast"
    ws["A1"].font = TITLE_FONT

    headers = list(forecast_df.columns)
    for col_num, header in enumerate(headers, start=1):
        ws.cell(row=3, column=col_num, value=header)
    _style_header_row(ws, 3, len(headers))

    for row_num, (_, row) in enumerate(forecast_df.iterrows(), start=4):
        for col_num, value in enumerate(row, start=1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            if col_num > 1:  # everything except the "Year" column
                cell.number_format = "$#,##0,,\" M\""
            cell.border = THIN_BORDER

    _autofit_columns(ws)


def build_sensitivity_sheet(ws, sensitivity_df: pd.DataFrame, current_price: float):
    ws["A1"] = "Sensitivity: Implied Share Price by WACC / Terminal Growth"
    ws["A1"].font = TITLE_FONT
    ws["A3"] = f"(Current market price: ${current_price:,.2f})"

    start_row = 5
    ws.cell(row=start_row, column=1, value="WACC \\ Growth")
    for col_num, growth in enumerate(sensitivity_df.columns, start=2):
        ws.cell(row=start_row, column=col_num, value=f"{growth:.1%}")
    _style_header_row(ws, start_row, len(sensitivity_df.columns) + 1)

    for row_offset, (wacc, row) in enumerate(sensitivity_df.iterrows(), start=1):
        r = start_row + row_offset
        ws.cell(row=r, column=1, value=f"{wacc:.1%}").font = LABEL_FONT
        for col_offset, value in enumerate(row, start=2):
            cell = ws.cell(row=r, column=col_offset, value=value)
            cell.number_format = "$#,##0.00"
            cell.border = THIN_BORDER

    # Color scale: green where implied price is closest to current market price
    last_col_letter = get_column_letter(1 + len(sensitivity_df.columns))
    data_range = f"B{start_row + 1}:{last_col_letter}{start_row + len(sensitivity_df)}"
    rule = ColorScaleRule(
        start_type="min", start_color="F8696B",
        mid_type="percentile", mid_value=50, mid_color="FFEB84",
        end_type="max", end_color="63BE7B",
    )
    ws.conditional_formatting.add(data_range, rule)

    _autofit_columns(ws)


def build_scenario_sheet(ws, scenarios: list):
    """scenarios: list of dicts with keys 'label', 'capex_override' (or None),
    'wacc', 'terminal_growth', 'implied_price'."""
    ws["A1"] = "Scenario Comparison"
    ws["A1"].font = TITLE_FONT
    ws["A3"] = "Base case uses unadjusted historical median assumptions - the most defensible, non-circular estimate. The scenarios below show how sensitive the valuation is to specific, named judgment calls."
    ws["A3"].alignment = Alignment(wrap_text=True)
    ws.merge_cells("A3:E3")
    ws.row_dimensions[3].height = 40

    headers = ["Scenario", "Capex Assumption", "WACC", "Terminal Growth", "Implied Share Price"]
    start_row = 5
    for col_num, header in enumerate(headers, start=1):
        ws.cell(row=start_row, column=col_num, value=header)
    _style_header_row(ws, start_row, len(headers))

    for i, sc in enumerate(scenarios, start=1):
        r = start_row + i
        ws.cell(row=r, column=1, value=sc["label"])
        ws.cell(row=r, column=2, value=sc.get("capex_label", "Historical median"))
        ws.cell(row=r, column=3, value=sc["wacc"]).number_format = "0.0%"
        ws.cell(row=r, column=4, value=sc["terminal_growth"]).number_format = "0.0%"
        price_cell = ws.cell(row=r, column=5, value=sc["implied_price"])
        price_cell.number_format = "$#,##0.00"
        for c in range(1, 6):
            ws.cell(row=r, column=c).border = THIN_BORDER

    _autofit_columns(ws)


def export_to_excel(ticker, current_price, result, assumptions, forecast_df,
                     sensitivity_df, cash, total_debt, shares_outstanding,
                     scenarios=None, output_path="dcf_output.xlsx"):
    wb = Workbook()

    summary_ws = wb.active
    summary_ws.title = "Summary"
    build_summary_sheet(summary_ws, ticker, current_price, result,
                         assumptions, cash, total_debt, shares_outstanding)

    forecast_ws = wb.create_sheet("DCF Forecast")
    build_forecast_sheet(forecast_ws, forecast_df)

    sensitivity_ws = wb.create_sheet("Sensitivity")
    build_sensitivity_sheet(sensitivity_ws, sensitivity_df, current_price)

    if scenarios:
        scenario_ws = wb.create_sheet("Scenarios")
        build_scenario_sheet(scenario_ws, scenarios)

    wb.save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    import yfinance as yf
    from step3_dcf_engine import get_dcf_inputs, get_historical_assumptions, forecast_free_cash_flow, calculate_dcf_valuation
    from step4_sensitivity import build_sensitivity_table

    ticker = "MSFT"
    df = get_dcf_inputs(ticker)

    # OFFICIAL BASE CASE: unadjusted historical median assumptions.
    # This is the defensible number - not tuned to match the market price.
    assumptions = get_historical_assumptions(df)
    forecast_df = forecast_free_cash_flow(assumptions)

    latest_year = assumptions["latest_year"]
    cash = df.loc["Cash", latest_year]
    total_debt = df.loc["Total Debt", latest_year]
    stock_info = yf.Ticker(ticker).info
    shares_outstanding = stock_info.get("sharesOutstanding")
    current_price = stock_info.get("currentPrice")

    result = calculate_dcf_valuation(
        forecast_df, wacc=0.09, terminal_growth=0.025,
        cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
    )

    sensitivity_df = build_sensitivity_table(
        forecast_df, cash, total_debt, shares_outstanding,
        wacc_range=[0.07, 0.08, 0.09, 0.10, 0.11],
        growth_range=[0.015, 0.02, 0.025, 0.03, 0.035],
    )

    # Build the scenario comparison: base case vs. named judgment-call adjustments
    scenarios = []
    scenario_defs = [
        ("Base case", None, 0.09, 0.025),
        ("Lower capex assumption (AI spend treated as temporary)", 0.15, 0.09, 0.025),
        ("Lower WACC / higher growth (market-implied)", None, 0.07, 0.02),
        ("Combined: lower capex + market-implied WACC/growth", 0.15, 0.07, 0.02),
    ]
    for label, capex_ov, wacc, growth in scenario_defs:
        sc_overrides = {"avg_capex_pct_revenue": capex_ov} if capex_ov else None
        sc_assumptions = get_historical_assumptions(df, overrides=sc_overrides)
        sc_forecast = forecast_free_cash_flow(sc_assumptions)
        sc_result = calculate_dcf_valuation(
            sc_forecast, wacc=wacc, terminal_growth=growth,
            cash=cash, total_debt=total_debt, shares_outstanding=shares_outstanding,
        )
        scenarios.append({
            "label": label,
            "capex_label": f"{capex_ov:.0%}" if capex_ov else "Historical median",
            "wacc": wacc,
            "terminal_growth": growth,
            "implied_price": sc_result["implied_share_price"],
        })

    export_to_excel(ticker, current_price, result, assumptions, forecast_df,
                     sensitivity_df, cash, total_debt, shares_outstanding,
                     scenarios=scenarios, output_path=f"{ticker}_dcf_output.xlsx")