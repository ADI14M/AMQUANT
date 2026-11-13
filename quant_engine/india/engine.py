"""Professional Multi-Asset Historical Backtesting Engine for Indian Equities.

Strictly enforces:
- Realistic next-session (Day t+1 Open) order fills to eliminate look-ahead bias
- Gap-handling on stop-loss and take-profit executions
- Trailing stop-loss tracking peak prices
- Flexible position sizing (percent of equity, fixed capital, fixed shares)
- Cash availability and maximum concurrent positions constraints
- Statutory Indian taxes & transaction costs (STT, GST, Brokerage, Stamp duty, Slippage)
- Full gross vs net accounting
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal
import numpy as np
import pandas as pd

from quant_engine.india.costs import calculate_indian_cost
from quant_engine.india.strategies import BaseStrategy

PositionSizingType = Literal["PERCENT_OF_EQUITY", "FIXED_AMOUNT", "FIXED_SHARES"]


@dataclass
class TradeRecord:
    trade_id: int
    symbol: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    quantity: int
    holding_period_days: int
    gross_pnl: float
    net_pnl: float
    gross_return_pct: float
    net_return_pct: float
    entry_friction: float
    exit_friction: float
    total_friction: float
    exit_reason: str  # 'SIGNAL_EXIT' | 'STOP_LOSS' | 'TAKE_PROFIT' | 'TRAILING_STOP' | 'END_OF_DATA'
    is_winner: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BacktestConfig:
    strategy: BaseStrategy
    symbols: list[str]
    initial_capital: float = 1_000_000.0
    start_date: str | None = None
    end_date: str | None = None
    sizing_type: PositionSizingType = "PERCENT_OF_EQUITY"
    sizing_value: float = 100.0  # 100% of equity for single stock, or e.g. 20% for 5 stocks
    max_concurrent_positions: int = 5
    stop_loss_pct: float | None = None  # e.g. 5.0 for 5% stop loss
    take_profit_pct: float | None = None  # e.g. 15.0 for 15% target
    trailing_stop_pct: float | None = None  # e.g. 5.0 for 5% trailing stop
    slippage_bps: float = 5.0  # 5 bps realistic execution slippage
    brokerage_rate: float = 0.0003  # 0.03%
    brokerage_cap: float = 20.0  # ₹20 discount broker cap
    benchmark_symbol: str = "NIFTY 50"
    risk_free_rate: float = 0.065  # 6.5% Indian 91-day T-bill / RBI repo proxy


@dataclass
class BacktestOutput:
    config: dict[str, Any]
    summary_metrics: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    monthly_returns: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    transaction_costs_summary: dict[str, Any]
    benchmark_comparison: dict[str, Any]
    validation_report: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProfessionalBacktestEngine:
    """Core simulation engine executing strategies across one or more Indian equities."""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(
        self,
        data_map: dict[str, pd.DataFrame],
        benchmark_df: pd.DataFrame | None = None,
    ) -> BacktestOutput:
        """Execute the chronological backtest across provided instrument datasets."""
        if not data_map:
            raise ValueError("Must provide at least one instrument dataset.")

        # 1. Clean and align all datasets on common chronological calendar
        aligned_dfs: dict[str, pd.DataFrame] = {}
        for sym, df in data_map.items():
            if df.empty or len(df) < 2:
                continue
            d = df.copy()
            date_col = next((c for c in d.columns if c in ("date", "timestamp", "datetime")), None)
            if not date_col:
                raise ValueError(f"Instrument {sym} missing date column.")
            d["date_norm"] = pd.to_datetime(d[date_col]).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
            d = d.sort_values(by="date_norm").drop_duplicates(subset=["date_norm"]).reset_index(drop=True)

            # Date filtering if configured
            if self.config.start_date:
                d = d[d["date_norm"] >= self.config.start_date]
            if self.config.end_date:
                d = d[d["date_norm"] <= self.config.end_date]

            if len(d) >= 2:
                aligned_dfs[sym] = d.reset_index(drop=True)

        if not aligned_dfs:
            raise ValueError("No valid price data remained after date filtering.")

        # Compute signals for each symbol
        signals_map: dict[str, pd.Series] = {}
        for sym, df in aligned_dfs.items():
            signals_map[sym] = self.config.strategy.generate_signals(df)

        # Build master unified date timeline
        all_dates_set = set()
        for df in aligned_dfs.values():
            all_dates_set.update(df["date_norm"].tolist())
        calendar_dates = sorted(list(all_dates_set))

        # Index dataframes by date for O(1) lookup
        date_indexed_data: dict[str, dict[str, dict[str, Any]]] = {}
        for sym, df in aligned_dfs.items():
            sigs = signals_map[sym].values
            date_indexed_data[sym] = {}
            for i, r in df.iterrows():
                d_str = r["date_norm"]
                date_indexed_data[sym][d_str] = {
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r.get("volume", 0)),
                    "signal": float(sigs[i]) if i < len(sigs) else 0.0,
                }

        # Simulation state
        cash = float(self.config.initial_capital)
        portfolio_positions: dict[str, dict[str, Any]] = {}  # sym -> {qty, entry_price, entry_date, peak_price}
        trades_history: list[TradeRecord] = []
        trade_id_seq = 1

        daily_equity_curve: list[dict[str, Any]] = []
        total_stt = 0.0
        total_gst = 0.0
        total_brokerage = 0.0
        total_stamp_duty = 0.0
        total_exchange_fees = 0.0
        total_slippage = 0.0

        daily_rf = (1.0 + self.config.risk_free_rate) ** (1.0 / 252.0) - 1.0

        # Run day-by-day simulation
        n_days = len(calendar_dates)
        for t in range(n_days):
            current_date = calendar_dates[t]
            prev_date = calendar_dates[t - 1] if t > 0 else None

            # ─────────────────────────────────────────────────────────
            # STEP A: Check Exits / Stop Losses / Signals for open positions
            # Orders execute at current_date Open (generated at prev_date Close)
            # ─────────────────────────────────────────────────────────
            symbols_to_close: list[tuple[str, str, float]] = []  # (symbol, exit_reason, fill_price)

            for sym, pos in list(portfolio_positions.items()):
                sym_day = date_indexed_data[sym].get(current_date)
                if not sym_day:
                    continue

                curr_open = sym_day["open"]
                curr_high = sym_day["high"]
                curr_low = sym_day["low"]

                # Update peak price for trailing stop
                if curr_high > pos["peak_price"]:
                    pos["peak_price"] = curr_high

                entry_p = pos["entry_price"]
                peak_p = pos["peak_price"]

                # 1. Stop-Loss check (with realistic gap down fill!)
                if self.config.stop_loss_pct is not None:
                    sl_price = entry_p * (1.0 - (self.config.stop_loss_pct / 100.0))
                    if curr_low <= sl_price:
                        # If market gapped down below stop, fill at Open, otherwise at Stop Price
                        fill_p = min(curr_open, sl_price)
                        symbols_to_close.append((sym, "STOP_LOSS", fill_p))
                        continue

                # 2. Take-Profit check (with gap up fill!)
                if self.config.take_profit_pct is not None:
                    tp_price = entry_p * (1.0 + (self.config.take_profit_pct / 100.0))
                    if curr_high >= tp_price:
                        fill_p = max(curr_open, tp_price)
                        symbols_to_close.append((sym, "TAKE_PROFIT", fill_p))
                        continue

                # 3. Trailing Stop-Loss check
                if self.config.trailing_stop_pct is not None:
                    ts_price = peak_p * (1.0 - (self.config.trailing_stop_pct / 100.0))
                    if curr_low <= ts_price:
                        fill_p = min(curr_open, ts_price)
                        symbols_to_close.append((sym, "TRAILING_STOP", fill_p))
                        continue

                # 4. Strategy Exit Signal (generated at prev_date Close)
                if prev_date:
                    prev_sym_data = date_indexed_data[sym].get(prev_date)
                    if prev_sym_data and prev_sym_data["signal"] == 0.0:
                        symbols_to_close.append((sym, "SIGNAL_EXIT", curr_open))
                        continue

            # Execute exits
            for sym, reason, exit_price in symbols_to_close:
                pos = portfolio_positions.pop(sym)
                qty = pos["quantity"]

                # Apply slippage on exit (selling receives slightly less)
                slip_factor = 1.0 - (self.config.slippage_bps / 10000.0)
                eff_exit_price = max(0.05, round(exit_price * slip_factor, 2))

                exit_cost = calculate_indian_cost(
                    price=eff_exit_price,
                    quantity=qty,
                    side="SELL",
                    segment="DELIVERY",
                    base_slippage_bps=0.0,  # slippage already factored into eff_exit_price
                    brokerage_rate=self.config.brokerage_rate,
                    brokerage_cap=self.config.brokerage_cap,
                )

                gross_proceeds = qty * eff_exit_price
                net_proceeds = gross_proceeds - exit_cost.total_friction
                cash += net_proceeds

                gross_pnl = (eff_exit_price - pos["entry_price"]) * qty
                net_pnl = net_proceeds - (pos["entry_price"] * qty + pos["entry_cost_friction"])
                gross_ret = (eff_exit_price / pos["entry_price"] - 1.0) * 100.0
                net_ret = (net_pnl / (pos["entry_price"] * qty + pos["entry_cost_friction"])) * 100.0

                holding_days = max(1, (datetime.strptime(current_date, "%Y-%m-%d") - datetime.strptime(pos["entry_date"], "%Y-%m-%d")).days)

                total_stt += exit_cost.stt
                total_gst += exit_cost.gst
                total_brokerage += exit_cost.brokerage
                total_stamp_duty += exit_cost.stamp_duty
                total_exchange_fees += exit_cost.exchange_charges
                total_slippage += (exit_price - eff_exit_price) * qty

                trades_history.append(
                    TradeRecord(
                        trade_id=trade_id_seq,
                        symbol=sym,
                        entry_date=pos["entry_date"],
                        entry_price=pos["entry_price"],
                        exit_date=current_date,
                        exit_price=eff_exit_price,
                        quantity=qty,
                        holding_period_days=holding_days,
                        gross_pnl=round(gross_pnl, 2),
                        net_pnl=round(net_pnl, 2),
                        gross_return_pct=round(gross_ret, 2),
                        net_return_pct=round(net_ret, 2),
                        entry_friction=pos["entry_cost_friction"],
                        exit_friction=round(exit_cost.total_friction, 2),
                        total_friction=round(pos["entry_cost_friction"] + exit_cost.total_friction, 2),
                        exit_reason=reason,
                        is_winner=net_pnl > 0,
                    )
                )
                trade_id_seq += 1

            # ─────────────────────────────────────────────────────────
            # STEP B: Check New Entries (Signals generated at prev_date Close)
            # ─────────────────────────────────────────────────────────
            if prev_date:
                candidate_entries: list[tuple[str, float]] = []
                for sym in self.config.symbols:
                    if sym in portfolio_positions:
                        continue  # Already in position
                    prev_sym = date_indexed_data.get(sym, {}).get(prev_date)
                    curr_sym = date_indexed_data.get(sym, {}).get(current_date)
                    if prev_sym and curr_sym and prev_sym["signal"] == 1.0:
                        candidate_entries.append((sym, curr_sym["open"]))

                # Respect max concurrent positions
                available_slots = max(0, self.config.max_concurrent_positions - len(portfolio_positions))
                candidates_to_enter = candidate_entries[:available_slots]

                # Position sizing calculation
                current_portfolio_equity = cash + sum(
                    p["quantity"] * date_indexed_data[s].get(current_date, {}).get("close", p["entry_price"])
                    for s, p in portfolio_positions.items()
                )

                for sym, open_p in candidates_to_enter:
                    # Apply slippage on entry (buying costs slightly more)
                    slip_factor = 1.0 + (self.config.slippage_bps / 10000.0)
                    eff_entry_price = round(open_p * slip_factor, 2)

                    if self.config.sizing_type == "PERCENT_OF_EQUITY":
                        target_capital = (current_portfolio_equity * (self.config.sizing_value / 100.0)) / max(1, self.config.max_concurrent_positions)
                        usable_cash = min(cash, target_capital)
                        qty = int(usable_cash / (eff_entry_price * 1.003))
                    elif self.config.sizing_type == "FIXED_AMOUNT":
                        target_capital = self.config.sizing_value
                        usable_cash = min(cash, target_capital)
                        qty = int(usable_cash / (eff_entry_price * 1.003))
                    else:  # FIXED_SHARES
                        desired_qty = int(self.config.sizing_value)
                        max_affordable_qty = int(cash / (eff_entry_price * 1.003))
                        qty = min(desired_qty, max_affordable_qty)

                    if qty >= 1:
                        entry_cost = calculate_indian_cost(
                            price=eff_entry_price,
                            quantity=qty,
                            side="BUY",
                            segment="DELIVERY",
                            base_slippage_bps=0.0,
                            brokerage_rate=self.config.brokerage_rate,
                            brokerage_cap=self.config.brokerage_cap,
                        )

                        required_total = (qty * eff_entry_price) + entry_cost.total_friction
                        if cash >= required_total:
                            cash -= required_total
                            portfolio_positions[sym] = {
                                "quantity": qty,
                                "entry_price": eff_entry_price,
                                "entry_date": current_date,
                                "peak_price": eff_entry_price,
                                "entry_cost_friction": round(entry_cost.total_friction, 2),
                            }
                            total_stt += entry_cost.stt
                            total_gst += entry_cost.gst
                            total_brokerage += entry_cost.brokerage
                            total_stamp_duty += entry_cost.stamp_duty
                            total_exchange_fees += entry_cost.exchange_charges
                            total_slippage += (eff_entry_price - open_p) * qty

            # ─────────────────────────────────────────────────────────
            # STEP C: End of Day Accounting & Daily NAV
            # ─────────────────────────────────────────────────────────
            # Liquid cash earns daily risk-free interest (call money / repo proxy)
            if not portfolio_positions:
                cash *= (1.0 + daily_rf)

            invested_val = 0.0
            for sym, pos in portfolio_positions.items():
                day_data = date_indexed_data[sym].get(current_date)
                close_p = day_data["close"] if day_data else pos["entry_price"]
                invested_val += pos["quantity"] * close_p

            total_equity = cash + invested_val

            daily_equity_curve.append({
                "date": current_date,
                "strategy_nav": round(total_equity, 2),
                "cash": round(cash, 2),
                "invested": round(invested_val, 2),
                "open_positions": len(portfolio_positions),
            })

        # Close any lingering positions on the final day for complete accounting
        last_date = calendar_dates[-1]
        for sym, pos in list(portfolio_positions.items()):
            last_p = date_indexed_data[sym].get(last_date, {}).get("close", pos["entry_price"])
            cost = calculate_indian_cost(price=last_p, quantity=pos["quantity"], side="SELL")
            net_proceeds = (pos["quantity"] * last_p) - cost.total_friction
            cash += net_proceeds
            net_pnl = net_proceeds - (pos["entry_price"] * pos["quantity"] + pos["entry_cost_friction"])
            holding_days = max(1, (datetime.strptime(last_date, "%Y-%m-%d") - datetime.strptime(pos["entry_date"], "%Y-%m-%d")).days)

            trades_history.append(
                TradeRecord(
                    trade_id=trade_id_seq,
                    symbol=sym,
                    entry_date=pos["entry_date"],
                    entry_price=pos["entry_price"],
                    exit_date=last_date,
                    exit_price=last_p,
                    quantity=pos["quantity"],
                    holding_period_days=holding_days,
                    gross_pnl=round((last_p - pos["entry_price"]) * pos["quantity"], 2),
                    net_pnl=round(net_pnl, 2),
                    gross_return_pct=round((last_p / pos["entry_price"] - 1.0) * 100.0, 2),
                    net_return_pct=round((net_pnl / (pos["entry_price"] * pos["quantity"] + pos["entry_cost_friction"])) * 100.0, 2),
                    entry_friction=pos["entry_cost_friction"],
                    exit_friction=round(cost.total_friction, 2),
                    total_friction=round(pos["entry_cost_friction"] + cost.total_friction, 2),
                    exit_reason="END_OF_DATA",
                    is_winner=net_pnl > 0,
                )
            )
            trade_id_seq += 1

        # ─────────────────────────────────────────────────────────
        # STEP D: Performance Analytics & Benchmark Integration
        # ─────────────────────────────────────────────────────────
        from quant_engine.india.analytics import compute_performance_analytics

        return compute_performance_analytics(
            daily_curve=daily_equity_curve,
            trades=trades_history,
            config=self.config,
            total_stt=total_stt,
            total_gst=total_gst,
            total_brokerage=total_brokerage,
            total_stamp_duty=total_stamp_duty,
            total_exchange_fees=total_exchange_fees,
            total_slippage=total_slippage,
            benchmark_df=benchmark_df,
        )
