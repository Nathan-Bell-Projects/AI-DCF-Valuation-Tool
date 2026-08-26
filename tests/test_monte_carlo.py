"""
Tests for monte_carlo.py

test_verbose_suppression_actually_works is a direct regression test for a
real bug found during manual testing: running 2000 simulations initially
flooded the terminal with thousands of '[override] ...' print lines from
get_historical_assumptions(), because Monte Carlo calls run_dcf_scenario()
in a tight loop. Fixed by adding a verbose parameter that defaults to True
(preserving normal single-run behavior) but is set False inside the
simulation loop.
"""

from monte_carlo import run_monte_carlo, probability_above_price


def test_reproducibility_same_seed_same_results(msft_like_df):
    """Same seed must produce identical results - Monte Carlo without this
    would be untestable and un-debuggable (a different answer every run)."""
    result1 = run_monte_carlo(msft_like_df, cash=20935000000, total_debt=56826000000,
        shares_outstanding=7425545491, wacc_base=0.09, terminal_growth_base=0.025,
        n_simulations=200, random_seed=42)
    result2 = run_monte_carlo(msft_like_df, cash=20935000000, total_debt=56826000000,
        shares_outstanding=7425545491, wacc_base=0.09, terminal_growth_base=0.025,
        n_simulations=200, random_seed=42)

    assert result1["mean"] == result2["mean"]
    assert result1["median"] == result2["median"]
    assert list(result1["prices"]) == list(result2["prices"])


def test_percentiles_are_correctly_ordered(msft_like_df):
    """p5 <= p25 <= p50 <= p75 <= p95, and min/max bracket everything -
    a basic sanity check that the statistics aren't scrambled."""
    result = run_monte_carlo(msft_like_df, cash=20935000000, total_debt=56826000000,
        shares_outstanding=7425545491, wacc_base=0.09, terminal_growth_base=0.025,
        n_simulations=200, random_seed=42)

    assert result["min"] <= result["p5"] <= result["p25"] <= result["p50"] <= result["p75"] <= result["p95"] <= result["max"]


def test_probability_above_price_is_bounded(msft_like_df):
    """A probability must be between 0 and 1 - guards against an inverted
    comparison or a unit error silently producing a nonsense value."""
    result = run_monte_carlo(msft_like_df, cash=20935000000, total_debt=56826000000,
        shares_outstanding=7425545491, wacc_base=0.09, terminal_growth_base=0.025,
        n_simulations=200, random_seed=42)

    prob = probability_above_price(result, 484.0)
    assert 0.0 <= prob <= 1.0

    # A price far below every simulated outcome should give ~100% probability
    prob_low = probability_above_price(result, 1.0)
    assert prob_low > 0.95

    # A price far above every simulated outcome should give ~0% probability
    prob_high = probability_above_price(result, 100000.0)
    assert prob_high < 0.05


def test_verbose_suppression_actually_works(msft_like_df, capsys):
    """Regression test for the real terminal-flooding bug: running a batch
    of simulations must NOT print any '[override]' lines."""
    run_monte_carlo(msft_like_df, cash=20935000000, total_debt=56826000000,
        shares_outstanding=7425545491, wacc_base=0.09, terminal_growth_base=0.025,
        n_simulations=100, random_seed=42)

    captured = capsys.readouterr()
    assert "[override]" not in captured.out, (
        "Monte Carlo simulation must suppress per-iteration override print "
        "statements - this exact issue flooded the terminal with thousands "
        "of lines during manual testing"
    )


def test_mean_centers_near_base_case(msft_like_df):
    """Since growth/WACC/terminal growth are sampled from distributions
    CENTERED on the base-case values, the simulation mean should land
    reasonably close to the known base-case implied price ($281.19),
    not somewhere wildly different."""
    result = run_monte_carlo(msft_like_df, cash=20935000000, total_debt=56826000000,
        shares_outstanding=7425545491, wacc_base=0.09, terminal_growth_base=0.025,
        n_simulations=500, random_seed=42)

    assert 200 < result["mean"] < 400
