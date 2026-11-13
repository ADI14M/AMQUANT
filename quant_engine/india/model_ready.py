"""Model-Ready Data Interfaces for the 6 Quantitative Research Modules.

Bridges raw and cleaned Indian market data directly into the mathematical models:
- Week 1: CRR, risk-neutral pricing, replicating hedging portfolios
- Week 2: Information-flow modelling & liquidity impact
- Week 3: Bayesian inference & sequential posterior updates
- Week 4: Itô processes & Ornstein-Uhlenbeck SDE calibration
- Week 5: Correlated Geometric Brownian Motion (GBM) Monte Carlo
- Week 6: Information-driven modelling & noisy signal assimilation
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from quant_engine.india.providers.macro import get_current_macro_snapshot


def get_crr_model_inputs(df: pd.DataFrame, spot_override: float | None = None) -> dict[str, Any]:
    """Week 1: Prepare exact inputs for Cox-Ross-Rubinstein binomial lattice."""
    if df.empty:
        raise ValueError("Cannot prepare model inputs from empty DataFrame.")

    spot = float(spot_override or df["close"].iloc[-1])
    # 20-day annualized realized volatility
    if "rolling_vol_20d" in df.columns and not np.isnan(df["rolling_vol_20d"].iloc[-1]):
        sigma = float(df["rolling_vol_20d"].iloc[-1])
    else:
        log_rets = np.log(df["close"] / df["close"].shift(1)).dropna()
        sigma = float(log_rets.std() * np.sqrt(252)) if len(log_rets) > 5 else 0.20

    sigma = max(0.05, min(1.5, sigma))  # bounded

    macro = get_current_macro_snapshot()
    risk_free_rate = macro.t_bill_91d_yield / 100.0  # e.g., 0.0665

    # Standard ATM strike and range
    strike = round(spot / 50.0) * 50.0  # rounded to nearest 50 (typical Indian strike step)
    if strike <= 0:
        strike = round(spot, 2)

    return {
        "spot": round(spot, 2),
        "strike": strike,
        "maturity_years": 0.25,  # 3-month quarterly standard
        "risk_free_rate": round(risk_free_rate, 4),
        "volatility": round(sigma, 4),
        "dividend_yield": 0.012,  # Typical NIFTY 50 dividend yield ~1.2%
        "steps": 50,
        "strike_step": 50.0 if spot > 1000 else 10.0,
    }


def get_information_flow_inputs(df: pd.DataFrame) -> dict[str, Any]:
    """Week 2: Prepare order flow imbalance and Kyle's lambda price impact proxies."""
    if df.empty or len(df) < 10:
        return {"kyle_lambda": 0.001, "avg_daily_turnover_cr": 100.0, "volume_clock_ticks": []}

    feat = df.copy()
    feat["ret"] = feat["close"].pct_change().fillna(0.0)
    feat["turnover_cr"] = (feat["close"] * feat["volume"]) / 1e7

    # Kyle's lambda proxy: covariance(return, sign(return) * turnover) / variance(order flow)
    order_flow = np.sign(feat["ret"]) * feat["turnover_cr"]
    cov_ret_flow = np.cov(feat["ret"].iloc[-60:], order_flow.iloc[-60:])[0, 1] if len(feat) >= 60 else 0.001
    var_flow = np.var(order_flow.iloc[-60:]) if len(feat) >= 60 else 1.0

    kyle_lambda = abs(cov_ret_flow / max(1e-4, var_flow))

    return {
        "kyle_lambda": round(float(kyle_lambda), 6),
        "avg_daily_turnover_cr": round(float(feat["turnover_cr"].tail(20).mean()), 2),
        "volume_volatility": round(float(feat["volume"].tail(20).std() / max(1.0, feat["volume"].tail(20).mean())), 4),
    }


def get_bayesian_regime_inputs(df: pd.DataFrame) -> dict[str, Any]:
    """Week 3: Prepare observation sequences and priors for Bayesian regime updating."""
    if df.empty or len(df) < 20:
        return {"trials": 20, "successes": 11, "prior_alpha": 2.0, "prior_beta": 2.0}

    # Binary trials: 1 if daily return > 0, else 0
    rets = df["close"].pct_change().dropna().tail(60)
    successes = int((rets > 0).sum())
    trials = len(rets)

    return {
        "trials": trials,
        "successes": successes,
        "empirical_win_rate": round(successes / max(1, trials), 4),
        "prior_alpha": 2.0,
        "prior_beta": 2.0,
        "posterior_alpha": 2.0 + successes,
        "posterior_beta": 2.0 + (trials - successes),
    }


def get_ito_sde_calibration(df: pd.DataFrame) -> dict[str, Any]:
    """Week 4: Calibrate drift mu, diffusion sigma, and Ornstein-Uhlenbeck parameters."""
    if df.empty or len(df) < 30:
        return {"drift_mu": 0.12, "diffusion_sigma": 0.18, "ou_speed_theta": 1.5, "ou_mean_mu": 14.0}

    log_rets = np.log(df["close"] / df["close"].shift(1)).dropna()
    dt = 1.0 / 252.0

    # Annualized drift mu and diffusion sigma
    sigma = float(log_rets.std() / np.sqrt(dt))
    mu = float(log_rets.mean() / dt + 0.5 * sigma**2)

    # Fit AR(1) proxy for Ornstein-Uhlenbeck: X_t = a + b * X_{t-1} + e
    x = df["close"].tail(100).values
    x_prev = x[:-1]
    x_curr = x[1:]
    slope, intercept = np.polyfit(x_prev, x_curr, 1)

    # b = 1 - theta * dt  =>  theta = (1 - b) / dt
    theta = max(0.01, (1.0 - slope) / dt) if slope < 1.0 else 0.5
    # long-term mean: mu_ou = a / (1 - b)
    ou_mean = float(intercept / (1.0 - slope)) if abs(1.0 - slope) > 1e-4 else float(np.mean(x))

    return {
        "drift_mu": round(mu, 4),
        "diffusion_sigma": round(sigma, 4),
        "ou_speed_theta": round(theta, 3),
        "ou_mean_mu": round(ou_mean, 2),
    }


def get_correlated_gbm_parameters(multi_asset_returns: pd.DataFrame) -> dict[str, Any]:
    """Week 5: Cholesky decomposition of empirical covariance for multi-asset Indian simulation."""
    if multi_asset_returns.empty or multi_asset_returns.shape[1] < 2:
        return {"symbols": [], "cholesky_matrix": []}

    cov = multi_asset_returns.cov() * 252
    # Ensure positive semi-definite
    cov_arr = cov.values
    # Add tiny regularizer on diagonal
    cov_reg = cov_arr + np.eye(len(cov_arr)) * 1e-6
    try:
        chol = np.linalg.cholesky(cov_reg)
        return {
            "symbols": list(multi_asset_returns.columns),
            "cholesky_matrix": chol.round(4).tolist(),
        }
    except Exception:
        return {"symbols": list(multi_asset_returns.columns), "cholesky_matrix": []}

