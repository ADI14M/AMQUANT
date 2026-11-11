"""Beta–Bernoulli conjugate inference for binary event probabilities."""
from math import lgamma, log

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_distribution
from scipy.special import gammaln


def _validate_prior(alpha: float, beta: float) -> None:
    if alpha <= 0 or beta <= 0:
        raise ValueError("Beta prior alpha and beta must be positive")


def beta_density(grid: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    _validate_prior(alpha, beta)
    log_norm = gammaln(alpha + beta) - gammaln(alpha) - gammaln(beta)
    return np.exp(log_norm + (alpha - 1) * np.log(grid) + (beta - 1) * np.log1p(-grid))


def beta_bernoulli_update(alpha: float, beta: float, observations: list[int]) -> dict[str, object]:
    """Return posterior parameters, marginal likelihood, predictive probability, and sequential history."""
    _validate_prior(alpha, beta)
    if any(value not in (0, 1) for value in observations):
        raise ValueError("observations must contain only 0 or 1")
    current_a, current_b = float(alpha), float(beta)
    prior_a, prior_b = current_a, current_b
    log_marginal = 0.0
    history = [{"observation": "prior", "successes": 0, "failures": 0, "alpha": current_a, "beta": current_b, "mean": current_a / (current_a + current_b)}]
    successes = failures = 0
    for observation in observations:
        predictive = current_a / (current_a + current_b) if observation else current_b / (current_a + current_b)
        log_marginal += log(predictive)
        if observation:
            successes += 1
            current_a += 1
        else:
            failures += 1
            current_b += 1
        history.append({"observation": observation, "successes": successes, "failures": failures, "alpha": current_a, "beta": current_b, "mean": current_a / (current_a + current_b)})
    # Closed form check/definition: B(a+s,b+f)/B(a,b); stable via log gamma.
    log_marginal = (lgamma(prior_a + successes) + lgamma(prior_b + failures) - lgamma(prior_a + prior_b + len(observations))) - (lgamma(prior_a) + lgamma(prior_b) - lgamma(prior_a + prior_b))
    table = pd.DataFrame(history)
    grid = np.linspace(0.001, 0.999, 101)
    density = beta_density(grid, current_a, current_b)
    likelihood = grid**successes * (1-grid)**failures
    likelihood /= max(float(likelihood.max()), 1e-300)
    credible_interval = beta_distribution.ppf([0.025, 0.975], current_a, current_b)
    return {"prior": {"alpha": prior_a, "beta": prior_b, "mean": prior_a / (prior_a + prior_b)}, "posterior": {"alpha": current_a, "beta": current_b, "mean": current_a / (current_a + current_b), "variance": current_a * current_b / ((current_a + current_b)**2 * (current_a + current_b + 1)), "predictive_success_probability": current_a / (current_a + current_b), "credible_interval_95": [float(credible_interval[0]), float(credible_interval[1])]}, "successes": successes, "failures": failures, "log_marginal_likelihood": log_marginal, "density": [{"probability": float(x), "prior_density": float(y), "likelihood_relative": float(l), "posterior_density": float(z)} for x, y, l, z in zip(grid, beta_density(grid, prior_a, prior_b), likelihood, density)], "sequence": table.to_dict(orient="records")}
