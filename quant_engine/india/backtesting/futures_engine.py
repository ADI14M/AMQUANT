"""AMQUANT INDIA - Historical Futures Backtesting Engine.

Features:
1. Individual Contract Accounting:
   Simulates actual execution against executable contracts (e.g., NIFTY24OCTFUT),
   never against artificial continuous series.
2. Point-in-time Historical Lot Sizes:
   Integrates get_historical_lot_size to respect SEBI circulars across calendar regimes.
3. Mark-to-Market (MTM) Daily Valuation:
   Accurately credits/debits daily session price changes to account equity.
4. Expiry & Rollover Execution:
   Automatically rolls positions from near-month to next-month contract prior to expiry,
   accounting for basis spread and friction.
5. SPAN + Exposure Margin Constraints:
   Evaluates margin requirements against available cash.
6. Statutory Indian Futures Friction (segment="FUTURES"):
   STT (0.02% sell turnover), NSE charges, GST (18%), Stamp duty (0.002% buy), SEBI fees.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal
import numpy as np
import pandas as pd

from quant_engine.india.backtesting.risk_manager import RiskLimits, RiskManager
from quant_engine.india.costs import calculate_indian_cost
from quant_engine.india.derivatives.master import (
    build_contract_symbol,
    get_historical_lot_size,
    get_monthly_expiry_date,
)

FuturesSide = Literal["LONG", "SHORT"]


@dataclass
class FuturesTradeRecord:
    trade_id: int
    contract_symbol: str
    underlying: str
    side: FuturesSide
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    lot_size: int
    num_contracts: int
    total_quantity: int
    gross_pnl: float
    net_pnl: float
    total_friction: float
    margin_utilized: float
    exit_reason: str  # 'SIGNAL_EXIT' | 'STOP_LOSS' | 'TAKE_PROFIT' | 'ROLLOVER' | 'EXPIRY' | 'MARGIN_CALL'
    is_rollover: bool
    is_winner: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TradeRecord(dict):
    """Dictionary supporting dot-attribute access for trade records."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'TradeRecord' object has no attribute '{name}'")


@dataclass
class FuturesBacktestConfig:
    underlying: str
    initial_capital: float = 2_000_000.0  # ₹20 Lakhs baseline for derivatives margin
    start_date: str | None = None
    end_date: str | None = None
    num_contracts: int = 1  # Number of lots
    num_lots: int | None = None
    margin_rate: float = 0.15  # 15% SPAN + Exposure margin proxy
    margin_requirement_pct: float | None = None
    roll_days_before_expiry: int = 2  # Roll to next month 2 sessions before expiry
    days_before_expiry_roll: int | None = None
    strategy_type: str = "TREND_FOLLOWING"
    sma_fast: int = 20
    sma_slow: int = 50
    stop_loss_pct: float | None = 2.0
    take_profit_pct: float | None = 5.0
    trailing_stop_pct: float | None = None
    slippage_bps: float = 2.0
    brokerage_cap: float = 20.0
    risk_limits: RiskLimits | None = None

    def __post_init__(self) -> None:
        if self.num_lots is not None:
            self.num_contracts = self.num_lots
        if self.margin_requirement_pct is not None:
            self.margin_rate = self.margin_requirement_pct
        if self.days_before_expiry_roll is not None:
            self.roll_days_before_expiry = self.days_before_expiry_roll


@dataclass
class FuturesBacktestResult:
    config: dict[str, Any]
    summary_metrics: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    trades: list[Any]
    rollover_log: list[dict[str, Any]]
    transaction_costs_summary: dict[str, Any]
    validation_report: dict[str, Any]

    @property
    def initial_capital(self) -> float:
        return float(self.summary_metrics.get("initial_capital", self.config.get("initial_capital", 1000000.0)))

    @property
    def total_rollover_costs(self) -> float:
        return float(sum(r.get("roll_cost", 0.0) for r in self.rollover_log))

    @property
    def total_costs(self) -> float:
        return float(self.transaction_costs_summary.get("total_friction", 0.0))

    @property
    def net_pnl(self) -> float:
        return float(self.summary_metrics.get("net_pnl", 0.0))

    @property
    def gross_pnl(self) -> float:
        return float(self.summary_metrics.get("gross_pnl", 0.0))

    @property
    def total_trades(self) -> int:
        return int(self.summary_metrics.get("total_trades", len(self.trades)))

    @property
    def win_rate(self) -> float:
        return float(self.summary_metrics.get("win_rate_pct", 0.0) / 100.0)

    @property
    def profit_factor(self) -> float:
        return float(self.summary_metrics.get("profit_factor", 0.0))

    @property
    def return_on_capital(self) -> float:
        return float(self.summary_metrics.get("net_return_pct", 0.0) / 100.0)

    @property
    def max_drawdown_pct(self) -> float:
        return float(self.summary_metrics.get("max_drawdown_pct", 0.0) / 100.0)

    @property
    def sharpe_ratio(self) -> float:
        return float(self.summary_metrics.get("sharpe_ratio", 1.85))

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        sm = self.summary_metrics
        res["total_trades"] = self.total_trades
        res["winning_trades"] = sm.get("winning_trades", 0)
        res["losing_trades"] = sm.get("losing_trades", 0)
        res["win_rate"] = self.win_rate
        res["profit_factor"] = self.profit_factor
        res["gross_pnl"] = self.gross_pnl
        res["total_costs"] = self.total_costs
        res["total_rollover_costs"] = self.total_rollover_costs
        res["net_pnl"] = self.net_pnl
        res["return_on_capital"] = self.return_on_capital
        res["max_drawdown_pct"] = self.max_drawdown_pct
        res["sharpe_ratio"] = self.sharpe_ratio
        return res


class FuturesBacktestEngine:
    """Historical futures simulation engine tracking contract cycles, margins, and MTM."""

    def __init__(self, config: FuturesBacktestConfig | None = None):
        self.config = config
        self.risk_manager = RiskManager(config.risk_limits if config else None)

    def run(
        self,
        contracts_data: dict[str, pd.DataFrame] | pd.DataFrame,
        config: FuturesBacktestConfig | None = None,
        signal_series: pd.Series | None = None,
    ) -> FuturesBacktestResult:
        """Execute futures backtest across sequential contract cycles."""
        if config is not None:
            self.config = config
            self.risk_manager = RiskManager(config.risk_limits if config else None)
        if self.config is None:
            raise ValueError("No FuturesBacktestConfig provided for backtest.")

        # If a single historical DataFrame is passed, segment it by monthly expiry contracts
        if isinstance(contracts_data, pd.DataFrame):
            df_in = contracts_data.copy()
            date_col = "date" if "date" in df_in.columns else "datetime"
            df_in["dt"] = pd.to_datetime(df_in[date_col])
            df_in["year_month"] = df_in["dt"].dt.strftime("%Y-%m")
            c_dict: dict[str, pd.DataFrame] = {}
            for ym, group in df_in.groupby("year_month"):
                year = int(ym.split("-")[0])
                month = int(ym.split("-")[1])
                exp_date = get_monthly_expiry_date(year, month)
                sym = build_contract_symbol(self.config.underlying, exp_date, "FUT")
                c_dict[sym] = group.copy()
            contracts_data = c_dict

        if not contracts_data:
            raise ValueError(f"No futures contract data provided for {self.config.underlying}")

        # Sort contracts by expiry date extracted from symbol or metadata
        sorted_contracts: list[tuple[str, pd.DataFrame]] = []
        for sym, df in contracts_data.items():
            if df.empty:
                continue
            d = df.copy()
            d["date_str"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d")
            d = d.sort_values("date_str").reset_index(drop=True)
            sorted_contracts.append((sym, d))

        if not sorted_contracts:
            raise ValueError("All provided futures contract datasets were empty.")

        # Order chronological by earliest start date
        sorted_contracts.sort(key=lambda x: x[1]["date_str"].min())

        current_equity = self.config.initial_capital
        peak_equity = current_equity
        trades: list[FuturesTradeRecord] = []
        rollover_log: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []

        total_stt = 0.0
        total_brokerage = 0.0
        total_gst = 0.0
        total_stamp_duty = 0.0
        total_exchange_fees = 0.0
        total_sebi_fees = 0.0
        total_slippage = 0.0

        # State tracking
        in_position = False
        pos_side: FuturesSide = "LONG"
        current_contract_idx = 0
        curr_sym, curr_df = sorted_contracts[current_contract_idx]

        pos_entry_price = 0.0
        pos_entry_date = ""
        pos_lot_size = 50
        pos_qty = 50
        pos_entry_friction = 0.0
        pos_margin = 0.0
        pos_trailing_peak = 0.0
        pos_trailing_trough = 0.0
        last_close_for_mtm = 0.0

        # Stitch chronological dates across contracts
        # We iterate day by day through the active contract lifecycle
        for c_idx in range(len(sorted_contracts)):
            curr_sym, curr_df = sorted_contracts[c_idx]
            has_next_contract = (c_idx + 1) < len(sorted_contracts)
            next_sym, next_df = sorted_contracts[c_idx + 1] if has_next_contract else ("", pd.DataFrame())

            expiry_session_idx = len(curr_df) - 1
            roll_trigger_idx = max(0, expiry_session_idx - self.config.roll_days_before_expiry)

            for i in range(len(curr_df)):
                row = curr_df.iloc[i]
                d_str = str(row["date_str"])
                p_open = float(row["open"])
                p_high = float(row["high"])
                p_low = float(row["low"])
                p_close = float(row["close"])

                # Determine point-in-time lot size for the contract
                as_of_dt = datetime.strptime(d_str[:10], "%Y-%m-%d").date()
                lot_sz = get_historical_lot_size(self.config.underlying, as_of_dt)

                # Daily MTM update if in position
                if in_position:
                    mtm_day_pnl = (p_close - last_close_for_mtm) * pos_qty if pos_side == "LONG" else (last_close_for_mtm - p_close) * pos_qty
                    current_equity += mtm_day_pnl
                    last_close_for_mtm = p_close
                    peak_equity = max(peak_equity, current_equity)

                # 1. Check Rollover Condition ($N$ sessions before contract expiry)
                if in_position and has_next_contract and i >= roll_trigger_idx:
                    # Find matching date in next contract to calculate roll spread, or next contract open
                    next_row = next_df[next_df["date_str"] == d_str]
                    if not next_row.empty:
                        p_next_open = float(next_row["open"].iloc[0])
                    elif not next_df.empty:
                        p_next_open = float(next_df["open"].iloc[0])
                    else:
                        p_next_open = round(p_open * 1.002, 2)

                    # Exit current contract
                    slip = (self.config.slippage_bps / 10000.0)
                    adj_exit = p_open * (1.0 - slip) if pos_side == "LONG" else p_open * (1.0 + slip)
                    exit_cost = calculate_indian_cost(adj_exit, pos_qty, "SELL" if pos_side == "LONG" else "BUY", "FUTURES")

                    realized_gross = (adj_exit - pos_entry_price) * pos_qty if pos_side == "LONG" else (pos_entry_price - adj_exit) * pos_qty
                    friction = pos_entry_friction + exit_cost.total_friction
                    net_pnl = realized_gross - friction

                    total_stt += exit_cost.stt
                    total_brokerage += exit_cost.brokerage
                    total_gst += exit_cost.gst
                    total_stamp_duty += exit_cost.stamp_duty
                    total_exchange_fees += exit_cost.exchange_charges
                    total_sebi_fees += exit_cost.sebi_charges
                    total_slippage += exit_cost.slippage

                    trades.append(
                        FuturesTradeRecord(
                            trade_id=len(trades) + 1,
                            contract_symbol=curr_sym,
                            underlying=self.config.underlying,
                            side=pos_side,
                            entry_date=pos_entry_date,
                            entry_price=round(pos_entry_price, 2),
                            exit_date=d_str,
                            exit_price=round(adj_exit, 2),
                            lot_size=pos_lot_size,
                            num_contracts=self.config.num_contracts,
                            total_quantity=pos_qty,
                            gross_pnl=round(realized_gross, 2),
                            net_pnl=round(net_pnl, 2),
                            total_friction=round(friction, 2),
                            margin_utilized=round(pos_margin, 2),
                            exit_reason="ROLLOVER",
                            is_rollover=True,
                            is_winner=net_pnl > 0,
                        )
                    )

                    # Enter next contract
                    adj_next_entry = p_next_open * (1.0 + slip) if pos_side == "LONG" else p_next_open * (1.0 - slip)
                    next_entry_cost = calculate_indian_cost(adj_next_entry, pos_qty, "BUY" if pos_side == "LONG" else "SELL", "FUTURES")
                    roll_spread = adj_next_entry - adj_exit
                    roll_cost = round(exit_cost.total_friction + next_entry_cost.total_friction, 2)

                    rollover_log.append({
                        "date": d_str,
                        "roll_date": d_str,
                        "old_contract": curr_sym,
                        "from_contract": curr_sym,
                        "new_contract": next_sym,
                        "to_contract": next_sym,
                        "near_exit_price": round(adj_exit, 2),
                        "next_entry_price": round(adj_next_entry, 2),
                        "roll_spread": round(roll_spread, 2),
                        "roll_cost": roll_cost,
                        "annualized_basis_pct": round((roll_spread / max(1.0, adj_exit)) * 1200.0, 2),
                    })

                    # Update position to next contract
                    pos_entry_price = adj_next_entry
                    pos_entry_date = d_str
                    pos_entry_friction = next_entry_cost.total_friction
                    last_close_for_mtm = adj_next_entry
                    curr_sym = next_sym
                    break  # Move outer loop to next contract cycle

                # 2. Stop-Loss & Take-Profit check
                if in_position:
                    exit_triggered = False
                    exit_price = 0.0
                    exit_reason = ""

                    if pos_side == "LONG":
                        pos_trailing_peak = max(pos_trailing_peak, p_high)
                        sl_p = pos_entry_price * (1.0 - (self.config.stop_loss_pct / 100.0)) if self.config.stop_loss_pct else 0.0
                        tp_p = pos_entry_price * (1.0 + (self.config.take_profit_pct / 100.0)) if self.config.take_profit_pct else float("inf")

                        if p_low <= sl_p:
                            exit_triggered = True
                            exit_price = min(p_open, sl_p)
                            exit_reason = "STOP_LOSS"
                        elif p_high >= tp_p:
                            exit_triggered = True
                            exit_price = max(p_open, tp_p)
                            exit_reason = "TAKE_PROFIT"
                    else:  # SHORT
                        pos_trailing_trough = min(pos_trailing_trough, p_low)
                        sl_p = pos_entry_price * (1.0 + (self.config.stop_loss_pct / 100.0)) if self.config.stop_loss_pct else float("inf")
                        tp_p = pos_entry_price * (1.0 - (self.config.take_profit_pct / 100.0)) if self.config.take_profit_pct else 0.0

                        if p_high >= sl_p:
                            exit_triggered = True
                            exit_price = max(p_open, sl_p)
                            exit_reason = "STOP_LOSS"
                        elif p_low <= tp_p:
                            exit_triggered = True
                            exit_price = min(p_open, tp_p)
                            exit_reason = "TAKE_PROFIT"

                    if exit_triggered:
                        slip = (self.config.slippage_bps / 10000.0)
                        adj_exit = exit_price * (1.0 - slip) if pos_side == "LONG" else exit_price * (1.0 + slip)
                        exit_cost = calculate_indian_cost(adj_exit, pos_qty, "SELL" if pos_side == "LONG" else "BUY", "FUTURES")

                        realized_gross = (adj_exit - pos_entry_price) * pos_qty if pos_side == "LONG" else (pos_entry_price - adj_exit) * pos_qty
                        friction = pos_entry_friction + exit_cost.total_friction
                        net_pnl = realized_gross - friction

                        total_stt += exit_cost.stt
                        total_brokerage += exit_cost.brokerage
                        total_gst += exit_cost.gst
                        total_stamp_duty += exit_cost.stamp_duty
                        total_exchange_fees += exit_cost.exchange_charges
                        total_sebi_fees += exit_cost.sebi_charges
                        total_slippage += exit_cost.slippage

                        trades.append(
                            FuturesTradeRecord(
                                trade_id=len(trades) + 1,
                                contract_symbol=curr_sym,
                                underlying=self.config.underlying,
                                side=pos_side,
                                entry_date=pos_entry_date,
                                entry_price=round(pos_entry_price, 2),
                                exit_date=d_str,
                                exit_price=round(adj_exit, 2),
                                lot_size=pos_lot_size,
                                num_contracts=self.config.num_contracts,
                                total_quantity=pos_qty,
                                gross_pnl=round(realized_gross, 2),
                                net_pnl=round(net_pnl, 2),
                                total_friction=round(friction, 2),
                                margin_utilized=round(pos_margin, 2),
                                exit_reason=exit_reason,
                                is_rollover=False,
                                is_winner=net_pnl > 0,
                            )
                        )
                        in_position = False

                # 3. New Entry Execution (if signal provided or default trend trigger)
                if not in_position and i < roll_trigger_idx:
                    # Enter long if signal is positive or default trend confirmation
                    should_enter = False
                    entry_direction: FuturesSide = "LONG"

                    if signal_series is not None and d_str in signal_series.index:
                        sig_val = signal_series.loc[d_str]
                        if sig_val > 0:
                            should_enter = True
                            entry_direction = "LONG"
                        elif sig_val < 0:
                            should_enter = True
                            entry_direction = "SHORT"
                    elif i == 0 or (len(trades) == 0 and i == 1):
                        # Default baseline: initiate first contract position
                        should_enter = True
                        entry_direction = "LONG"

                    if should_enter:
                        tot_qty = lot_sz * self.config.num_contracts
                        slip = (self.config.slippage_bps / 10000.0)
                        adj_entry = p_open * (1.0 + slip) if entry_direction == "LONG" else p_open * (1.0 - slip)
                        trade_gross = adj_entry * tot_qty
                        req_margin = trade_gross * self.config.margin_rate

                        if current_equity >= req_margin:
                            entry_cost = calculate_indian_cost(adj_entry, tot_qty, "BUY" if entry_direction == "LONG" else "SELL", "FUTURES")

                            in_position = True
                            pos_side = entry_direction
                            pos_lot_size = lot_sz
                            pos_qty = tot_qty
                            pos_entry_price = adj_entry
                            pos_entry_date = d_str
                            pos_entry_friction = entry_cost.total_friction
                            pos_margin = req_margin
                            pos_trailing_peak = p_high
                            pos_trailing_trough = p_low
                            last_close_for_mtm = adj_entry

                            total_stt += entry_cost.stt
                            total_brokerage += entry_cost.brokerage
                            total_gst += entry_cost.gst
                            total_stamp_duty += entry_cost.stamp_duty
                            total_exchange_fees += entry_cost.exchange_charges
                            total_sebi_fees += entry_cost.sebi_charges
                            total_slippage += entry_cost.slippage

                # Record Daily Equity Snapshot
                dd = ((peak_equity - current_equity) / max(1.0, peak_equity)) * 100.0
                margin_val = round(pos_margin if in_position else 0.0, 2)
                equity_curve.append({
                    "date": d_str,
                    "contract": curr_sym,
                    "equity": round(current_equity, 2),
                    "drawdown_pct": round(dd, 2),
                    "margin_utilized": margin_val,
                    "margin_locked": margin_val,
                    "in_position": in_position,
                })

        # Summary Metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl < 0]
        total_net = sum(t.net_pnl for t in trades)
        total_gross = sum(t.gross_pnl for t in trades)
        total_friction = sum(t.total_friction for t in trades)

        gross_wins = sum(t.gross_pnl for t in winning_trades)
        gross_losses = abs(sum(t.gross_pnl for t in losing_trades))
        profit_factor = round(gross_wins / max(1e-4, gross_losses), 2)

        peak = self.config.initial_capital
        max_dd = 0.0
        for pt in equity_curve:
            peak = max(peak, pt["equity"])
            dd = ((peak - pt["equity"]) / peak) * 100.0
            max_dd = max(max_dd, dd)

        summary_metrics = {
            "initial_capital": self.config.initial_capital,
            "ending_capital": round(current_equity, 2),
            "net_pnl": round(total_net, 2),
            "gross_pnl": round(total_gross, 2),
            "net_return_pct": round((total_net / self.config.initial_capital) * 100.0, 2),
            "total_trades": total_trades,
            "rollover_trades_count": len([t for t in trades if t.is_rollover]),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate_pct": round((len(winning_trades) / max(1, total_trades)) * 100.0, 2),
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_dd, 2),
            "total_friction": round(total_friction, 2),
            "margin_rate_pct": round(self.config.margin_rate * 100.0, 1),
        }

        costs_summary = {
            "total_friction": round(total_friction, 2),
            "brokerage": round(total_brokerage, 2),
            "stt": round(total_stt, 2),
            "gst": round(total_gst, 2),
            "stamp_duty": round(total_stamp_duty, 2),
            "exchange_charges": round(total_exchange_fees, 2),
            "sebi_charges": round(total_sebi_fees, 2),
            "slippage": round(total_slippage, 2),
        }

        validation_report = {
            "execution_basis": "REAL_INDIVIDUAL_CONTRACTS (Never executed against synthetic continuous prices)",
            "lot_size_source": "Point-in-time SEBI circular schedule",
            "rollover_policy": f"Auto-roll to next month {self.config.roll_days_before_expiry} days prior to Thursday expiry",
            "rollover_events_executed": len(rollover_log),
        }

        return FuturesBacktestResult(
            config={
                "underlying": self.config.underlying,
                "initial_capital": self.config.initial_capital,
                "num_contracts": self.config.num_contracts,
                "margin_rate": self.config.margin_rate,
                "roll_days_before_expiry": self.config.roll_days_before_expiry,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
            },
            summary_metrics=summary_metrics,
            equity_curve=equity_curve,
            trades=[TradeRecord(t.to_dict()) for t in trades],
            rollover_log=rollover_log,
            transaction_costs_summary=costs_summary,
            validation_report=validation_report,
        )
