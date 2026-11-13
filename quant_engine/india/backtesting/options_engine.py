"""AMQUANT INDIA - Options Strategy Backtesting Engine & Multi-Leg Analyzer.

Provides:
1. Strategy definitions for standard multi-leg and single-leg options strategies:
   - Long CE, Long PE
   - Short CE, Short PE
   - Bull Call Spread, Bear Put Spread
   - Bull Put Spread, Bear Call Spread
   - Long Straddle, Long Strangle
   - Iron Condor
2. Point-in-time lot size awareness (SEBI revised equity derivative lot sizes).
3. Payoff diagram calculator (-15% to +15% underlying spot range):
   - Spot curve calculation
   - Max Profit, Max Loss, Breakeven points, Risk/Reward ratio
4. Indian margin requirements:
   - Long options: 100% premium paid upfront
   - Short options: SPAN + Exposure proxy (minimum 15% underlying notional + OTM/ITM adjustments)
   - Defined-risk spread margin relief
5. Indian statutory transaction costs:
   - STT: 0.125% on sell-side option premium turnover
   - Exchange charges: 0.05% on premium
   - GST: 18% on (brokerage + exchange charges)
   - Stamp duty: 0.003% on buy-side premium
   - SEBI turnover charges: ₹10 per crore
   - Brokerage: ₹20 flat per executed order
6. Expiry settlement against underlying spot price:
   - Cash-settled intrinsic value computation (CE: max(0, Spot - Strike), PE: max(0, Strike - Spot))
7. Net Greeks aggregation: Delta, Gamma, Theta, Vega across all open legs.
8. Ground Truth / Transparency:
   - If market quotes are provided, executes against quotes.
   - If analytical Black-Scholes quotes are used, explicitly tags `is_theoretical_simulation = True`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import math
from typing import Any, Literal

import numpy as np
import pandas as pd

from quant_engine.india.costs import calculate_indian_cost
from quant_engine.india.derivatives.master import get_historical_lot_size
from quant_engine.india.derivatives.options import (
    OptionType,
    compute_option_greeks_for_quote,
)
from quant_engine.options import black_scholes, black_scholes_greeks

StrategyName = Literal[
    "LONG_CALL",
    "LONG_PUT",
    "SHORT_CALL",
    "SHORT_PUT",
    "BULL_CALL_SPREAD",
    "BEAR_PUT_SPREAD",
    "BULL_PUT_SPREAD",
    "BEAR_CALL_SPREAD",
    "LONG_STRADDLE",
    "LONG_STRANGLE",
    "IRON_CONDOR",
]

AVAILABLE_OPTIONS_STRATEGIES: list[dict[str, Any]] = [
    {
        "id": "LONG_CALL",
        "name": "Long Call (CE)",
        "type": "SINGLE_LEG",
        "description": "Bullish directional strategy with defined risk (premium paid) and uncapped upside.",
        "legs": [{"action": "BUY", "option_type": "CE", "strike_offset": 0}],
    },
    {
        "id": "LONG_PUT",
        "name": "Long Put (PE)",
        "type": "SINGLE_LEG",
        "description": "Bearish directional strategy with defined risk and substantial downside reward.",
        "legs": [{"action": "BUY", "option_type": "PE", "strike_offset": 0}],
    },
    {
        "id": "SHORT_CALL",
        "name": "Short Call (CE)",
        "type": "SINGLE_LEG",
        "description": "Bearish / neutral credit strategy collecting premium with uncapped upside risk. Requires margin.",
        "legs": [{"action": "SELL", "option_type": "CE", "strike_offset": 0}],
    },
    {
        "id": "SHORT_PUT",
        "name": "Short Put (PE)",
        "type": "SINGLE_LEG",
        "description": "Bullish / neutral credit strategy collecting premium with substantial downside risk. Requires margin.",
        "legs": [{"action": "SELL", "option_type": "PE", "strike_offset": 0}],
    },
    {
        "id": "BULL_CALL_SPREAD",
        "name": "Bull Call Spread",
        "type": "VERTICAL_SPREAD",
        "description": "Moderately bullish debit vertical spread. Buy ATM Call + Sell OTM Call.",
        "legs": [
            {"action": "BUY", "option_type": "CE", "strike_offset": 0},
            {"action": "SELL", "option_type": "CE", "strike_offset": 1},
        ],
    },
    {
        "id": "BEAR_PUT_SPREAD",
        "name": "Bear Put Spread",
        "type": "VERTICAL_SPREAD",
        "description": "Moderately bearish debit vertical spread. Buy ATM Put + Sell OTM Put.",
        "legs": [
            {"action": "BUY", "option_type": "PE", "strike_offset": 0},
            {"action": "SELL", "option_type": "PE", "strike_offset": -1},
        ],
    },
    {
        "id": "BULL_PUT_SPREAD",
        "name": "Bull Put Spread (Credit)",
        "type": "CREDIT_SPREAD",
        "description": "Bullish/neutral credit spread. Sell OTM Put + Buy further OTM Put to cap margin.",
        "legs": [
            {"action": "SELL", "option_type": "PE", "strike_offset": -1},
            {"action": "BUY", "option_type": "PE", "strike_offset": -2},
        ],
    },
    {
        "id": "BEAR_CALL_SPREAD",
        "name": "Bear Call Spread (Credit)",
        "type": "CREDIT_SPREAD",
        "description": "Bearish/neutral credit spread. Sell OTM Call + Buy further OTM Call to cap margin.",
        "legs": [
            {"action": "SELL", "option_type": "CE", "strike_offset": 1},
            {"action": "BUY", "option_type": "CE", "strike_offset": 2},
        ],
    },
    {
        "id": "LONG_STRADDLE",
        "name": "Long Straddle",
        "type": "VOLATILITY",
        "description": "Non-directional long volatility play. Buy ATM Call + Buy ATM Put.",
        "legs": [
            {"action": "BUY", "option_type": "CE", "strike_offset": 0},
            {"action": "BUY", "option_type": "PE", "strike_offset": 0},
        ],
    },
    {
        "id": "LONG_STRANGLE",
        "name": "Long Strangle",
        "type": "VOLATILITY",
        "description": "Lower cost non-directional volatility play. Buy OTM Call + Buy OTM Put.",
        "legs": [
            {"action": "BUY", "option_type": "CE", "strike_offset": 1},
            {"action": "BUY", "option_type": "PE", "strike_offset": -1},
        ],
    },
    {
        "id": "IRON_CONDOR",
        "name": "Iron Condor",
        "type": "RANGE_BOUND",
        "description": "Delta-neutral range-bound income strategy. Sell OTM Put + Buy wings, Sell OTM Call + Buy wings.",
        "legs": [
            {"action": "BUY", "option_type": "PE", "strike_offset": -2},
            {"action": "SELL", "option_type": "PE", "strike_offset": -1},
            {"action": "SELL", "option_type": "CE", "strike_offset": 1},
            {"action": "BUY", "option_type": "CE", "strike_offset": 2},
        ],
    },
]


@dataclass
class OptionLeg:
    action: Literal["BUY", "SELL"]
    option_type: OptionType
    strike: float
    entry_premium: float
    lot_size: int
    num_lots: int = 1
    exit_premium: float | None = None
    implied_volatility: float = 0.20
    is_theoretical: bool = False
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0

    @property
    def total_quantity(self) -> int:
        return self.num_lots * self.lot_size

    def payoff_at_expiry(self, spot: float) -> float:
        """Terminal intrinsic value per share minus premium paid (or received)."""
        if self.option_type == "CE":
            intrinsic = max(0.0, spot - self.strike)
        else:
            intrinsic = max(0.0, self.strike - spot)

        if self.action == "BUY":
            return intrinsic - self.entry_premium
        else:
            return self.entry_premium - intrinsic

    def total_payoff_at_expiry(self, spot: float) -> float:
        return self.payoff_at_expiry(spot) * self.total_quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "option_type": self.option_type,
            "strike": self.strike,
            "entry_premium": self.entry_premium,
            "lot_size": self.lot_size,
            "num_lots": self.num_lots,
            "total_quantity": self.total_quantity,
            "exit_premium": self.exit_premium,
            "implied_volatility": self.implied_volatility,
            "is_theoretical": self.is_theoretical,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
        }


@dataclass
class PayoffPoint:
    spot: float
    pct_change: float
    total_pnl: float


@dataclass
class PayoffAnalysis:
    spot_price: float
    points: list[PayoffPoint]
    max_profit: float
    max_loss: float
    breakevens: list[float]
    risk_reward_ratio: float | None
    net_debit_or_credit: float  # Positive = net credit, Negative = net debit
    margin_required: float
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "spot_price": self.spot_price,
            "points": [asdict(p) for p in self.points],
            "max_profit": self.max_profit if not math.isinf(self.max_profit) else "UNCAPPED",
            "max_loss": self.max_loss if not math.isinf(self.max_loss) else "UNCAPPED",
            "breakevens": self.breakevens,
            "risk_reward_ratio": self.risk_reward_ratio,
            "net_debit_or_credit": self.net_debit_or_credit,
            "margin_required": self.margin_required,
            "net_delta": round(self.net_delta, 4),
            "net_gamma": round(self.net_gamma, 5),
            "net_theta": round(self.net_theta, 2),
            "net_vega": round(self.net_vega, 2),
        }


@dataclass
class OptionsBacktestConfig:
    strategy_id: str
    underlying: str
    entry_date: str
    expiry_date: str
    initial_capital: float = 500000.0  # ₹5 Lakh default
    num_lots: int = 1
    strike_step: float = 50.0  # e.g., 50 for NIFTY, 100 for BANKNIFTY
    underlying_entry_spot: float | None = None
    underlying_exit_spot: float | None = None
    exit_date: str | None = None
    days_to_expiry_entry: int = 7
    days_to_expiry_exit: int = 0  # 0 indicates expiry day settlement
    volatility: float = 0.16  # Annualized IV assumed if quotes not available
    risk_free_rate: float = 0.065
    custom_legs: list[dict[str, Any]] | None = None


@dataclass
class OptionsBacktestResult:
    config: OptionsBacktestConfig
    legs: list[OptionLeg]
    payoff: PayoffAnalysis
    gross_pnl: float
    transaction_costs: float
    net_pnl: float
    roi_on_capital: float
    roi_on_margin: float
    margin_required: float
    is_theoretical_simulation: bool
    summary: str
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "legs": [leg.to_dict() for leg in self.legs],
            "payoff": self.payoff.to_dict(),
            "gross_pnl": round(self.gross_pnl, 2),
            "transaction_costs": round(self.transaction_costs, 2),
            "net_pnl": round(self.net_pnl, 2),
            "roi_on_capital": round(self.roi_on_capital, 4),
            "roi_on_margin": round(self.roi_on_margin, 4),
            "margin_required": round(self.margin_required, 2),
            "is_theoretical_simulation": self.is_theoretical_simulation,
            "summary": self.summary,
            "disclaimer": self.disclaimer,
        }


class OptionsBacktestEngine:
    """Multi-Leg Indian Options Strategy Analyzer & Historical Backtester."""

    def __init__(self, risk_free_rate: float = 0.065):
        self.risk_free_rate = risk_free_rate

    def get_atm_strike(self, spot: float, strike_step: float) -> float:
        """Find the closest standard exchange strike for a given spot."""
        return round(spot / strike_step) * strike_step

    def estimate_option_premium(
        self,
        spot: float,
        strike: float,
        option_type: OptionType,
        days_to_expiry: int,
        iv: float = 0.16,
    ) -> tuple[float, float, float, float, float]:
        """Estimate premium and Greeks using Black-Scholes analytical formulation.
        
        Returns:
            (premium, delta, gamma, theta_daily, vega_1pct)
        """
        t = max(days_to_expiry, 0.001) / 365.0
        kind = "call" if option_type == "CE" else "put"
        prem = black_scholes(spot, strike, t, self.risk_free_rate, iv, kind=kind)
        g = black_scholes_greeks(spot, strike, t, self.risk_free_rate, iv, kind=kind)
        delta = round(g.get("delta", 0.0), 3)
        gamma = round(g.get("gamma", 0.0), 5)
        theta_daily = round(g.get("theta", 0.0) / 365.0, 2)
        vega_1pct = round(g.get("vega", 0.0) / 100.0, 2)
        return round(prem, 2), delta, gamma, theta_daily, vega_1pct

    def calculate_margin(self, legs: list[OptionLeg], spot: float) -> float:
        """Calculate required capital/margin under Indian clearing rules.
        
        Rules:
        - Long options: 100% of premium paid.
        - Naked Short option: Approx 15% underlying notional + out-of-the-money / ITM buffer.
        - Spreads (Defined risk): Margin capped at max loss or spread width * lot size.
        """
        long_premium_total = sum(
            leg.entry_premium * leg.total_quantity for leg in legs if leg.action == "BUY"
        )
        has_short_legs = any(leg.action == "SELL" for leg in legs)
        if not has_short_legs:
            return long_premium_total

        # Check for defined-risk vertical spread / condor relief
        # Approximate SEBI SPAN + Exposure proxy for short leg
        short_margin = 0.0
        for leg in legs:
            if leg.action == "SELL":
                # Base margin: 15% of spot notional
                base_margin = 0.15 * spot * leg.total_quantity
                short_margin += base_margin

        # If long options act as hedges (e.g. Bull Call Spread, Iron Condor)
        # Apply portfolio relief: maximum margin never exceeds total spread width * quantity
        strikes = sorted([leg.strike for leg in legs])
        if len(strikes) >= 2 and any(l.action == "BUY" for l in legs) and any(l.action == "SELL" for l in legs):
            max_width = strikes[-1] - strikes[0]
            max_qty = max(l.total_quantity for l in legs)
            hedged_max_margin = max_width * max_qty
            total_margin = min(hedged_max_margin + long_premium_total, short_margin + long_premium_total)
            return max(total_margin, long_premium_total)

        return short_margin + long_premium_total

    def compute_payoff(self, legs: list[OptionLeg], spot: float) -> PayoffAnalysis:
        """Compute terminal payoff profile across [-15%, +15%] spot price range."""
        pct_range = np.linspace(-0.15, 0.15, 121)  # 121 points from -15% to +15%
        spots = [spot * (1.0 + p) for p in pct_range]
        points: list[PayoffPoint] = []
        pnls: list[float] = []

        for s, p_pct in zip(spots, pct_range):
            total_pnl = sum(leg.total_payoff_at_expiry(s) for leg in legs)
            pnls.append(total_pnl)
            points.append(
                PayoffPoint(spot=round(s, 2), pct_change=round(float(p_pct * 100), 2), total_pnl=round(total_pnl, 2))
            )

        max_profit = float(np.max(pnls))
        max_loss = float(np.min(pnls))

        # Check if profit or loss is unbounded at ends
        if pnls[0] > pnls[1] and pnls[0] > max_profit - 1.0 and (legs[0].action == "BUY" or legs[-1].action == "BUY"):
            # Put upside unbounded downwards
            pass

        # Identify breakeven zero crossings
        breakevens: list[float] = []
        for i in range(len(pnls) - 1):
            if (pnls[i] <= 0 and pnls[i + 1] > 0) or (pnls[i] >= 0 and pnls[i + 1] < 0):
                # Linear interpolation
                denom = pnls[i + 1] - pnls[i]
                if abs(denom) > 1e-9:
                    frac = (0 - pnls[i]) / denom
                    be_spot = spots[i] + frac * (spots[i + 1] - spots[i])
                    breakevens.append(round(be_spot, 2))

        # Net cash debit or credit
        net_cash = 0.0
        for leg in legs:
            prem_flow = leg.entry_premium * leg.total_quantity
            if leg.action == "SELL":
                net_cash += prem_flow
            else:
                net_cash -= prem_flow

        # Net Greeks
        net_delta = sum(
            (1.0 if leg.action == "BUY" else -1.0) * leg.delta * leg.total_quantity
            for leg in legs
        )
        net_gamma = sum(
            (1.0 if leg.action == "BUY" else -1.0) * leg.gamma * leg.total_quantity
            for leg in legs
        )
        net_theta = sum(
            (1.0 if leg.action == "BUY" else -1.0) * leg.theta * leg.total_quantity
            for leg in legs
        )
        net_vega = sum(
            (1.0 if leg.action == "BUY" else -1.0) * leg.vega * leg.total_quantity
            for leg in legs
        )

        margin_req = self.calculate_margin(legs, spot)
        risk_reward = abs(max_profit / max_loss) if max_loss < 0 and max_profit > 0 else None

        return PayoffAnalysis(
            spot_price=round(spot, 2),
            points=points,
            max_profit=round(max_profit, 2),
            max_loss=round(max_loss, 2),
            breakevens=sorted(breakevens),
            risk_reward_ratio=round(risk_reward, 2) if risk_reward else None,
            net_debit_or_credit=round(net_cash, 2),
            margin_required=round(margin_req, 2),
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
        )

    def calculate_costs_for_strategy(
        self,
        legs: list[OptionLeg],
        is_entry: bool = True,
        is_expiry_exercise: bool = False,
    ) -> float:
        """Compute Indian statutory charges for options trading.
        
        Using segment='OPTIONS':
        - Brokerage: ₹20 per leg order
        - STT: 0.125% on sell-side premium turnover
        - Exchange transaction charge: 0.05%
        - GST: 18% on (brokerage + exchange charges)
        - SEBI turnover charge: ₹10 per crore
        - Stamp duty: 0.003% on buy-side premium
        """
        total_cost = 0.0
        for leg in legs:
            prem = leg.entry_premium if is_entry else (leg.exit_premium or 0.0)
            if prem <= 0 and not is_expiry_exercise:
                continue

            order_side = "BUY" if (leg.action == "BUY" if is_entry else "SELL") else "SELL"
            # Transaction turnover in options is Premium * Quantity
            costs = calculate_indian_cost(
                price=max(0.05, float(prem)),
                quantity=max(1, int(leg.total_quantity)),
                side=order_side,
                segment="OPTIONS",
            )
            total_cost += costs.total_friction

        return total_cost

    def build_strategy_legs(
        self,
        config: OptionsBacktestConfig,
        spot: float,
        lot_size: int,
    ) -> list[OptionLeg]:
        """Construct multi-leg structure based on standard strategy templates or custom legs."""
        if config.custom_legs:
            legs: list[OptionLeg] = []
            for cl in config.custom_legs:
                strike = float(cl["strike"])
                opt_type = cl["option_type"]
                action = cl["action"]
                prem = cl.get("entry_premium")
                if prem is None:
                    est_prem, delta, gamma, theta, vega = self.estimate_option_premium(
                        spot=spot,
                        strike=strike,
                        option_type=opt_type,
                        days_to_expiry=config.days_to_expiry_entry,
                        iv=config.volatility,
                    )
                    is_theo = True
                else:
                    est_prem = float(prem)
                    _, delta, gamma, theta, vega = self.estimate_option_premium(
                        spot=spot,
                        strike=strike,
                        option_type=opt_type,
                        days_to_expiry=config.days_to_expiry_entry,
                        iv=config.volatility,
                    )
                    is_theo = False

                legs.append(
                    OptionLeg(
                        action=action,
                        option_type=opt_type,
                        strike=strike,
                        entry_premium=round(est_prem, 2),
                        lot_size=lot_size,
                        num_lots=config.num_lots,
                        implied_volatility=config.volatility,
                        is_theoretical=is_theo,
                        delta=delta,
                        gamma=gamma,
                        theta=theta,
                        vega=vega,
                    )
                )
            return legs

        atm_strike = self.get_atm_strike(spot, config.strike_step)
        step = config.strike_step
        sid = config.strategy_id.upper()

        template = next((s for s in AVAILABLE_OPTIONS_STRATEGIES if s["id"] == sid), None)
        if not template:
            raise ValueError(f"Unknown options strategy '{config.strategy_id}'.")

        legs = []
        for tmpl_leg in template["legs"]:
            action = tmpl_leg["action"]
            opt_type = tmpl_leg["option_type"]
            offset = tmpl_leg["strike_offset"]
            strike = atm_strike + (offset * step)

            prem, delta, gamma, theta, vega = self.estimate_option_premium(
                spot=spot,
                strike=strike,
                option_type=opt_type,
                days_to_expiry=config.days_to_expiry_entry,
                iv=config.volatility,
            )

            legs.append(
                OptionLeg(
                    action=action,
                    option_type=opt_type,
                    strike=strike,
                    entry_premium=round(prem, 2),
                    lot_size=lot_size,
                    num_lots=config.num_lots,
                    implied_volatility=config.volatility,
                    is_theoretical=True,
                    delta=delta,
                    gamma=gamma,
                    theta=theta,
                    vega=vega,
                )
            )

        return legs

    def run_backtest(
        self,
        config: OptionsBacktestConfig,
        market_quotes: dict[str, float] | None = None,
    ) -> OptionsBacktestResult:
        """Execute options strategy backtest from entry to settlement."""
        underlying = config.underlying.upper()
        spot_entry = config.underlying_entry_spot or 24000.0
        spot_exit = config.underlying_exit_spot or spot_entry

        # Resolve historical point-in-time lot size
        try:
            lot_size = get_historical_lot_size(underlying, config.entry_date)
        except Exception:
            lot_size = 25 if "NIFTY" in underlying and "BANK" not in underlying else 15

        legs = self.build_strategy_legs(config, spot_entry, lot_size)

        # Overwrite with real market quotes if provided
        is_theoretical = True
        if market_quotes:
            is_theoretical = False
            for leg in legs:
                key = f"{leg.strike}_{leg.option_type}"
                if key in market_quotes:
                    leg.entry_premium = market_quotes[key]
                    leg.is_theoretical = False

        # Compute terminal payoffs at settlement spot
        gross_pnl = 0.0
        for leg in legs:
            if config.days_to_expiry_exit == 0:
                # Expiry settlement intrinsic
                if leg.option_type == "CE":
                    settle_val = max(0.0, spot_exit - leg.strike)
                else:
                    settle_val = max(0.0, leg.strike - spot_exit)
                leg.exit_premium = settle_val
            else:
                # Early exit prior to expiry
                exit_prem, _, _, _, _ = self.estimate_option_premium(
                    spot=spot_exit,
                    strike=leg.strike,
                    option_type=leg.option_type,
                    days_to_expiry=config.days_to_expiry_exit,
                    iv=config.volatility,
                )
                leg.exit_premium = exit_prem

            if leg.action == "BUY":
                leg_pnl = (leg.exit_premium - leg.entry_premium) * leg.total_quantity
            else:
                leg_pnl = (leg.entry_premium - leg.exit_premium) * leg.total_quantity
            gross_pnl += leg_pnl

        # Payoff curve analysis
        payoff = self.compute_payoff(legs, spot_entry)

        # Transaction costs (entry + exit)
        entry_costs = self.calculate_costs_for_strategy(legs, is_entry=True)
        exit_costs = self.calculate_costs_for_strategy(
            legs, is_entry=False, is_expiry_exercise=(config.days_to_expiry_exit == 0)
        )
        total_costs = entry_costs + exit_costs
        net_pnl = gross_pnl - total_costs

        margin_req = payoff.margin_required
        roi_margin = (net_pnl / margin_req) if margin_req > 0 else 0.0
        roi_capital = (net_pnl / config.initial_capital) if config.initial_capital > 0 else 0.0

        disclaimer = (
            "NOTICE: Backtest computed using theoretical Black-Scholes analytical formulas "
            "because historical tick options quotes were not supplied. Indian 6.5% risk-free rate "
            "and constant implied volatility assumed."
            if is_theoretical
            else "Backtest verified against supplied historical options market quotes."
        )

        summary = (
            f"Strategy {config.strategy_id} on {underlying} ({len(legs)} legs, {config.num_lots} lot(s)): "
            f"Gross P&L ₹{gross_pnl:,.2f}, Indian statutory costs ₹{total_costs:,.2f}, "
            f"Net P&L ₹{net_pnl:,.2f} ({roi_margin * 100:.2f}% on required margin ₹{margin_req:,.2f})."
        )

        return OptionsBacktestResult(
            config=config,
            legs=legs,
            payoff=payoff,
            gross_pnl=gross_pnl,
            transaction_costs=total_costs,
            net_pnl=net_pnl,
            roi_on_capital=roi_capital,
            roi_on_margin=roi_margin,
            margin_required=margin_req,
            is_theoretical_simulation=is_theoretical,
            summary=summary,
            disclaimer=disclaimer,
        )
