"""
Shared default constants
------------------------------
Single source of truth for values that were previously repeated as
hardcoded literals across step3_dcf_engine.py, step5_excel_export.py, and
capm_wacc.py (e.g. tax_rate=0.21 appeared as a separate default in five
different places). Change a default here once, instead of hunting down
every copy.
"""

DEFAULT_TAX_RATE = 0.21
DEFAULT_WACC = 0.09
DEFAULT_TERMINAL_GROWTH = 0.025
DEFAULT_FORECAST_YEARS = 5

DEFAULT_EQUITY_RISK_PREMIUM = 0.05
DEFAULT_RISK_FREE_RATE = 0.04   # fallback if a live Treasury yield pull fails
DEFAULT_CREDIT_SPREAD = 0.015   # fallback pre-tax cost of debt = risk-free rate + this

DEFAULT_SENSITIVITY_WACC_RANGE = [0.07, 0.08, 0.09, 0.10, 0.11]
DEFAULT_SENSITIVITY_GROWTH_RANGE = [0.015, 0.02, 0.025, 0.03, 0.035]
