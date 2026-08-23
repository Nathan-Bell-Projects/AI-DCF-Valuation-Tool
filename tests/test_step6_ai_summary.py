"""
Tests for compute_valuation_rating() in step6_ai_summary.py

This function had no test coverage at all until now, despite being real,
load-bearing logic - it's used both in the Excel AI Valuation Summary sheet
and, since the Streamlit polish pass, directly in app.py's headline rating
display. Covers every threshold boundary explicitly, since off-by-one
errors at boundaries are the most common bug in this kind of bucketed logic.
"""

import pytest
from step6_ai_summary import compute_valuation_rating


@pytest.mark.parametrize("gap_pct,expected_stars,expected_label", [
    (0.50, 5, "Strongly Undervalued (model)"),
    (0.31, 5, "Strongly Undervalued (model)"),
    (0.20, 4, "Undervalued (model)"),
    (0.11, 4, "Undervalued (model)"),
    (0.05, 3, "Fairly Valued (model)"),
    (0.0, 3, "Fairly Valued (model)"),
    (-0.05, 3, "Fairly Valued (model)"),
    (-0.15, 2, "Overvalued (model)"),
    (-0.29, 2, "Overvalued (model)"),
    (-0.416, 1, "Strongly Overvalued (model)"),  # the real MSFT gap seen throughout testing
    (-0.90, 1, "Strongly Overvalued (model)"),
])
def test_rating_thresholds(gap_pct, expected_stars, expected_label):
    result = compute_valuation_rating(gap_pct)
    assert result["stars"] == expected_stars
    assert result["label"] == expected_label


def test_boundary_exactly_at_30_percent():
    """gap_pct > 0.30 is 5 stars, so exactly 0.30 should NOT qualify -
    verifies the boundary is strictly greater-than, not greater-or-equal."""
    result = compute_valuation_rating(0.30)
    assert result["stars"] == 4  # falls into the 4-star bucket, not 5


def test_boundary_exactly_at_10_percent():
    result = compute_valuation_rating(0.10)
    assert result["stars"] == 3  # falls into the 3-star bucket, not 4


def test_boundary_exactly_at_negative_10_percent():
    """Verified empirically before writing this assertion (not guessed):
    -0.10 is NOT > -0.10, so it falls through to the NEXT bucket (2 stars),
    not the 3-star bucket a naive reading might expect."""
    result = compute_valuation_rating(-0.10)
    assert result["stars"] == 2


def test_boundary_exactly_at_negative_30_percent():
    result = compute_valuation_rating(-0.30)
    assert result["stars"] == 1
