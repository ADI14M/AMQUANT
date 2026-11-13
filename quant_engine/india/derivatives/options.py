"""AMQUANT INDIA - Historical Options Data Infrastructure, Option Chains & Model Greeks.

Features:
1. Historical options data representation (Underlying, Expiry, Strike, CE/PE, OHLC, Volume, Open Interest, Lot Size).
2. Option Chain Model:
   - Bidirectional strike matrix (Calls left, Puts right).
   - ATM strike identification from underlying spot.
   - Put-Call Ratio (PCR-OI, PCR-Volume).
   - Max Pain strike calculation.
3. Analytical Model Greeks & Implied Volatility (IV):
   - Leverages quant_engine.options (Black-Scholes analytical formulation).
   - Implied Volatility calculation via root inversion against market price.
   - Delta, Gamma, Theta, Vega, Rho.
   - Clear disclosure: All Greeks & IV carry is_model_estimate = True using Indian 6.5% risk-free rate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from math import exp, log, sqrt
from typing import Any, Literal
import numpy as np
import pandas as pd

from quant_engine.options import black_scholes, black_scholes_greeks

OptionType = Literal["CE", "PE"]


@dataclass
class OptionQuote:
    strike: float
    option_type: OptionType
    last_price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int
    lot_size: int
    iv: float  # Implied Volatility (annualized %)
    delta: float
    gamma: float
    theta: float
    vega: float
    is_model_estimate: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OptionChainRow:
    strike: float
    call: OptionQuote | None
    put: OptionQuote | None
    is_atm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "strike": self.strike,
            "call": self.call.to_dict() if self.call else None,
            "put": self.put.to_dict() if self.put else None,
            "is_atm": self.is_atm,
        }


@dataclass
class OptionChain:
    underlying: str
    underlying_price: float
    as_of_date: str
    expiry_date: str
    days_to_expiry: int
    pcr_oi: float
    pcr_volume: float
    max_pain_strike: float
    total_call_oi: int
    total_put_oi: int
    total_call_volume: int
    total_put_volume: int
    strikes: list[OptionChainRow]
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["strikes"] = [s.to_dict() if isinstance(s, OptionChainRow) else s for s in self.strikes]
        return res


def calculate_implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    maturity_years: float,
    rate: float = 0.065,  # 6.5% Indian 91-day T-Bill rate
    kind: str = "call",
    tol: float = 1e-4,
    max_iter: int = 50,
) -> float:
    """Calculate implied volatility using bisection root-finding over Black-Scholes formula.

    Returns:
        Annualized volatility (e.g., 0.18 for 18%).
    """
    if maturity_years <= 0 or market_price <= 0 or spot <= 0 or strike <= 0:
        return 0.0

    # Intrinsic value lower bound check
    intrinsic = max(0.0, spot - strike) if kind == "call" else max(0.0, strike - spot)
    if market_price < intrinsic:
        return 0.0

    low_vol = 0.01
    high_vol = 4.0

    for _ in range(max_iter):
        mid_vol = (low_vol + high_vol) / 2.0
        p = black_scholes(spot, strike, maturity_years, rate, mid_vol, kind=kind)
        diff = p - market_price

        if abs(diff) < tol:
            return round(mid_vol, 4)

        if diff > 0:
            high_vol = mid_vol
        else:
            low_vol = mid_vol

    return round((low_vol + high_vol) / 2.0, 4)


def compute_option_greeks_for_quote(
    market_price: float,
    spot: float,
    strike: float,
    maturity_years: float,
    kind: str,
    rate: float = 0.065,
) -> tuple[float, float, float, float, float]:
    """Compute (iv, delta, gamma, theta, vega) for an option quote.

    Returns:
        iv, delta, gamma, theta_per_day, vega_per_1pct
    """
    if maturity_years <= 0 or market_price <= 0 or spot <= 0:
        delta = 1.0 if (kind == "call" and spot > strike) else (0.0 if kind == "call" else (-1.0 if spot < strike else 0.0))
        return 0.0, delta, 0.0, 0.0, 0.0

    iv = calculate_implied_volatility(market_price, spot, strike, maturity_years, rate, kind)
    if iv <= 0:
        iv = 0.15  # Fallback default proxy for deep OTM/ITM

    g = black_scholes_greeks(spot, strike, maturity_years, rate, iv, kind=kind)
    delta = round(g.get("delta", 0.0), 3)
    gamma = round(g.get("gamma", 0.0), 5)
    theta_daily = round(g.get("theta", 0.0) / 365.0, 2)  # Theta per calendar day
    vega_1pct = round(g.get("vega", 0.0) / 100.0, 2)  # Vega per 1% vol change

    return round(iv * 100.0, 2), delta, gamma, theta_daily, vega_1pct


def calculate_max_pain(strikes_data: list[tuple[float, int, int]]) -> float:
    """Calculate the Max Pain strike price (strike with minimum total loss for option writers).

    Args:
        strikes_data: list of (strike, call_oi, put_oi)
    """
    if not strikes_data:
        return 0.0

    strikes = [s[0] for s in strikes_data]
    min_loss = float("inf")
    best_strike = strikes[0]

    for test_strike in strikes:
        total_loss = 0.0
        for s, c_oi, p_oi in strikes_data:
            # Call loss: if test_strike > s, call buyer gains (test_strike - s) * c_oi
            if test_strike > s:
                total_loss += (test_strike - s) * c_oi
            # Put loss: if test_strike < s, put buyer gains (s - test_strike) * p_oi
            if test_strike < s:
                total_loss += (s - test_strike) * p_oi

        if total_loss < min_loss:
            min_loss = total_loss
            best_strike = test_strike

    return best_strike


class OptionChainBuilder:
    """Builds structured option chains with model Greeks, IV, PCR, and Max Pain."""

    DISCLAIMER = (
        "Greeks and Implied Volatility are analytical Black-Scholes model estimates (is_model_estimate=True) "
        "computed using the 6.5% Indian 91-day T-Bill risk-free rate. Actual exchange traded quotes reflect "
        "market bid/ask dynamics."
    )

    def build_chain(
        self,
        underlying: str,
        underlying_price: float,
        expiry_date: str,
        quotes_data: list[dict[str, Any]],  # raw records with strike, option_type, price/close, volume, oi, lot_size
        as_of_date: str | None = None,
        risk_free_rate: float = 0.065,
    ) -> OptionChain:
        """Construct a full OptionChain object from raw contract observations."""
        today_str = as_of_date or datetime.now().strftime("%Y-%m-%d")
        dt_today = datetime.strptime(today_str[:10], "%Y-%m-%d")
        dt_exp = datetime.strptime(expiry_date[:10], "%Y-%m-%d")

        days_to_exp = max(0, (dt_exp - dt_today).days)
        maturity_years = max(1 / 365.0, days_to_exp / 365.0)

        # Aggregate quotes by strike
        grouped_by_strike: dict[float, dict[str, dict[str, Any]]] = {}
        for q in quotes_data:
            k = float(q["strike"])
            t = str(q.get("option_type", "CE")).upper()
            if k not in grouped_by_strike:
                grouped_by_strike[k] = {}
            grouped_by_strike[k][t] = q

        sorted_strikes = sorted(grouped_by_strike.keys())

        # Determine ATM strike (closest to spot)
        atm_strike = min(sorted_strikes, key=lambda x: abs(x - underlying_price)) if sorted_strikes else 0.0

        chain_rows: list[OptionChainRow] = []
        tot_call_oi = 0
        tot_put_oi = 0
        tot_call_vol = 0
        tot_put_vol = 0
        pain_data: list[tuple[float, int, int]] = []

        for k in sorted_strikes:
            pair = grouped_by_strike[k]
            call_raw = pair.get("CE")
            put_raw = pair.get("PE")

            call_quote: OptionQuote | None = None
            if call_raw:
                p = float(call_raw.get("last_price") or call_raw.get("close") or 0.0)
                vol = int(call_raw.get("volume", 0))
                oi = int(call_raw.get("open_interest", 0))
                ls = int(call_raw.get("lot_size", 25))
                tot_call_oi += oi
                tot_call_vol += vol

                iv, delta, gamma, theta, vega = compute_option_greeks_for_quote(
                    p, underlying_price, k, maturity_years, "call", risk_free_rate
                )
                call_quote = OptionQuote(
                    strike=k,
                    option_type="CE",
                    last_price=round(p, 2),
                    open=float(call_raw.get("open", p)),
                    high=float(call_raw.get("high", p)),
                    low=float(call_raw.get("low", p)),
                    close=round(p, 2),
                    volume=vol,
                    open_interest=oi,
                    lot_size=ls,
                    iv=iv,
                    delta=delta,
                    gamma=gamma,
                    theta=theta,
                    vega=vega,
                    is_model_estimate=True,
                )

            put_quote: OptionQuote | None = None
            if put_raw:
                p = float(put_raw.get("last_price") or put_raw.get("close") or 0.0)
                vol = int(put_raw.get("volume", 0))
                oi = int(put_raw.get("open_interest", 0))
                ls = int(put_raw.get("lot_size", 25))
                tot_put_oi += oi
                tot_put_vol += vol

                iv, delta, gamma, theta, vega = compute_option_greeks_for_quote(
                    p, underlying_price, k, maturity_years, "put", risk_free_rate
                )
                put_quote = OptionQuote(
                    strike=k,
                    option_type="PE",
                    last_price=round(p, 2),
                    open=float(put_raw.get("open", p)),
                    high=float(put_raw.get("high", p)),
                    low=float(put_raw.get("low", p)),
                    close=round(p, 2),
                    volume=vol,
                    open_interest=oi,
                    lot_size=ls,
                    iv=iv,
                    delta=delta,
                    gamma=gamma,
                    theta=theta,
                    vega=vega,
                    is_model_estimate=True,
                )

            c_oi_val = call_quote.open_interest if call_quote else 0
            p_oi_val = put_quote.open_interest if put_quote else 0
            pain_data.append((k, c_oi_val, p_oi_val))

            chain_rows.append(
                OptionChainRow(
                    strike=k,
                    call=call_quote,
                    put=put_quote,
                    is_atm=k == atm_strike,
                )
            )

        pcr_oi = round(tot_put_oi / max(1, tot_call_oi), 2)
        pcr_vol = round(tot_put_vol / max(1, tot_call_vol), 2)
        max_pain = calculate_max_pain(pain_data)

        return OptionChain(
            underlying=underlying,
            underlying_price=round(underlying_price, 2),
            as_of_date=today_str,
            expiry_date=expiry_date,
            days_to_expiry=days_to_exp,
            pcr_oi=pcr_oi,
            pcr_volume=pcr_vol,
            max_pain_strike=max_pain,
            total_call_oi=tot_call_oi,
            total_put_oi=tot_put_oi,
            total_call_volume=tot_call_vol,
            total_put_volume=tot_put_vol,
            strikes=chain_rows,
            disclaimer=self.DISCLAIMER,
        )

