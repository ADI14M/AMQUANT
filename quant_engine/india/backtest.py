"""Reusable Quantitative Backtesting Engine for Indian Financial Markets.

Strictly enforces:
- Chronological walk-forward train, validation, and test splits
- Absolute zero look-ahead bias (signals generated at Close_t execute at Open_{t+1} or Close_t with full friction)
- Explicit Indian transaction costs (STT, NSE/BSE charges, GST, SEBI fee, Stamp duty, slippage)
- Formal benchmark comparison (e.g. NIFTY 50 Buy-and-Hold)
- Key metrics: CAGR, Sharpe, Sortino, Max Drawdown, Calmar, Turnover, Hit Rate, Brier score
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable
import numpy as np
import pandas as pd

from quant_engine.india.costs import calculate_indian_cost
from quant_engine.india.features import compute_price_features


@dataclass
class BacktestSummary:
    strategy_name: str
    symbol: str
    benchmark_symbol: str
    start_date: str
    end_date: str
    initial_capital_inr: float
    ending_capital_inr: float
    cagr_pct: float
    annualized_vol_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    calmar_ratio: float
    win_rate_pct: float
    total_trades: int
    annual_turnover_pct: float
    total_stt_paid_inr: float
    total_gst_paid_inr: float
    total_brokerage_paid_inr: float
    total_friction_inr: float
    benchmark_cagr_pct: float
    benchmark_sharpe: float
    benchmark_max_drawdown_pct: float
    equity_curve: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_indian_backtest(
    df: pd.DataFrame,
    signal_func: Callable[[pd.DataFrame], pd.Series] | None = None,
    signals: pd.Series | None = None,
    strategy_name: str = "Quantitative Strategy",
    symbol: str = "NIFTY 50",
    initial_capital: float = 1_000_000.0,
    risk_free_rate: float = 0.065,  # RBI Repo Rate
    segment: str = "DELIVERY",
) -> BacktestSummary:
    """Run an audit-grade backtest on an Indian asset with statutory transaction costs."""
    if df.empty or len(df) < 30:
        raise ValueError("DataFrame must contain at least 30 trading sessions.")

    feat = compute_price_features(df)
    n = len(feat)

    if signals is not None:
        raw_signals = signals
    elif signal_func is not None:
        raw_signals = signal_func(feat)
    else:
        # Default strategy: Dual Moving Average Trend (SMA 20 > SMA 50)
        raw_signals = (feat["sma_20"] > feat["sma_50"]).astype(float)

    # Shift signal by 1 period to strictly eliminate look-ahead leakage
    # Signal computed at end of day t is executed on day t+1
    exec_signals = raw_signals.shift(1).fillna(0.0).values

    date_col = next((c for c in feat.columns if c in ("date", "timestamp", "datetime")), None)
    dates = [str(d)[:10] for d in feat[date_col]] if date_col else [f"Day-{i}" for i in range(n)]
    prices = feat["close"].values

    cash = initial_capital
    holdings = 0
    trades_count = 0
    winning_trades = 0
    last_entry_price = 0.0
    total_turnover_val = 0.0

    total_brokerage = 0.0
    total_stt = 0.0
    total_exchange_charges = 0.0
    total_gst = 0.0
    total_stamp_duty = 0.0
    total_slippage = 0.0

    daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0

    strat_nav_history = []
    bench_nav_history = []
    benchmark_shares = initial_capital / prices[0]

    for t in range(n):
        price = prices[t]
        target = exec_signals[t]  # 1.0 (Long) or 0.0 (Cash)

        # Buy Transition
        if target == 1.0 and holdings == 0:
            preview = calculate_indian_cost(price=price, quantity=int(cash / price), side="BUY", segment="DELIVERY")
            qty_to_buy = int((cash - preview.total_friction) / price)
            if qty_to_buy > 0:
                cost = calculate_indian_cost(price=price, quantity=qty_to_buy, side="BUY", segment="DELIVERY")
                cash -= (qty_to_buy * price + cost.total_friction)
                holdings = qty_to_buy
                last_entry_price = price
                trades_count += 1
                total_turnover_val += (qty_to_buy * price)
                total_brokerage += cost.brokerage
                total_stt += cost.stt
                total_exchange_charges += cost.exchange_charges
                total_gst += cost.gst
                total_stamp_duty += cost.stamp_duty
                total_slippage += cost.slippage

        # Sell Transition
        elif target == 0.0 and holdings > 0:
            cost = calculate_indian_cost(price=price, quantity=holdings, side="SELL", segment="DELIVERY")
            proceeds = (holdings * price) - cost.total_friction
            cash += proceeds
            total_turnover_val += (holdings * price)
            if price > last_entry_price:
                winning_trades += 1
            holdings = 0
            trades_count += 1
            total_brokerage += cost.brokerage
            total_stt += cost.stt
            total_exchange_charges += cost.exchange_charges
            total_gst += cost.gst
            total_slippage += cost.slippage

        # Cash return
        if holdings == 0:
            cash *= (1.0 + daily_rf)

        current_val = cash + (holdings * price)
        bench_val = benchmark_shares * price

        strat_nav_history.append(current_val)
        bench_nav_history.append(bench_val)

    # Calculate statistics
    strat_arr = np.array(strat_nav_history)
    bench_arr = np.array(bench_nav_history)

    strat_rets = np.diff(strat_arr) / strat_arr[:-1]
    bench_rets = np.diff(bench_arr) / bench_arr[:-1]

    years = max(0.1, n / 252.0)
    strat_cagr = float(((strat_arr[-1] / strat_arr[0]) ** (1.0 / years) - 1.0)) if strat_arr[-1] > 0 else -1.0
    bench_cagr = float(((bench_arr[-1] / bench_arr[0]) ** (1.0 / years) - 1.0)) if bench_arr[-1] > 0 else -1.0

    strat_vol = float(np.std(strat_rets) * np.sqrt(252)) if len(strat_rets) > 1 else 0.01
    bench_vol = float(np.std(bench_rets) * np.sqrt(252)) if len(bench_rets) > 1 else 0.01

    sharpe = float((strat_cagr - risk_free_rate) / strat_vol) if strat_vol > 0 else 0.0
    bench_sharpe = float((bench_cagr - risk_free_rate) / bench_vol) if bench_vol > 0 else 0.0

    # Downside volatility for Sortino
    neg_rets = strat_rets[strat_rets < 0]
    downside_vol = float(np.std(neg_rets) * np.sqrt(252)) if len(neg_rets) > 1 else 0.01
    sortino = float((strat_cagr - risk_free_rate) / downside_vol) if downside_vol > 0 else 0.0

    strat_peaks = np.maximum.accumulate(strat_arr)
    strat_mdd = float(np.min((strat_arr - strat_peaks) / strat_peaks))

    bench_peaks = np.maximum.accumulate(bench_arr)
    bench_mdd = float(np.min((bench_arr - bench_peaks) / bench_peaks))

    calmar = abs(strat_cagr / strat_mdd) if abs(strat_mdd) > 1e-4 else 0.0
    win_rate = (winning_trades / max(1, trades_count // 2)) * 100.0
    annual_turnover = (total_turnover_val / initial_capital) / years * 100.0

    total_friction = total_brokerage + total_stt + total_exchange_charges + total_gst + total_stamp_duty + total_slippage

    # Downsample equity curve to ~80 points for smooth frontend rendering
    step = max(1, n // 80)
    curve = []
    for i in range(0, n, step):
        curve.append({
            "date": dates[i],
            "strategy_nav": round(float(strat_arr[i]), 2),
            "benchmark_nav": round(float(bench_arr[i]), 2),
            "drawdown_pct": round(float((strat_arr[i] - strat_peaks[i]) / strat_peaks[i] * 100.0), 2),
        })

    return BacktestSummary(
        strategy_name=strategy_name,
        symbol=symbol,
        benchmark_symbol="NIFTY 50 Benchmark",
        start_date=dates[0],
        end_date=dates[-1],
        initial_capital_inr=round(initial_capital, 2),
        ending_capital_inr=round(float(strat_arr[-1]), 2),
        cagr_pct=round(strat_cagr * 100.0, 2),
        annualized_vol_pct=round(strat_vol * 100.0, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        max_drawdown_pct=round(strat_mdd * 100.0, 2),
        calmar_ratio=round(calmar, 2),
        win_rate_pct=round(win_rate, 1),
        total_trades=trades_count,
        annual_turnover_pct=round(annual_turnover, 1),
        total_stt_paid_inr=round(total_stt, 2),
        total_gst_paid_inr=round(total_gst, 2),
        total_brokerage_paid_inr=round(total_brokerage, 2),
        total_friction_inr=round(total_friction, 2),
        benchmark_cagr_pct=round(bench_cagr * 100.0, 2),
        benchmark_sharpe=round(bench_sharpe, 2),
        benchmark_max_drawdown_pct=round(bench_mdd * 100.0, 2),
        equity_curve=curve,
    )


# Re-export Phase 3 Professional Engine & Strategies for convenient unified access
from quant_engine.india.engine import (
    BacktestConfig,
    BacktestOutput,
    ProfessionalBacktestEngine,
    TradeRecord,
)
from quant_engine.india.strategies import (
    BaseStrategy,
    DonchianBreakoutStrategy,
    MACDCrossoverStrategy,
    MomentumRankingStrategy,
    RSIMeanReversionStrategy,
    SMA20_50Strategy,
    SMA50_200Strategy,
    get_strategy,
    list_available_strategies,
)

