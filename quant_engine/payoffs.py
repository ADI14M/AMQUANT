"""Expiration payoff helpers."""


def call_payoff(spot: float, strike: float, premium: float = 0.0) -> float:
    """Long call profit at expiry, net of the stated premium."""
    return max(spot - strike, 0.0) - premium


def put_payoff(spot: float, strike: float, premium: float = 0.0) -> float:
    """Long put profit at expiry, net of the stated premium."""
    return max(strike - spot, 0.0) - premium
