"""Option payoffs, Cox–Ross–Rubinstein pricing, and dynamic replication."""
from math import exp, sqrt
from typing import Literal

from .options import _validate

OptionKind = Literal["call", "put"]
ExerciseStyle = Literal["european", "american"]


def option_payoff(spot: float, strike: float, kind: OptionKind) -> float:
    if strike <= 0 or spot < 0:
        raise ValueError("spot must be non-negative and strike must be positive")
    if kind == "call":
        return max(spot - strike, 0.0)
    if kind == "put":
        return max(strike - spot, 0.0)
    raise ValueError("kind must be 'call' or 'put'")


def option_profit(spot: float, strike: float, premium: float, kind: OptionKind, position: Literal["long", "short"] = "long") -> float:
    if premium < 0:
        raise ValueError("premium cannot be negative")
    sign = 1.0 if position == "long" else -1.0 if position == "short" else None
    if sign is None:
        raise ValueError("position must be 'long' or 'short'")
    return sign * (option_payoff(spot, strike, kind) - premium)


def crr_binomial(spot: float, strike: float, maturity: float, rate: float, volatility: float, steps: int, kind: OptionKind = "call", exercise: ExerciseStyle = "european", dividend_yield: float = 0.0, include_hedge_tree: bool = False) -> dict[str, object]:
    """CRR price and (optionally) node-by-node delta/cash replication schedule."""
    _validate(spot, strike, maturity, volatility)
    if steps < 1 or steps > 500:
        raise ValueError("steps must be between 1 and 500")
    if kind not in {"call", "put"} or exercise not in {"european", "american"}:
        raise ValueError("invalid option kind or exercise style")
    if maturity == 0:
        intrinsic = option_payoff(spot, strike, kind)
        result = {"price": intrinsic, "delta": 1.0 if kind == "call" and spot > strike else -1.0 if kind == "put" and spot < strike else 0.0, "hedge_shares": 0.0, "hedge_cash": intrinsic, "up_factor": 1.0, "down_factor": 1.0, "risk_neutral_probability": 0.0, "steps": steps, "exercise": exercise, "kind": kind}
        if include_hedge_tree:
            result["hedge_schedule"] = []
        return result
    dt = maturity / steps
    if volatility == 0:
        exercise_times = [maturity] if exercise == "european" else [index * dt for index in range(steps + 1)]
        candidates = []
        for time in exercise_times:
            forward_spot = spot * exp((rate - dividend_yield) * time)
            value = exp(-rate * time) * option_payoff(forward_spot, strike, kind)
            candidates.append((value, time, forward_spot))
        price, optimal_time, forward_spot = max(candidates, key=lambda candidate: candidate[0])
        is_itm = forward_spot > strike if kind == "call" else forward_spot < strike
        delta = (exp(-dividend_yield * optimal_time) if kind == "call" else -exp(-dividend_yield * optimal_time)) if is_itm else 0.0
        result = {"price": price, "delta": delta, "hedge_shares": delta, "hedge_cash": price - delta * spot, "up_factor": 1.0, "down_factor": 1.0, "risk_neutral_probability": 0.0, "steps": steps, "exercise": exercise, "kind": kind}
        if include_hedge_tree:
            result["hedge_schedule"] = []
        return result
    u = exp(volatility * sqrt(dt))
    d = 1.0 / u
    growth = exp((rate - dividend_yield) * dt)
    probability = (growth - d) / (u - d)
    if not 0 <= probability <= 1:
        raise ValueError("CRR parameters imply an arbitrage risk-neutral probability; increase steps or review inputs")
    discount = exp(-rate * dt)
    levels: list[list[float] | None] = [None] * (steps + 1)
    early_exercise: list[list[bool] | None] = [None] * steps
    levels[steps] = [option_payoff(spot * u**j * d**(steps-j), strike, kind) for j in range(steps + 1)]
    for level in range(steps - 1, -1, -1):
        next_values = levels[level + 1]
        assert next_values is not None
        current_values = []
        current_exercise = []
        for j in range(level + 1):
            continuation = discount * (probability * next_values[j + 1] + (1 - probability) * next_values[j])
            node_spot = spot * u**j * d**(level-j)
            intrinsic = option_payoff(node_spot, strike, kind)
            exercise_now = exercise == "american" and intrinsic > continuation
            current_values.append(max(continuation, intrinsic) if exercise == "american" else continuation)
            current_exercise.append(exercise_now)
        levels[level] = current_values
        early_exercise[level] = current_exercise
    root = levels[0]
    first_step = levels[1]
    assert root is not None and first_step is not None
    down_value, up_value = first_step[0], first_step[1]
    root_exercise = early_exercise[0]
    assert root_exercise is not None
    if root_exercise[0]:
        delta = 1.0 if kind == "call" and spot > strike else -1.0 if kind == "put" and spot < strike else 0.0
        bond_cash = root[0] - delta * spot
    else:
        delta = (up_value - down_value) / (spot * (u - d))
        bond_cash = discount * (u * down_value - d * up_value) / (u - d)
    result = {"price": root[0], "delta": delta, "hedge_shares": delta, "hedge_cash": bond_cash, "up_factor": u, "down_factor": d, "risk_neutral_probability": probability, "steps": steps, "exercise": exercise, "kind": kind}
    if include_hedge_tree:
        schedule = []
        for level in range(steps):
            next_values = levels[level + 1]
            node_values = levels[level]
            exercise_nodes = early_exercise[level]
            assert next_values is not None and node_values is not None and exercise_nodes is not None
            time = level * dt
            for j in range(level + 1):
                node_spot = spot * u**j * d**(level-j)
                down_node_value, up_node_value = next_values[j], next_values[j + 1]
                if exercise_nodes[j]:
                    node_delta = 1.0 if kind == "call" and node_spot > strike else -1.0 if kind == "put" and node_spot < strike else 0.0
                    node_cash = node_values[j] - node_delta * node_spot
                else:
                    node_delta = (up_node_value - down_node_value) / (node_spot * (u - d))
                    node_cash = discount * (u * down_node_value - d * up_node_value) / (u - d)
                schedule.append({"level": level, "node": j, "time": time, "spot": node_spot, "option_value": node_values[j], "delta": node_delta, "cash": node_cash, "exercise_now": exercise_nodes[j]})
        result["hedge_schedule"] = schedule
    return result
