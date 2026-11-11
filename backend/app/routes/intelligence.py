"""AMQUANT Research Intelligence: Unified research workflow synthesizing Bayesian inference,
stochastic path generation, binomial lattices, and Black-Scholes-Merton derivatives valuation."""
from math import exp
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.security import execute_guarded_calculation
from quant_engine.bayesian import beta_bernoulli_update
from quant_engine.foundations import crr_binomial
from quant_engine.options import black_scholes_greeks, option_sensitivities
from quant_engine.stochastic import simulate_process

router = APIRouter(prefix="/api/intelligence", tags=["AMQUANT Research Intelligence"])


class IntelligenceRequest(BaseModel):
    asset: str = Field(default="SYNTH_TECH", max_length=20, description="Asset ticker or research label")
    spot: float = Field(default=100.0, gt=0, le=1e7, description="Current asset spot price")
    strike: float = Field(default=100.0, gt=0, le=1e7, description="Option strike price")
    maturity: float = Field(default=1.0, gt=0, le=20, description="Investment horizon in years")
    rate: float = Field(default=0.05, ge=-1, le=1, description="Annualized continuously compounded risk-free rate")
    volatility: float = Field(default=0.20, gt=0, le=5, description="Annualized volatility")
    drift: float = Field(default=0.08, ge=-5, le=5, description="Annualized expected physical drift")
    dividend_yield: float = Field(default=0.0, ge=-1, le=1, description="Continuous dividend yield")
    kind: Literal["call", "put"] = Field(default="call", description="Option contract kind")
    prior_alpha: float = Field(default=2.0, gt=0, le=10000, description="Beta prior alpha (prior successes)")
    prior_beta: float = Field(default=2.0, gt=0, le=10000, description="Beta prior beta (prior failures)")
    observations: list[int] = Field(default=[1, 1, 0, 1, 1, 0, 1], max_length=5000, description="Observed binary regime signals (1 or 0), max 5,000")
    sim_steps: int = Field(default=100, ge=10, le=500, description="Simulation time steps (max 500)")
    sim_paths: int = Field(default=12, ge=2, le=40, description="Displayed sample paths")
    sim_seed: int = Field(default=42, ge=0, description="Random seed for reproducibility")
    mc_paths: int = Field(default=10000, ge=500, le=10000, description="Monte Carlo sample paths (max 10,000)")
    tree_steps: int = Field(default=50, ge=10, le=500, description="Binomial tree time steps (max 500)")


def _compute_intelligence(request: IntelligenceRequest) -> dict[str, object]:
    # 1. Bayesian Evidence Update
    bayesian = beta_bernoulli_update(request.prior_alpha, request.prior_beta, request.observations)
    prior_mean = float(bayesian["prior"]["mean"])
    post_mean = float(bayesian["posterior"]["mean"])
    ci = bayesian["posterior"]["credible_interval_95"]
    succ = int(bayesian["successes"])
    fail = int(bayesian["failures"])
    shift_pct = (post_mean - prior_mean) * 100
    direction = "upward" if shift_pct > 0.05 else "downward" if shift_pct < -0.05 else "neutral"

    shift_summary = (
        f"Prior expectation of {prior_mean:.1%} was updated with {succ} positive and {fail} negative signals across "
        f"{len(request.observations)} observations. Posterior belief shifted {direction} by {abs(shift_pct):.1f}% "
        f"to {post_mean:.1%} with a 95% equal-tailed credible interval of [{ci[0]:.1%}, {ci[1]:.1%}]."
    )

    # 2. Stochastic Simulation (Physical P-Measure vs Risk-Neutral Q-Measure)
    sim_physical = simulate_process(
        process="gbm",
        spot=request.spot,
        drift=request.drift,
        volatility=request.volatility,
        maturity=request.maturity,
        steps=request.sim_steps,
        paths=request.sim_paths,
        seed=request.sim_seed,
        strike=request.strike,
        rate=request.rate,
        mc_paths=request.mc_paths,
        kind=request.kind,
    )

    risk_neutral_drift = request.rate - request.dividend_yield
    sim_risk_neutral = simulate_process(
        process="gbm",
        spot=request.spot,
        drift=risk_neutral_drift,
        volatility=request.volatility,
        maturity=request.maturity,
        steps=request.sim_steps,
        paths=request.sim_paths,
        seed=request.sim_seed + 101,
        strike=request.strike,
        rate=request.rate,
        mc_paths=request.mc_paths,
        kind=request.kind,
    )

    # Theoretical terminal moments for verification
    theory_mean_p = request.spot * exp(request.drift * request.maturity)
    theory_std_p = request.spot * exp(request.drift * request.maturity) * ((exp(request.volatility**2 * request.maturity) - 1.0) ** 0.5)
    theory_mean_q = request.spot * exp(risk_neutral_drift * request.maturity)
    theory_std_q = request.spot * exp(risk_neutral_drift * request.maturity) * ((exp(request.volatility**2 * request.maturity) - 1.0) ** 0.5)

    # 3. Derivatives Valuation Across Frameworks
    bsm_call = black_scholes_greeks(request.spot, request.strike, request.maturity, request.rate, request.volatility, "call", request.dividend_yield)
    bsm_put = black_scholes_greeks(request.spot, request.strike, request.maturity, request.rate, request.volatility, "put", request.dividend_yield)
    bsm_target = bsm_call if request.kind == "call" else bsm_put

    tree_european = crr_binomial(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.tree_steps, request.kind, "european", request.dividend_yield, include_hedge_tree=True)
    tree_american = crr_binomial(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.tree_steps, request.kind, "american", request.dividend_yield)

    mc_estimate = sim_risk_neutral.get("mc_call_estimate")
    mc_price = mc_estimate["price"] if mc_estimate else None
    mc_se = mc_estimate["standard_error"] if mc_estimate else None
    mc_ci = mc_estimate["confidence_interval_95"] if mc_estimate else None

    # Put-Call Parity: C - P = S*exp(-q*T) - K*exp(-r*T)
    parity_forward = request.spot * exp(-request.dividend_yield * request.maturity) - request.strike * exp(-request.rate * request.maturity)
    parity_actual = bsm_call["price"] - bsm_put["price"]
    parity_diff = abs(parity_actual - parity_forward)

    # Early exercise premium (American vs European)
    early_exercise_premium = max(float(tree_american["price"]) - float(tree_european["price"]), 0.0)

    # 4. Sensitivity Grids
    sensitivities = option_sensitivities(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.kind, request.dividend_yield, points=21)

    # 5. Model Comparison Matrix
    models = [
        {
            "model": "Black–Scholes–Merton (European)",
            "price": bsm_target["price"],
            "delta": bsm_target["delta"],
            "assumptions": "Continuous lognormal diffusion, continuous delta hedging, constant volatility",
            "divergence": 0.0,
        },
        {
            "model": f"CRR Binomial Lattice ({request.tree_steps} steps, European)",
            "price": tree_european["price"],
            "delta": tree_european["delta"],
            "assumptions": f"Discrete binomial tree, u={tree_european['up_factor']:.3f}, d={tree_european['down_factor']:.3f}, q_rn={tree_european['risk_neutral_probability']:.3f}",
            "divergence": float(tree_european["price"]) - bsm_target["price"],
        },
        {
            "model": f"CRR Binomial Lattice ({request.tree_steps} steps, American)",
            "price": tree_american["price"],
            "delta": tree_american["delta"],
            "assumptions": f"Dynamic programming with early-exercise check; early exercise premium = ${early_exercise_premium:.4f}",
            "divergence": float(tree_american["price"]) - bsm_target["price"],
        },
    ]
    if mc_price is not None and mc_se is not None:
        models.append({
            "model": f"Risk-Neutral Monte Carlo ({request.mc_paths:,} paths)",
            "price": mc_price,
            "delta": None,
            "assumptions": f"Standard error = ±${mc_se:.4f}, 95% CI = [${mc_ci[0]:.3f}, ${mc_ci[1]:.3f}]",
            "divergence": mc_price - bsm_target["price"],
        })

    # 6. Structured Research Conclusion
    uncertainty_drivers = [
        f"Directional exposure: Delta is {bsm_target['delta']:.3f} (portfolio moves approx ${abs(bsm_target['delta']):.2f} per $1 underlying move).",
        f"Curvature risk: Gamma is {bsm_target['gamma']:.4f}, dictating the delta-hedge rebalancing speed.",
        f"Volatility exposure: Vega is {bsm_target['vega']:.3f} per 1.00 vol (a 1% change shifts option value by approx ${bsm_target['vega'] * 0.01:.4f}).",
        f"Time decay: Theta is {bsm_target['theta']:.3f}/year, eroding approx ${abs(bsm_target['theta']) / 365:.4f}/day.",
        f"Bayesian uncertainty: The regime success probability carries an equal-tailed 95% credible range of {ci[1] - ci[0]:.1%}.",
    ]

    model_limitations = [
        "Geometric Brownian Motion assumes stationary volatility and continuous lognormal returns, understating tail risk and market jumps.",
        "Risk-neutral pricing assumes frictionless, continuous delta rebalancing without transaction costs or bid-ask friction.",
        "Bayesian evidence assumes conditionally independent Bernoulli observation trials within a stationary environment.",
        "Binomial lattice prices are subject to discretization oscillation that converges as steps approach infinity.",
    ]

    executive_summary = (
        f"Research analysis for {request.asset} at spot ${request.spot:.2f} over a {request.maturity:.2f}-year horizon. "
        f"Bayesian inference revised regime belief from {prior_mean:.1%} to {post_mean:.1%}. "
        f"Stochastic forecasting projects physical terminal price distribution centered at ${sim_physical['terminal_mean']:.2f} (std ${sim_physical['terminal_std']:.2f}). "
        f"Risk-neutral derivatives valuation yields a benchmark {request.kind} price of ${bsm_target['price']:.4f} via Black–Scholes–Merton, "
        f"with CRR American valuation at ${tree_american['price']:.4f} (early exercise premium: ${early_exercise_premium:.4f})."
    )

    return {
        "setup": {
            "asset": request.asset,
            "spot": request.spot,
            "strike": request.strike,
            "maturity": request.maturity,
            "rate": request.rate,
            "volatility": request.volatility,
            "drift": request.drift,
            "dividend_yield": request.dividend_yield,
            "kind": request.kind,
        },
        "bayesian": {
            "prior": bayesian["prior"],
            "posterior": bayesian["posterior"],
            "successes": succ,
            "failures": fail,
            "log_marginal_likelihood": bayesian["log_marginal_likelihood"],
            "density": bayesian["density"],
            "sequence": bayesian["sequence"],
            "shift_summary": shift_summary,
        },
        "stochastic": {
            "physical": {
                "time": sim_physical["time"],
                "paths": sim_physical["paths"],
                "terminal_mean": sim_physical["terminal_mean"],
                "terminal_median": sim_physical.get("terminal_median", sim_physical["terminal_mean"]),
                "terminal_std": sim_physical["terminal_std"],
                "theory_mean": theory_mean_p,
                "theory_std": theory_std_p,
                "drift_type": "Physical Drift μ (Real-World Forecast)",
                "drift_value": request.drift,
            },
            "risk_neutral": {
                "time": sim_risk_neutral["time"],
                "paths": sim_risk_neutral["paths"],
                "terminal_mean": sim_risk_neutral["terminal_mean"],
                "terminal_median": sim_risk_neutral.get("terminal_median", sim_risk_neutral["terminal_mean"]),
                "terminal_std": sim_risk_neutral["terminal_std"],
                "theory_mean": theory_mean_q,
                "theory_std": theory_std_q,
                "drift_type": "Risk-Neutral Drift r - q (Martingale Pricing Measure)",
                "drift_value": risk_neutral_drift,
            },
            "measure_distinction": "Physical measure P reflects estimated real-world returns for forecasting; Risk-neutral measure Q adjusts drift to the risk-free rate r-q for arbitrage-free replication and option valuation.",
        },
        "valuation": {
            "kind": request.kind,
            "black_scholes": bsm_target,
            "binomial_european": tree_european,
            "binomial_american": tree_american,
            "early_exercise_premium": early_exercise_premium,
            "monte_carlo": mc_estimate,
            "put_call_parity": {
                "call_price": bsm_call["price"],
                "put_price": bsm_put["price"],
                "parity_difference": parity_diff,
                "holds": parity_diff < 1e-4,
                "formula": "C - P = S0 * exp(-q*T) - K * exp(-r*T)",
            },
            "models_comparison": models,
            "root_hedge": {
                "delta_shares": tree_european["hedge_shares"],
                "cash_borrowing": tree_european["hedge_cash"],
                "explanation": f"To replicate the option at t=0, hold {tree_european['hedge_shares']:.4f} shares of {request.asset} and finance with ${tree_european['hedge_cash']:.4f} in cash.",
            },
        },
        "sensitivities": sensitivities,
        "conclusion": {
            "executive_summary": executive_summary,
            "uncertainty_drivers": uncertainty_drivers,
            "model_limitations": model_limitations,
            "disclaimer": "AMQUANT Quantitative Finance Research Terminal · Generated for research and educational purposes. Not an investment recommendation, trading strategy, or guaranteed forecast.",
        },
    }


@router.post("/analyze")
async def run_research_intelligence(request: IntelligenceRequest) -> dict[str, object]:
    if any(obs not in (0, 1) for obs in request.observations):
        raise HTTPException(status_code=422, detail="Observations must contain only binary outcomes (0 or 1)")

    try:
        return await execute_guarded_calculation(_compute_intelligence, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


