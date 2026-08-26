"""
Tests for fx_conversion.py

Converted from a standalone assert-script into proper pytest test
functions - the original version ran its checks as module-level code,
which meant pytest silently collected 0 test items from this file (no
`test_*` functions to discover), so none of these checks ever showed up
in `pytest tests/ -v` output even though they were passing. Same checks,
now actually visible in the test suite - which matters here more than
usual, since the README explicitly documents this project's testing
discipline as one of its selling points.
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from fx_conversion import fetch_fx_rate, convert_financial_statements


def _mock_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_fetch_fx_rate_builds_correct_request():
    """Mock a response matching Frankfurter's documented format and verify
    both the parsed rate and the actual request parameters sent."""
    mock_resp = _mock_response({
        "amount": 1.0, "base": "JPY", "date": "2026-08-25", "rates": {"USD": 0.0067},
    })
    with patch("fx_conversion.requests.get", return_value=mock_resp) as mock_get:
        rate = fetch_fx_rate("JPY", "USD")

        assert rate == 0.0067
        assert mock_get.call_args.kwargs["params"] == {"base": "JPY", "symbols": "USD"}


def test_same_currency_short_circuits_without_network_call():
    """No API call should be made when converting a currency to itself."""
    with patch("fx_conversion.requests.get") as mock_get:
        rate = fetch_fx_rate("USD", "USD")
        assert rate == 1.0
        mock_get.assert_not_called()


def test_conversion_math_on_realistic_jpy_figures():
    """Sanity check the actual conversion math on realistic SONY-scale JPY
    figures (Sony's real revenue is genuinely in this ballpark in USD terms)."""
    sony_like_jpy = pd.DataFrame({
        "2026": {"Revenue": 13000000000000, "EBIT": 1200000000000, "Cash": 1500000000000},
    })
    converted = convert_financial_statements(sony_like_jpy, rate=0.0067)

    expected_revenue_usd = 13000000000000 * 0.0067
    assert abs(converted.loc["Revenue", "2026"] - expected_revenue_usd) < 1


def test_malformed_response_raises_clear_error_not_silent_crash():
    """A response missing the requested rate should raise a clear ValueError,
    not crash on a KeyError or silently return something wrong."""
    bad_resp = _mock_response({"amount": 1.0, "base": "JPY", "rates": {}})  # missing USD
    with patch("fx_conversion.requests.get", return_value=bad_resp):
        with pytest.raises(ValueError):
            fetch_fx_rate("JPY", "USD")
