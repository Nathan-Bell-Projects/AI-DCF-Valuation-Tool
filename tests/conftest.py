"""
Shared pytest fixtures for all test files.

The MSFT-like dataset here is the SAME data used throughout manual testing
in building this project - reusing it means these tests double as
regression tests against numbers we already know are correct (e.g. the
$281.19 base-case implied share price), not just abstract sanity checks.
"""

import sys
import os
import pandas as pd
import pytest

# Ensure the project root (one level up from tests/) is importable regardless
# of how/where pytest is invoked from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def msft_like_df():
    """4 years of real MSFT figures (in raw dollars, matching what yfinance
    actually returns) - used as the project's standard regression fixture."""
    return pd.DataFrame({
        "2023": {"Revenue": 211915000000, "EBIT": 91279000000, "D&A": 13861000000,
                  "Capex": -28107000000, "Cash": 34704000000, "Total Debt": 59965000000,
                  "Current Assets": 184257000000, "Current Liabilities": 104149000000,
                  "Interest Expense": 1968000000},
        "2024": {"Revenue": 245122000000, "EBIT": 110722000000, "D&A": 20958000000,
                  "Capex": -44477000000, "Cash": 18315000000, "Total Debt": 67127000000,
                  "Current Assets": 159734000000, "Current Liabilities": 125286000000,
                  "Interest Expense": 2935000000},
        "2025": {"Revenue": 281724000000, "EBIT": 126012000000, "D&A": 29433000000,
                  "Capex": -64551000000, "Cash": 30242000000, "Total Debt": 60588000000,
                  "Current Assets": 191131000000, "Current Liabilities": 141218000000,
                  "Interest Expense": 2749000000},
        "2026": {"Revenue": 331839000000, "EBIT": 168985000000, "D&A": 38534000000,
                  "Capex": -115948000000, "Cash": 20935000000, "Total Debt": 56826000000,
                  "Current Assets": 207710000000, "Current Liabilities": 168825000000,
                  "Interest Expense": 2400000000},
    })


@pytest.fixture
def reit_like_df():
    """Simulates a REIT (like Realty Income): capex-equivalent line item is
    'Purchase Of Investment Properties', not 'Capital Expenditure' at all -
    this is the exact scenario that caused a real crash during manual
    testing (before the multi-candidate fallback and NaN fix)."""
    return pd.DataFrame({
        "2024": {"Revenue": 5266000000, "EBIT": 1680000000, "D&A": 1620000000,
                  "Purchase Of Investment Properties": -3800000000,
                  "Cash": 401000000, "Total Debt": 25100000000,
                  "Current Assets": 1350000000, "Current Liabilities": 980000000},
        "2025": {"Revenue": 5749000000, "EBIT": 1820000000, "D&A": 1700000000,
                  "Purchase Of Investment Properties": -4100000000,
                  "Cash": 435000000, "Total Debt": 29346000000,
                  "Current Assets": 1400000000, "Current Liabilities": 1010000000},
    })
