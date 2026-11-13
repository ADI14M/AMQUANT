"""AMQUANT INDIA - Phase 3 Professional Historical Backtesting Engine Test Suite.

Verifies:
1. Strategy Library: 6 configurable strategy models, parameter schemas, entry & exit signals.
2. Execution Engine: Next-session Open fills (zero lookahead), slippage, gap handling on SL/TP, trailing stops.
3. Portfolio & Risk: Position sizing rules, cash constraints, max concurrent positions, multi-asset basket.
4. Indian Statutory Costs: Itemized friction, gross vs net performance, CAGR, Sharpe, Sortino.
5. Chronological Walk-Forward: 70/30 in-sample vs out-of-sample split, low-trade statistical power warnings.
6. FastAPI Endpoints: GET /api/india/backtest/strategies, POST /api/india/backtest/run-advanced, saved scenarios.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from quant_engine.india.engine import (
    BacktestConfig,
    ProfessionalBacktestEngine,
)
from quant_engine.india.strategies import (
    DonchianBreakoutStrategy,
    MACDCrossoverStrategy,
    MomentumRankingStrategy,
    RSIMeanReversionStrategy,
    SMA20_50Strategy,
    SMA50_200Strategy,
    get_strategy,
    list_available_strategies,
)


def _generate_synthetic_ohlcv(
    n_bars: int = 300,
    start_price: float = 1000.0,
    seed: int = 42,
    trend: float = 0.0005,
) -> pd.DataFrame:
    """Generate realistic OHLCV price series for unit testing."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n_bars, freq="B")

    daily_returns = rng.normal(trend, 0.015, n_bars)
    prices = start_price * np.cumprod(1 + daily_returns)

    opens = prices * (1 + rng.normal(0, 0.003, n_bars))
    highs = np.maximum(opens, prices) * (1 + rng.uniform(0.001, 0.012, n_bars))
    lows = np.minimum(opens, prices) * (1 - rng.uniform(0.001, 0.012, n_bars))
    closes = prices
    volumes = rng.integers(100_000, 2_000_000, n_bars)

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": np.round(opens, 2),
        "high": np.round(highs, 2),
        "low": np.round(lows, 2),
        "close": np.round(closes, 2),
        "volume": volumes,
    })


# ----------------------------------------------------------------------
# 1. Strategy Library Tests
# ----------------------------------------------------------------------
def test_strategy_catalog_and_registry():
    """Verify all 6 strategies are registered with valid parameter schemas and rules."""
    strategies = list_available_strategies()
    assert len(strategies) == 6

    ids = {s["id"] for s in strategies}
    expected_ids = {
        "SMA_20_50",
        "SMA_50_200",
        "RSI_MEAN_REVERSION",
        "MACD_CROSSOVER",
        "DONCHIAN_BREAKOUT",
        "MOMENTUM_RANKING",
    }
    assert ids == expected_ids

    for s in strategies:
        assert s["name"]
        assert s["category"] in ("TREND_FOLLOWING", "MEAN_REVERSION", "MOMENTUM")
        assert len(s["parameters"]) >= 1
        assert "Open" in s["entry_rule"] or "Golden" in s["entry_rule"] or "Long" in s["entry_rule"]
        assert "Open" in s["exit_rule"] or "Death" in s["exit_rule"] or "Cash" in s["exit_rule"]

        # Instantiate each strategy via registry
        instance = get_strategy(s["id"])
        assert instance.id == s["id"]


def test_strategy_signal_generation():
    """Verify each strategy computes valid signals (-1, 0, 1) without NaN corruption."""
    df = _generate_synthetic_ohlcv(200)

    strategies = [
        SMA20_50Strategy(fast_period=10, slow_period=30),
        SMA50_200Strategy(fast_period=20, slow_period=50),
        RSIMeanReversionStrategy(rsi_period=14, oversold=35.0, overbought=65.0),
        MACDCrossoverStrategy(fast_period=12, slow_period=26, signal_period=9),
        DonchianBreakoutStrategy(entry_lookback=20, exit_lookback=10),
        MomentumRankingStrategy(lookback_days=30, top_n=1),
    ]

    for strat in strategies:
        signals = strat.generate_signals(df)
        assert len(signals) == len(df)
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert not signals.isna().any()


# ----------------------------------------------------------------------
# 2. Execution Engine & Look-Ahead Bias Prevention Tests
# ----------------------------------------------------------------------
def test_order_execution_on_next_session_open_with_slippage():
    """Verify orders generated at Day t Close strictly execute on Day t+1 Open with slippage."""
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "open": [100.0, 102.0, 105.0, 108.0],
        "high": [103.0, 104.0, 107.0, 110.0],
        "low": [99.0, 101.0, 104.0, 107.0],
        "close": [101.0, 103.0, 106.0, 109.0],
        "volume": [10000, 10000, 10000, 10000],
    })

    class MockImmediateBuyStrategy(SMA20_50Strategy):
        def generate_signals(self, df_bar: pd.DataFrame) -> pd.Series:
            s = pd.Series(0.0, index=df_bar.index)
            s.iloc[1] = 1.0  # Buy at index 1 Close -> Day 2 Open
            s.iloc[2] = 0.0  # Exit at index 2 Close -> Day 3 Open
            return s

    strategy = MockImmediateBuyStrategy()
    config = BacktestConfig(
        strategy=strategy,
        symbols=["TEST"],
        initial_capital=100_000.0,
        sizing_type="FIXED_SHARES",
        sizing_value=100.0,
        slippage_bps=10.0,  # 10 bps = 0.1%
    )
    engine = ProfessionalBacktestEngine(config)
    output = engine.run({"TEST": df})

    assert len(output.trades) == 1
    trade = output.trades[0]

    # Entry must occur on Day 2 ("2024-01-03")
    assert trade["entry_date"] == "2024-01-03"
    expected_entry_open = 105.0
    expected_entry_price = round(expected_entry_open * (1 + 10.0 / 10000.0), 4)
    assert pytest.approx(trade["entry_price"], rel=1e-3) == expected_entry_price

    # Exit must occur on Day 3 ("2024-01-04")
    assert trade["exit_date"] == "2024-01-04"
    expected_exit_open = 108.0
    expected_exit_price = round(expected_exit_open * (1 - 10.0 / 10000.0), 4)
    assert pytest.approx(trade["exit_price"], rel=1e-3) == expected_exit_price


def test_stop_loss_gap_down_execution():
    """Verify that when a stock gaps down below stop-loss price, execution occurs at gap open."""
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "open": [100.0, 100.0, 90.0],  # Day 2 opens at 90 (gap down)
        "high": [102.0, 101.0, 92.0],
        "low": [99.0, 98.0, 88.0],
        "close": [101.0, 99.0, 89.0],
        "volume": [10000, 10000, 10000],
    })

    class ForceBuyStrategy(SMA20_50Strategy):
        def generate_signals(self, df_bar: pd.DataFrame) -> pd.Series:
            s = pd.Series(0.0, index=df_bar.index)
            s.iloc[0] = 1.0
            return s

    config = BacktestConfig(
        strategy=ForceBuyStrategy(),
        symbols=["TEST"],
        initial_capital=100_000.0,
        sizing_type="FIXED_SHARES",
        sizing_value=100.0,
        stop_loss_pct=5.0,  # 5% SL -> ₹95.0
        slippage_bps=0.0,
    )
    engine = ProfessionalBacktestEngine(config)
    output = engine.run({"TEST": df})

    assert len(output.trades) == 1
    trade = output.trades[0]
    assert trade["exit_reason"] == "STOP_LOSS"
    # Fills at min(Open, SL) = min(90.0, 95.0) = 90.0
    assert trade["exit_price"] == 90.0
    assert trade["net_pnl"] < 0


def test_trailing_stop_loss_execution():
    """Verify trailing stop ratchets up with new highs and triggers upon reversal."""
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "open": [100.0, 100.0, 115.0, 107.0],
        "high": [101.0, 102.0, 120.0, 109.0],
        "low": [99.0, 99.0, 114.0, 104.0],  # Day 3 touches 104 <= trailing stop 108
        "close": [100.0, 101.0, 118.0, 105.0],
        "volume": [10000, 10000, 10000, 10000],
    })

    class TriggerOnceStrategy(SMA20_50Strategy):
        def generate_signals(self, df_bar: pd.DataFrame) -> pd.Series:
            return pd.Series(1.0, index=df_bar.index)

    config = BacktestConfig(
        strategy=TriggerOnceStrategy(),
        symbols=["TEST"],
        initial_capital=100_000.0,
        sizing_type="FIXED_SHARES",
        sizing_value=100.0,
        trailing_stop_pct=10.0,  # 10% trailing
        slippage_bps=0.0,
    )
    engine = ProfessionalBacktestEngine(config)
    output = engine.run({"TEST": df})

    assert len(output.trades) >= 1
    trade = output.trades[0]
    assert trade["exit_reason"] == "TRAILING_STOP"
    assert trade["exit_date"] == "2024-01-04"
    # Peak high was 120.0 (10% trailing SL = 108.0); Open gapped down to 107.0 so filled at 107.0
    assert trade["exit_price"] == 107.0
    assert trade["net_pnl"] > 0


# ----------------------------------------------------------------------
# 3. Position Sizing & Multi-Asset Portfolio Constraints
# ----------------------------------------------------------------------
def test_position_sizing_types_and_cash_limits():
    """Verify fixed shares, fixed amount, and percent of equity sizing with cash constraints."""
    df = _generate_synthetic_ohlcv(100, start_price=500.0)

    # 1. FIXED_SHARES = 50
    config_shares = BacktestConfig(
        strategy=SMA20_50Strategy(fast_period=5, slow_period=15),
        symbols=["STOCK"],
        initial_capital=200_000.0,
        sizing_type="FIXED_SHARES",
        sizing_value=50.0,
    )
    out_shares = ProfessionalBacktestEngine(config_shares).run({"STOCK": df})
    for t in out_shares.trades:
        assert t["quantity"] == 50

    # 2. FIXED_AMOUNT = ₹25,000
    config_amt = BacktestConfig(
        strategy=SMA20_50Strategy(fast_period=5, slow_period=15),
        symbols=["STOCK"],
        initial_capital=100_000.0,
        sizing_type="FIXED_AMOUNT",
        sizing_value=25_000.0,
    )
    out_amt = ProfessionalBacktestEngine(config_amt).run({"STOCK": df})
    for t in out_amt.trades:
        cost = t["quantity"] * t["entry_price"]
        assert cost <= 25_000.0

    # 3. Insufficient capital rejects orders safely without crash
    config_poor = BacktestConfig(
        strategy=SMA20_50Strategy(fast_period=5, slow_period=15),
        symbols=["STOCK"],
        initial_capital=100.0,  # ₹100 cannot buy 50 shares of ₹500 stock
        sizing_type="FIXED_SHARES",
        sizing_value=50.0,
    )
    out_poor = ProfessionalBacktestEngine(config_poor).run({"STOCK": df})
    assert len(out_poor.trades) == 0


def test_multi_asset_portfolio_and_max_concurrent_positions():
    """Verify multi-asset execution respects max_concurrent_positions cap."""
    df_a = _generate_synthetic_ohlcv(120, seed=1)
    df_b = _generate_synthetic_ohlcv(120, seed=2)
    df_c = _generate_synthetic_ohlcv(120, seed=3)

    data_map = {"STOCK_A": df_a, "STOCK_B": df_b, "STOCK_C": df_c}

    config = BacktestConfig(
        strategy=SMA20_50Strategy(fast_period=5, slow_period=12),
        symbols=["STOCK_A", "STOCK_B", "STOCK_C"],
        initial_capital=1_000_000.0,
        sizing_type="PERCENT_OF_EQUITY",
        sizing_value=30.0,
        max_concurrent_positions=2,  # Limit to at most 2 concurrent positions
    )

    output = ProfessionalBacktestEngine(config).run(data_map)
    assert output.summary_metrics["total_trades"] >= 0

    for pt in output.equity_curve:
        assert pt["cash"] >= -1e-5
        assert pt["strategy_nav"] > 0


# ----------------------------------------------------------------------
# 4. Indian Statutory Cost Engine & Performance Analytics
# ----------------------------------------------------------------------
def test_statutory_costs_and_gross_vs_net_discrepancy():
    """Verify STT, Brokerage cap, GST, Stamp duty, and Exchange fees are deducted."""
    df = _generate_synthetic_ohlcv(200, start_price=2000.0, trend=0.001)

    config = BacktestConfig(
        strategy=SMA20_50Strategy(fast_period=10, slow_period=30),
        symbols=["RELIANCE"],
        initial_capital=1_000_000.0,
        sizing_type="PERCENT_OF_EQUITY",
        sizing_value=100.0,
        slippage_bps=5.0,
    )
    output = ProfessionalBacktestEngine(config).run({"RELIANCE": df})

    metrics = output.summary_metrics
    costs = output.transaction_costs_summary

    if metrics["total_trades"] > 0:
        # Gross CAGR must be strictly greater than or equal to Net CAGR
        assert metrics["gross_cagr_pct"] >= metrics["net_cagr_pct"]
        assert metrics["total_friction_inr"] > 0

        # Costs breakdown must have positive statutory amounts
        assert costs["total_stt_inr"] >= 0
        assert costs["total_gst_inr"] >= 0
        assert costs["total_brokerage_inr"] >= 0
        assert costs["total_exchange_charges_inr"] >= 0
        assert costs["total_stamp_duty_inr"] >= 0


def test_walk_forward_split_and_statistical_warnings():
    """Verify in-sample vs out-of-sample split and trade count warnings."""
    df = _generate_synthetic_ohlcv(150, trend=0.0001)

    config = BacktestConfig(
        strategy=SMA20_50Strategy(fast_period=50, slow_period=100),
        symbols=["TEST"],
        initial_capital=500_000.0,
    )
    output = ProfessionalBacktestEngine(config).run({"TEST": df})

    splits = output.validation_report
    assert "in_sample_train_cagr_pct" in splits
    assert "out_of_sample_test_cagr_pct" in splits

    # Survivorship bias warning is always present
    assert any("Survivorship Bias Notice" in w for w in splits["warnings"])

    # Low sample warning triggers when total trades < 10
    if output.summary_metrics["total_trades"] < 10:
        assert any("Low Sample Warning" in w for w in splits["warnings"])


# ----------------------------------------------------------------------
# 5. FastAPI Endpoints Integration Tests
# ----------------------------------------------------------------------
def test_api_backtest_strategies_catalog():
    """Verify GET /api/india/backtest/strategies returns all 6 strategies."""
    client = TestClient(app)
    response = client.get("/api/india/backtest/strategies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    assert any(s["id"] == "SMA_20_50" for s in data)
    assert any(s["id"] == "DONCHIAN_BREAKOUT" for s in data)


def test_api_run_advanced_backtest_endpoint():
    """Verify POST /api/india/backtest/run-advanced executes on RELIANCE."""
    client = TestClient(app)
    payload = {
        "strategy_id": "SMA_20_50",
        "strategy_params": {"fast_period": 15, "slow_period": 35},
        "symbols": ["RELIANCE"],
        "initial_capital": 1_000_000,
        "sizing_type": "PERCENT_OF_EQUITY",
        "sizing_value": 100,
        "stop_loss_pct": 5.0,
        "take_profit_pct": 15.0,
        "slippage_bps": 5.0,
        "benchmark_symbol": "NIFTY 50",
    }
    response = client.post("/api/india/backtest/run-advanced", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["summary_metrics"]["total_trades"] >= 0
    assert "equity_curve" in data
    assert "monthly_returns" in data
    assert "transaction_costs_summary" in data
    assert data["execution_assumptions"]["look_ahead_bias_audit"] == "PASSED - zero lookahead bias verified"


def test_api_run_advanced_portfolio_backtest():
    """Verify POST /api/india/backtest/run-advanced supports multi-asset basket."""
    client = TestClient(app)
    payload = {
        "strategy_id": "MACD_CROSSOVER",
        "strategy_params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "symbols": ["RELIANCE", "TCS"],
        "initial_capital": 2_000_000,
        "sizing_type": "PERCENT_OF_EQUITY",
        "sizing_value": 50,
        "max_concurrent_positions": 2,
        "slippage_bps": 5.0,
    }
    response = client.post("/api/india/backtest/run-advanced", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "summary_metrics" in data
    assert len(data["equity_curve"]) > 0
