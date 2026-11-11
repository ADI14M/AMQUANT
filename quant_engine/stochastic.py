"""Seedable Brownian and geometric Brownian motion with Monte Carlo estimates."""
import numpy as np
from scipy.stats import norm


def simulate_process(process: str, spot: float | None, drift: float, volatility: float, maturity: float, steps: int, paths: int, seed: int = 7, strike: float | None = None, rate: float = 0.0, mc_paths: int = 10000, kind: str = "call") -> dict[str, object]:
    if process not in {"brownian", "gbm"}:
        raise ValueError("process must be 'brownian' or 'gbm'")
    if (process == "gbm" and (spot is None or spot <= 0)) or volatility < 0 or maturity <= 0 or steps < 1 or paths < 1 or mc_paths < 100:
        raise ValueError("GBM spot and maturity must be positive; volatility non-negative; steps and paths positive; mc_paths at least 100")
    if steps > 252 or paths > 40 or mc_paths > 100000:
        raise ValueError("maximums are 252 steps, 40 displayed paths, and 100000 Monte Carlo paths")
    if strike is not None and strike <= 0:
        raise ValueError("strike must be positive")
    if kind not in {"call", "put"}:
        raise ValueError("kind must be 'call' or 'put'")
    rng = np.random.default_rng(seed)
    dt = maturity / steps
    display_z = rng.standard_normal((paths, steps))
    if process == "brownian":
        display_paths = np.column_stack([np.zeros(paths), np.cumsum(drift * dt + volatility * np.sqrt(dt) * display_z, axis=1)])
        mc_z = rng.standard_normal(mc_paths)
        terminal = drift * maturity + volatility * np.sqrt(maturity) * mc_z
        label = "X(T)"
        call_estimate = None
    else:
        assert spot is not None
        increments = (drift - 0.5 * volatility**2) * dt + volatility * np.sqrt(dt) * display_z
        display_paths = spot * np.exp(np.column_stack([np.zeros(paths), np.cumsum(increments, axis=1)]))
        mc_z = rng.standard_normal(mc_paths)
        terminal = spot * np.exp((drift - 0.5 * volatility**2) * maturity + volatility * np.sqrt(maturity) * mc_z)
        label = "S(T)"
        call_estimate = None
        if strike is not None:
            payoff = np.maximum(terminal - strike, 0) if kind == "call" else np.maximum(strike - terminal, 0)
            discounted_payoffs = np.exp(-rate * maturity) * payoff
            call_estimate = {
                "price": float(discounted_payoffs.mean()),
                "standard_error": float(discounted_payoffs.std(ddof=1) / np.sqrt(mc_paths)),
                "confidence_interval_95": [
                    float(discounted_payoffs.mean() - norm.ppf(0.975) * discounted_payoffs.std(ddof=1) / np.sqrt(mc_paths)),
                    float(discounted_payoffs.mean() + norm.ppf(0.975) * discounted_payoffs.std(ddof=1) / np.sqrt(mc_paths)),
                ],
                "paths": mc_paths,
                "kind": kind,
            }
    time_grid = np.linspace(0.0, maturity, steps + 1)
    path_data = [{"time": float(t), **{f"path_{i+1}": float(display_paths[i, j]) for i in range(paths)}} for j, t in enumerate(time_grid)]
    return {
        "process": process,
        "time": time_grid.tolist(),
        "paths": path_data,
        "path_count": paths,
        "steps": steps,
        "seed": seed,
        "terminal_mean": float(terminal.mean()),
        "terminal_std": float(terminal.std(ddof=1)),
        "terminal_median": float(np.median(terminal)),
        "terminal_label": label,
        "mc_call_estimate": call_estimate,
        "synthetic": True,
    }
