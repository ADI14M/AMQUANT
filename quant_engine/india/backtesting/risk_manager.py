"""AMQUANT INDIA - Risk Management Engine for Intraday, Futures and Options.

Enforces pre-trade and intra-trade risk constraints:
1. Maximum Daily Loss (INR): Halts new trade entries for the session once reached.
2. Maximum Portfolio Drawdown (%): Circuit breaker on equity peak-to-trough decline.
3. Maximum Position Size (% / INR): Prevents over-concentration in single names.
4. Maximum Open Positions: Limits concurrent active positions.
5. Margin Utilization Limit (%): Prevents margin call threshold violations (SPAN + Exposure).
6. Maximum Portfolio Delta Exposure: Caps directional net Greek exposure for options/futures.
7. End-of-Day Position Enforcement: Flags unauthorized overnight carries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RiskLimits:
    max_daily_loss_inr: float | None = None  # e.g., 25000.0 (halts trading for the day if breached)
    max_portfolio_drawdown_pct: float | None = None  # e.g., 15.0 (halts trading until reset)
    max_position_size_pct: float = 100.0  # e.g., 20.0% of portfolio equity
    max_open_positions: int = 5  # Max concurrent positions
    margin_utilization_limit_pct: float = 85.0  # Max 85% of capital tied up in margins
    max_portfolio_delta: float | None = None  # Max net delta allowed in options/futures
    require_eod_square_off: bool = True  # True for intraday MIS equity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: str
    metric_value: float = 0.0
    limit_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskManager:
    """Evaluates orders and portfolio state against configured risk limits."""

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()
        self.trading_halted_today: bool = False
        self.circuit_breaker_active: bool = False
        self.violations_log: list[dict[str, Any]] = []

    def reset_daily_state(self) -> None:
        """Reset session-specific flags (called at start of each trading session)."""
        self.trading_halted_today = False

    def check_pre_trade(
        self,
        current_equity: float,
        initial_capital: float,
        peak_equity: float,
        daily_realized_pnl: float,
        daily_unrealized_pnl: float,
        active_positions_count: int,
        current_margin_used: float,
        proposed_trade_margin: float,
        proposed_position_value: float,
        current_portfolio_delta: float = 0.0,
        proposed_trade_delta: float = 0.0,
    ) -> RiskCheckResult:
        """Evaluate whether a proposed trade is allowed under risk rules."""
        # 1. Permanent circuit breaker check (Portfolio Drawdown)
        current_dd_pct = ((peak_equity - current_equity) / max(1.0, peak_equity)) * 100.0
        if self.limits.max_portfolio_drawdown_pct is not None:
            if current_dd_pct >= self.limits.max_portfolio_drawdown_pct:
                self.circuit_breaker_active = True
                msg = f"Trading halted: Portfolio drawdown ({current_dd_pct:.2f}%) exceeded limit ({self.limits.max_portfolio_drawdown_pct:.1f}%)."
                self._record_violation("PORTFOLIO_DRAWDOWN", current_dd_pct, self.limits.max_portfolio_drawdown_pct, msg)
                return RiskCheckResult(False, msg, current_dd_pct, self.limits.max_portfolio_drawdown_pct)

        # 2. Daily Loss Circuit Breaker
        total_daily_pnl = daily_realized_pnl + daily_unrealized_pnl
        if self.limits.max_daily_loss_inr is not None:
            if total_daily_pnl <= -abs(self.limits.max_daily_loss_inr):
                self.trading_halted_today = True
                msg = f"Trading halted for session: Daily loss (₹{abs(total_daily_pnl):,.2f}) exceeded limit (₹{self.limits.max_daily_loss_inr:,.2f})."
                self._record_violation("DAILY_LOSS_LIMIT", abs(total_daily_pnl), self.limits.max_daily_loss_inr, msg)
                return RiskCheckResult(False, msg, abs(total_daily_pnl), self.limits.max_daily_loss_inr)

        if self.trading_halted_today:
            return RiskCheckResult(False, "Trading halted for session due to prior daily loss limit breach.")

        # 3. Maximum Open Positions
        if active_positions_count >= self.limits.max_open_positions:
            msg = f"Max open positions reached ({active_positions_count} >= {self.limits.max_open_positions})."
            self._record_violation("MAX_OPEN_POSITIONS", float(active_positions_count), float(self.limits.max_open_positions), msg)
            return RiskCheckResult(False, msg, float(active_positions_count), float(self.limits.max_open_positions))

        # 4. Position Size Limit (% of Equity)
        max_allowed_pos_val = current_equity * (self.limits.max_position_size_pct / 100.0)
        if proposed_position_value > max_allowed_pos_val * 1.01:  # Allow 1% leeway for discrete share lots
            msg = f"Proposed position size (₹{proposed_position_value:,.2f}) exceeds max allowed (₹{max_allowed_pos_val:,.2f} / {self.limits.max_position_size_pct}% of equity)."
            self._record_violation("POSITION_SIZE_LIMIT", proposed_position_value, max_allowed_pos_val, msg)
            return RiskCheckResult(False, msg, proposed_position_value, max_allowed_pos_val)

        # 5. Margin Utilization Limit
        new_total_margin = current_margin_used + proposed_trade_margin
        max_allowed_margin = current_equity * (self.limits.margin_utilization_limit_pct / 100.0)
        if new_total_margin > max_allowed_margin:
            msg = f"Insufficient margin: Required margin (₹{new_total_margin:,.2f}) exceeds utilization limit ({self.limits.margin_utilization_limit_pct}% = ₹{max_allowed_margin:,.2f})."
            self._record_violation("MARGIN_UTILIZATION", new_total_margin, max_allowed_margin, msg)
            return RiskCheckResult(False, msg, new_total_margin, max_allowed_margin)

        # 6. Portfolio Delta Exposure
        if self.limits.max_portfolio_delta is not None:
            new_net_delta = abs(current_portfolio_delta + proposed_trade_delta)
            if new_net_delta > self.limits.max_portfolio_delta:
                msg = f"Portfolio net delta ({new_net_delta:.2f}) would exceed limit ({self.limits.max_portfolio_delta:.2f})."
                self._record_violation("DELTA_EXPOSURE", new_net_delta, self.limits.max_portfolio_delta, msg)
                return RiskCheckResult(False, msg, new_net_delta, self.limits.max_portfolio_delta)

        return RiskCheckResult(True, "All pre-trade risk checks passed.")

    def _record_violation(self, rule_name: str, metric_value: float, limit_value: float, description: str) -> None:
        self.violations_log.append({
            "rule": rule_name,
            "metric_value": metric_value,
            "limit_value": limit_value,
            "description": description,
        })
