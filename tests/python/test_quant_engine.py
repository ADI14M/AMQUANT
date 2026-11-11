from math import exp

import numpy as np
import pytest

from quant_engine.bayesian import beta_bernoulli_update
from quant_engine.foundations import crr_binomial, option_payoff, option_profit
from quant_engine.options import black_scholes, black_scholes_greeks, option_sensitivities
from quant_engine.payoffs import call_payoff, put_payoff
from quant_engine.stochastic import simulate_process


def test_black_scholes_benchmark_and_put_call_parity():
    assert black_scholes(100, 100, 1, 0.05, 0.2) == pytest.approx(10.4506, abs=0.001)
    call = black_scholes(100, 105, 0.75, 0.03, 0.25, "call", 0.01)
    put = black_scholes(100, 105, 0.75, 0.03, 0.25, "put", 0.01)
    assert call - put == pytest.approx(100 * exp(-0.01 * 0.75) - 105 * exp(-0.03 * 0.75))


def test_analytical_greeks_match_finite_differences():
    spot, strike, maturity, rate, volatility = 100, 103, 0.8, 0.04, 0.27
    greeks = black_scholes_greeks(spot, strike, maturity, rate, volatility, "call")
    h = 1e-3
    up = black_scholes(spot + h, strike, maturity, rate, volatility)
    down = black_scholes(spot - h, strike, maturity, rate, volatility)
    assert greeks["delta"] == pytest.approx((up - down) / (2 * h), rel=1e-6)
    assert greeks["gamma"] == pytest.approx((up - 2 * greeks["price"] + down) / h**2, rel=1e-4)
    assert black_scholes_greeks(spot, strike, maturity, rate, volatility, "put")["delta"] < 0


def test_crr_converges_and_hedge_replicates_first_step():
    tree = crr_binomial(100, 100, 1, 0.05, 0.2, 300, "call")
    assert tree["price"] == pytest.approx(black_scholes(100, 100, 1, 0.05, 0.2), abs=0.04)
    one_step = crr_binomial(100, 100, 1, 0.05, 0.2, 1, "call")
    dt = 1
    up_spot = 100 * one_step["up_factor"]
    down_spot = 100 * one_step["down_factor"]
    up_payoff = max(up_spot - 100, 0)
    down_payoff = max(down_spot - 100, 0)
    assert one_step["hedge_shares"] * up_spot + one_step["hedge_cash"] * exp(0.05 * dt) == pytest.approx(up_payoff)
    assert one_step["hedge_shares"] * down_spot + one_step["hedge_cash"] * exp(0.05 * dt) == pytest.approx(down_payoff)
    full_tree = crr_binomial(100, 100, 1, 0.05, 0.2, 4, "call", include_hedge_tree=True)
    root_hedge = full_tree["hedge_schedule"][0]
    assert root_hedge["delta"] == pytest.approx(full_tree["delta"])
    assert len(full_tree["hedge_schedule"]) == 4 * 5 // 2


def test_american_put_dominates_european_and_zero_volatility_is_finite():
    european = crr_binomial(80, 100, 1, 0.05, 0.25, 100, "put", "european")
    american = crr_binomial(80, 100, 1, 0.05, 0.25, 100, "put", "american")
    assert american["price"] >= european["price"]
    euro_call = crr_binomial(100, 100, 1, 0.05, 0.2, 100, "call", "european")
    american_call = crr_binomial(100, 100, 1, 0.05, 0.2, 100, "call", "american")
    assert american_call["price"] == pytest.approx(euro_call["price"], abs=0.01)
    deterministic = crr_binomial(90, 100, 1, 0.05, 0, 50, "put")
    assert deterministic["price"] == pytest.approx(100 * exp(-0.05) - 90)


def test_payoff_signs_and_boundaries():
    assert option_payoff(115, 100, "call") == 15
    assert option_profit(115, 100, 5, "call", "short") == -10
    assert call_payoff(100, 100, 3) == -3
    assert put_payoff(100, 100, 3) == -3


def test_beta_bernoulli_prior_likelihood_posterior_and_sequence():
    result = beta_bernoulli_update(2, 2, [1, 0, 1, 1])
    assert result["prior"]["mean"] == pytest.approx(0.5)
    assert result["posterior"]["alpha"] == 5
    assert result["posterior"]["beta"] == 3
    assert result["posterior"]["mean"] == pytest.approx(0.625)
    assert result["posterior"]["credible_interval_95"][0] < 0.625 < result["posterior"]["credible_interval_95"][1]
    assert len(result["sequence"]) == 5
    reordered = beta_bernoulli_update(2, 2, [1, 1, 0, 1])
    assert reordered["posterior"]["mean"] == pytest.approx(result["posterior"]["mean"])
    assert result["density"][75]["likelihood_relative"] == pytest.approx(1)


def test_brownian_and_gbm_reproducibility_and_mc_estimate():
    first = simulate_process("brownian", 100, 0, 0.2, 1, 12, 5, seed=42, mc_paths=1000)
    second = simulate_process("brownian", 100, 0, 0.2, 1, 12, 5, seed=42, mc_paths=1000)
    assert first["paths"] == second["paths"]
    gbm = simulate_process("gbm", 100, 0.05, 0.2, 1, 12, 5, seed=42, strike=100, rate=0.05, mc_paths=10000)
    assert all(point["path_1"] > 0 for point in gbm["paths"])
    estimate = gbm["mc_call_estimate"]
    assert estimate["confidence_interval_95"][0] <= estimate["price"] <= estimate["confidence_interval_95"][1]


def test_model_inputs_reject_invalid_cases():
    with pytest.raises(ValueError):
        black_scholes(100, 100, 1, 0.02, 0.2, "straddle")
    with pytest.raises(ValueError):
        crr_binomial(100, 100, 1, 0.02, 0.2, 0, "call")
    with pytest.raises(ValueError):
        beta_bernoulli_update(1, 1, [1, 2])
    with pytest.raises(ValueError):
        simulate_process("gbm", 100, 0.03, 0.2, 1, 500, 3)
    sweep = option_sensitivities(100, 100, 1, 0.03, 0, points=5)
    assert len(sweep["volatility"]) == 5
    assert len(np.unique([row["input"] for row in sweep["volatility"]])) == 5


def test_explicit_portfolio_benchmarks():
    # Benchmark 1: Black-Scholes call with S=100, K=100, T=1, r=0.05, sigma=0.20, q=0 => ~10.4506
    call_price = black_scholes(100, 100, 1, 0.05, 0.20, kind="call", dividend_yield=0.0)
    assert call_price == pytest.approx(10.4506, abs=0.0005)

    # Benchmark 2: Black-Scholes put with S=100, K=100, T=1, r=0.05, sigma=0.20, q=0 => ~5.5735
    put_price = black_scholes(100, 100, 1, 0.05, 0.20, kind="put", dividend_yield=0.0)
    assert put_price == pytest.approx(5.5735, abs=0.0005)

    # Benchmark 3: Put-call parity for zero dividend: C - P = S - K * exp(-r * T)
    parity_lhs = call_price - put_price
    parity_rhs = 100.0 - 100.0 * exp(-0.05 * 1.0)
    assert parity_lhs == pytest.approx(parity_rhs, abs=1e-7)

    # Benchmark 4: Non-dividend American call should not exceed European call
    euro_c = crr_binomial(100, 100, 1, 0.05, 0.20, 100, "call", "european")
    amer_c = crr_binomial(100, 100, 1, 0.05, 0.20, 100, "call", "american")
    assert amer_c["price"] == pytest.approx(euro_c["price"], abs=1e-5)

    # Benchmark 5: American put strictly dominates European put when early exercise is optimal
    euro_p = crr_binomial(80, 100, 1, 0.05, 0.25, 100, "put", "european")
    amer_p = crr_binomial(80, 100, 1, 0.05, 0.25, 100, "put", "american")
    assert amer_p["price"] > euro_p["price"] + 0.50

    # Benchmark 6: Beta(2,2) updated with four successes and two failures produces Beta(6,4)
    beta_res = beta_bernoulli_update(2, 2, [1, 1, 1, 1, 0, 0])
    assert beta_res["posterior"]["alpha"] == 6.0
    assert beta_res["posterior"]["beta"] == 4.0
    assert beta_res["posterior"]["mean"] == pytest.approx(0.60)

    # Benchmark 7: Seeded simulations are reproducible
    sim_a = simulate_process("gbm", 100, 0.08, 0.20, 1.0, 50, 10, seed=123)
    sim_b = simulate_process("gbm", 100, 0.08, 0.20, 1.0, 50, 10, seed=123)
    assert sim_a["paths"] == sim_b["paths"]
    assert sim_a["terminal_mean"] == pytest.approx(sim_b["terminal_mean"])

    # Benchmark 8: Monte Carlo standard error decreases statistically with N
    mc_small = simulate_process("gbm", 100, 0.05, 0.20, 1.0, 20, 5, seed=10, strike=100, rate=0.05, mc_paths=1000)
    mc_large = simulate_process("gbm", 100, 0.05, 0.20, 1.0, 20, 5, seed=10, strike=100, rate=0.05, mc_paths=40000)
    se_small = mc_small["mc_call_estimate"]["standard_error"]
    se_large = mc_large["mc_call_estimate"]["standard_error"]
    assert se_large < se_small
    assert se_small / se_large == pytest.approx(6.32, rel=0.25)

    # Benchmark 9: ABM and GBM theoretical moments validation
    abm = simulate_process("brownian", 0, 0.5, 0.4, 2.0, 50, 5, seed=777, mc_paths=50000)
    assert abm["terminal_mean"] == pytest.approx(0.5 * 2.0, abs=0.03)
    assert abm["terminal_std"] == pytest.approx(0.4 * (2.0 ** 0.5), abs=0.03)

    gbm = simulate_process("gbm", 100, 0.08, 0.20, 1.0, 50, 5, seed=888, mc_paths=50000)
    theory_mean = 100.0 * exp(0.08)
    theory_std = 100.0 * exp(0.08) * ((exp(0.20**2) - 1.0) ** 0.5)
    assert gbm["terminal_mean"] == pytest.approx(theory_mean, rel=0.02)
    assert gbm["terminal_std"] == pytest.approx(theory_std, rel=0.05)
