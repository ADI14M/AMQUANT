"""Black–Scholes–Merton European option prices and analytical Greeks."""
from math import erf, exp, log, pi, sqrt


def _validate(spot: float, strike: float, maturity: float, volatility: float) -> None:
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if maturity < 0:
        raise ValueError("maturity cannot be negative")
    if volatility < 0:
        raise ValueError("volatility cannot be negative")


def _cdf(value: float) -> float:
    return 0.5 * (1 + erf(value / sqrt(2)))


def _pdf(value: float) -> float:
    return exp(-0.5 * value * value) / sqrt(2 * pi)


def black_scholes(spot: float, strike: float, maturity: float, rate: float, volatility: float, kind: str = "call", dividend_yield: float = 0.0) -> float:
    """European BSM price with continuously compounded annual rate and dividend yield."""
    _validate(spot, strike, maturity, volatility)
    if kind not in {"call", "put"}:
        raise ValueError("kind must be 'call' or 'put'")
    discounted_spot = spot * exp(-dividend_yield * maturity)
    discounted_strike = strike * exp(-rate * maturity)
    if maturity == 0 or volatility == 0:
        return max(discounted_spot - discounted_strike, 0.0) if kind == "call" else max(discounted_strike - discounted_spot, 0.0)
    root_t = sqrt(maturity)
    d1 = (log(spot / strike) + (rate - dividend_yield + volatility**2 / 2) * maturity) / (volatility * root_t)
    d2 = d1 - volatility * root_t
    if kind == "call":
        return discounted_spot * _cdf(d1) - discounted_strike * _cdf(d2)
    return discounted_strike * _cdf(-d2) - discounted_spot * _cdf(-d1)


def black_scholes_greeks(spot: float, strike: float, maturity: float, rate: float, volatility: float, kind: str = "call", dividend_yield: float = 0.0) -> dict[str, float]:
    """Analytical Greeks: vega/rho per 1.00 input change and theta per year."""
    price = black_scholes(spot, strike, maturity, rate, volatility, kind, dividend_yield)
    if maturity == 0:
        discount = exp(-dividend_yield * maturity)
        delta = (discount if spot * discount > strike * exp(-rate * maturity) else 0.0) if kind == "call" else (-discount if spot * discount < strike * exp(-rate * maturity) else 0.0)
        return {"price": price, "delta": delta, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
    if volatility == 0:
        discounted_spot = spot * exp(-dividend_yield * maturity)
        discounted_strike = strike * exp(-rate * maturity)
        if kind == "call":
            in_the_money = discounted_spot > discounted_strike
            delta = exp(-dividend_yield * maturity) if in_the_money else 0.0
            theta = dividend_yield * discounted_spot - rate * discounted_strike if in_the_money else 0.0
            rho = maturity * discounted_strike if in_the_money else 0.0
        elif kind == "put":
            in_the_money = discounted_spot < discounted_strike
            delta = -exp(-dividend_yield * maturity) if in_the_money else 0.0
            theta = rate * discounted_strike - dividend_yield * discounted_spot if in_the_money else 0.0
            rho = -maturity * discounted_strike if in_the_money else 0.0
        else:
            raise ValueError("kind must be 'call' or 'put'")
        # Degenerate zero-volatility gamma/vega are reported as zero by convention.
        return {"price": price, "delta": delta, "gamma": 0.0, "vega": 0.0, "theta": theta, "rho": rho}
    root_t = sqrt(maturity)
    d1 = (log(spot / strike) + (rate - dividend_yield + volatility**2 / 2) * maturity) / (volatility * root_t)
    d2 = d1 - volatility * root_t
    pdf = _pdf(d1)
    carry_spot = exp(-dividend_yield * maturity)
    discount_strike = exp(-rate * maturity)
    if kind == "call":
        delta = carry_spot * _cdf(d1)
        theta = -(spot * carry_spot * pdf * volatility) / (2 * root_t) - rate * strike * discount_strike * _cdf(d2) + dividend_yield * spot * carry_spot * _cdf(d1)
        rho = strike * maturity * discount_strike * _cdf(d2)
    elif kind == "put":
        delta = carry_spot * (_cdf(d1) - 1)
        theta = -(spot * carry_spot * pdf * volatility) / (2 * root_t) + rate * strike * discount_strike * _cdf(-d2) - dividend_yield * spot * carry_spot * _cdf(-d1)
        rho = -strike * maturity * discount_strike * _cdf(-d2)
    else:
        raise ValueError("kind must be 'call' or 'put'")
    gamma = carry_spot * pdf / (spot * volatility * root_t)
    vega = spot * carry_spot * pdf * root_t
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def option_sensitivities(spot: float, strike: float, maturity: float, rate: float, volatility: float, kind: str = "call", dividend_yield: float = 0.0, points: int = 21) -> dict[str, list[dict[str, float]]]:
    """One-factor spot and volatility sweeps around the supplied base assumptions."""
    if points < 3 or points > 101:
        raise ValueError("points must be between 3 and 101")
    spot_values = [spot * (0.7 + 0.6 * i / (points - 1)) for i in range(points)]
    vol_scale = volatility if volatility > 0 else 0.2
    vol_values = [max(0.001, vol_scale * (0.4 + 1.2 * i / (points - 1))) for i in range(points)]
    return {
        "spot": [{"input": s, "price": black_scholes(s, strike, maturity, rate, volatility, kind, dividend_yield)} for s in spot_values],
        "volatility": [{"input": v, "price": black_scholes(spot, strike, maturity, rate, v, kind, dividend_yield)} for v in vol_values],
    }
