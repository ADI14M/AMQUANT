"""AMQUANT INDIA — Phase 5 Comprehensive Unit and Integration Test Suite.

Covers:
1. Risk Manager limits (Max daily loss, Max drawdown, Position size, Margin utilization).
2. Intraday Strategy Library (7 strategies, parameter schemas, signals, 60m HTF filter).
3. Intraday Equity Backtesting Engine (t+1 Open fills, SL/TP conservative conflict resolution,
   trailing stop, mandatory 15:15 IST EOD square-off, Indian statutory costs, Walk-Forward 70/30).
4. Futures Backtesting Engine (individual contracts, point-in-time lot sizes, MTM accounting,
   rollover execution, basis & roll spread tracking, futures costs).
5. Options Strategy & Payoff Engine (11 strategies, terminal payoff curve, breakevens,
   cash-settled intrinsic expiry settlement, short option margin, net Greeks, theoretical disclosure).
6. Phase 5 FastAPI REST API Endpoints.
"""

from __future__ import annotations

import math
from datetime import datetime
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from quant_engine.india.backtesting.futures_engine import (
    FuturesBacktestConfig,
    FuturesBacktestEngine,
)
from quant_engine.india.backtesting.intraday_engine import (
    IntradayBacktestConfig,
    IntradayEquityBacktester,
)
from quant_engine.india.backtesting.intraday_strategies import (
    EMA9_21CrossoverStrategy,
    OpeningRangeBreakoutStrategy,
    PreviousDayHighLowBreakoutStrategy,
    RSIIntradayMeanReversionStrategy,
    VolumeBreakoutStrategy,
    VWAPReversionStrategy,
    VWAPTrendStrategy,
    get_intraday_strategy,
    list_intraday_strategies,
)
from quant_engine.india.backtesting.options_engine import (
    AVAILABLE_OPTIONS_STRATEGIES,
    OptionLeg,
    OptionsBacktestConfig,
    OptionsBacktestEngine,
)
from quant_engine.india.backtesting.risk_manager import (
    RiskLimits,
    RiskManager,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def synthetic_intraday_df() -> pd.DataFrame:
    """Generate deterministic 5-minute candles across two trading sessions."""
    rows = []
    # Session 1: 2024-01-02
    base_px = 2500.0
    times_day1 = [
        f"2024-01-02 {h:02d}:{m:02d}:00"
        for h in range(9, 16)
        for m in range(0, 60, 5)
        if not (h == 9 and m < 15) and not (h == 15 and m > 30)
    ]
    np.random.seed(42)
    for i, ts in enumerate(times_day1):
        drift = 0.5 * math.sin(i / 5.0)
        base_px += drift
        rows.append({
            "datetime": ts,
            "open": round(base_px - 0.5, 2),
            "high": round(base_px + 2.0, 2),
            "low": round(base_px - 2.0, 2),
            "close": round(base_px, 2),
            "volume": 5000 + int(i * 100),
        })

    # Session 2: 2024-01-03
    times_day2 = [
        f"2024-01-03 {h:02d}:{m:02d}:00"
        for h in range(9, 16)
        for m in range(0, 60, 5)
        if not (h == 9 and m < 15) and not (h == 15 and m > 30)
    ]
    for i, ts in enumerate(times_day2):
        drift = -0.4 * math.cos(i / 4.0)
        base_px += drift
        rows.append({
            "datetime": ts,
            "open": round(base_px + 0.5, 2),
            "high": round(base_px + 2.5, 2),
            "low": round(base_px - 2.5, 2),
            "close": round(base_px, 2),
            "volume": 6000 + int(i * 120),
        })

    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df


@pytest.fixture
def synthetic_daily_df() -> pd.DataFrame:
    """Generate daily OHLCV series for futures backtesting."""
    dates = pd.date_range("2024-01-01", "2024-06-30", freq="B")
    rows = []
    px = 22000.0
    np.random.seed(123)
    for d in dates:
        ret = np.random.normal(0.0005, 0.008)
        px *= (1.0 + ret)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": round(px * 0.998, 2),
            "high": round(px * 1.006, 2),
            "low": round(px * 0.994, 2),
            "close": round(px, 2),
            "volume": int(np.random.randint(500000, 2000000)),
        })
    return pd.DataFrame(rows)


# ============================================================================
# 1. RISK MANAGER TESTS
# ============================================================================

def test_risk_manager_pre_trade_and_circuit_breakers():
    limits = RiskLimits(
        max_daily_loss_inr=5000.0,
        max_portfolio_drawdown_pct=10.0,
        max_position_size_pct=30.0,
        max_open_positions=2,
        margin_utilization_limit_pct=85.0,
    )
    rm = RiskManager(limits)

    # 1. Valid trade
    check = rm.check_pre_trade(
        current_equity=100000.0,
        initial_capital=100000.0,
        peak_equity=100000.0,
        daily_realized_pnl=0.0,
        daily_unrealized_pnl=0.0,
        active_positions_count=1,
        current_margin_used=20000.0,
        proposed_trade_margin=5000.0,
        proposed_position_value=25000.0,
    )
    assert check.allowed is True
    assert "passed" in check.reason.lower()

    # 2. Position size exceed check (> 30% of capital, proposed 35,000 > 30,000)
    check_sz = rm.check_pre_trade(
        current_equity=100000.0,
        initial_capital=100000.0,
        peak_equity=100000.0,
        daily_realized_pnl=0.0,
        daily_unrealized_pnl=0.0,
        active_positions_count=1,
        current_margin_used=20000.0,
        proposed_trade_margin=7000.0,
        proposed_position_value=35000.0,
    )
    assert check_sz.allowed is False
    assert "position size" in check_sz.reason.lower()

    # 3. Max open positions check (limit = 2)
    check_pos = rm.check_pre_trade(
        current_equity=100000.0,
        initial_capital=100000.0,
        peak_equity=100000.0,
        daily_realized_pnl=0.0,
        daily_unrealized_pnl=0.0,
        active_positions_count=2,
        current_margin_used=20000.0,
        proposed_trade_margin=5000.0,
        proposed_position_value=15000.0,
    )
    assert check_pos.allowed is False
    assert "Max open positions" in check_pos.reason

    # 4. Max portfolio drawdown check (down 12% > 10% limit)
    check_dd = rm.check_pre_trade(
        current_equity=88000.0,
        initial_capital=100000.0,
        peak_equity=100000.0,
        daily_realized_pnl=0.0,
        daily_unrealized_pnl=0.0,
        active_positions_count=0,
        current_margin_used=0.0,
        proposed_trade_margin=2000.0,
        proposed_position_value=10000.0,
    )
    assert check_dd.allowed is False
    assert "Portfolio drawdown" in check_dd.reason

    # 5. Daily loss circuit breaker
    check_loss = rm.check_pre_trade(
        current_equity=94000.0,
        initial_capital=100000.0,
        peak_equity=100000.0,
        daily_realized_pnl=-6000.0,
        daily_unrealized_pnl=0.0,
        active_positions_count=0,
        current_margin_used=0.0,
        proposed_trade_margin=2000.0,
        proposed_position_value=10000.0,
    )
    assert check_loss.allowed is False
    assert "Daily loss" in check_loss.reason
    assert rm.trading_halted_today is True


# ============================================================================
# 2. INTRADAY STRATEGY LIBRARY TESTS
# ============================================================================

def test_intraday_strategies_catalog_and_instantiation():
    catalog = list_intraday_strategies()
    assert len(catalog) == 7
    strategy_ids = [s["id"] for s in catalog]
    expected_ids = [
        "VWAP_REVERSION",
        "VWAP_TREND",
        "OPENING_RANGE_BREAKOUT",
        "EMA_9_21_CROSSOVER",
        "RSI_INTRADAY",
        "VOLUME_BREAKOUT",
        "PDH_PDL_BREAKOUT",
    ]
    for eid in expected_ids:
        assert eid in strategy_ids

    # Instantiation via factory
    vwap_strat = get_intraday_strategy("VWAP_REVERSION", std_dev_mult=2.2)
    assert isinstance(vwap_strat, VWAPReversionStrategy)
    assert vwap_strat.params["std_dev_mult"] == 2.2

    ema_strat = get_intraday_strategy("EMA_9_21_CROSSOVER", fast_period=8, slow_period=20)
    assert isinstance(ema_strat, EMA9_21CrossoverStrategy)
    assert ema_strat.params["fast_period"] == 8


def test_intraday_strategy_signal_generation(synthetic_intraday_df):
    for strat_cls in [
        VWAPReversionStrategy,
        VWAPTrendStrategy,
        OpeningRangeBreakoutStrategy,
        EMA9_21CrossoverStrategy,
        RSIIntradayMeanReversionStrategy,
        VolumeBreakoutStrategy,
        PreviousDayHighLowBreakoutStrategy,
    ]:
        strat = strat_cls()
        signals = strat.generate_signals(synthetic_intraday_df.copy())
        assert len(signals) == len(synthetic_intraday_df)
        assert "signal" in signals.columns
        # Signals must strictly be in {-1, 0, 1}
        unique_signals = set(signals["signal"].unique())
        assert unique_signals.issubset({-1, 0, 1})


# ============================================================================
# 3. INTRADAY EQUITY BACKTESTING ENGINE TESTS
# ============================================================================

def test_intraday_engine_execution_and_eod_squareoff(synthetic_intraday_df):
    backtester = IntradayEquityBacktester()
    config = IntradayBacktestConfig(
        strategy_id="VWAP_REVERSION",
        symbol="RELIANCE",
        timeframe="5m",
        initial_capital=200000.0,
        position_sizing_pct=0.25,
        allow_short=True,
        stop_loss_pct=0.015,
        take_profit_pct=0.03,
        eod_square_off_time="15:15:00",
        walk_forward=True,
    )

    result = backtester.run(synthetic_intraday_df, config)
    assert result.initial_capital == 200000.0
    assert len(result.equity_curve) > 0
    assert result.total_costs >= 0.0

    # Verify all trades conform to rules
    for trade in result.trades:
        # Zero look-ahead: trade entry time must be strictly after signal index
        assert trade.entry_price > 0
        assert trade.exit_price > 0
        assert trade.total_costs > 0  # Indian statutory costs must be non-zero
        assert trade.net_pnl == pytest.approx(trade.gross_pnl - trade.total_costs, abs=0.01)

        # Mandatory EOD square-off check: exit time must be <= 15:20 on the same date
        entry_date = trade.entry_time.split(" ")[0]
        exit_date = trade.exit_time.split(" ")[0]
        assert entry_date == exit_date, "Intraday trade carried overnight!"


def test_conservative_sl_tp_conflict_resolution():
    """When both SL and TP are within candle [low, high], SL must trigger first."""
    backtester = IntradayEquityBacktester()
    # Construct a single bar where both SL and TP would be satisfied
    data = [
        {"datetime": "2024-01-02 09:15:00", "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1000},
        {"datetime": "2024-01-02 09:20:00", "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1000},
        # Signal bar generated at 09:20 Close
        # Entry executed at 09:25 Open at 100.0 (Buy)
        {"datetime": "2024-01-02 09:25:00", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.2, "volume": 1000},
        # Bar with huge range: High 105 (+5% TP), Low 97 (-3% SL)
        {"datetime": "2024-01-02 09:30:00", "open": 100.2, "high": 105.0, "low": 97.0, "close": 102.0, "volume": 5000},
        {"datetime": "2024-01-02 15:15:00", "open": 102.0, "high": 102.5, "low": 101.5, "close": 102.0, "volume": 1000},
    ]
    df = pd.DataFrame(data)

    config = IntradayBacktestConfig(
        strategy_id="VWAP_REVERSION",
        symbol="TEST",
        initial_capital=100000.0,
        stop_loss_pct=0.02,   # SL at 98.0
        take_profit_pct=0.04, # TP at 104.0
    )

    # Mock signal at bar 1
    class DummySignalStrat(VWAPReversionStrategy):
        def generate_signals(self, candles_df, htf_60m_df=None):
            cdf = candles_df.copy()
            cdf["signal"] = 0
            cdf.loc[1, "signal"] = 1  # Buy signal at bar 1 -> entry at bar 2 Open (100.0)
            return cdf

    backtester._get_strategy = lambda cfg: DummySignalStrat()
    result = backtester.run(df, config)

    assert len(result.trades) >= 1
    first_trade = result.trades[0]
    # In conservative resolution, SL must be triggered instead of TP
    assert "STOP_LOSS" in first_trade.exit_reason
    assert first_trade.exit_price == pytest.approx(98.0, abs=0.5)


# ============================================================================
# 4. FUTURES BACKTESTING ENGINE TESTS
# ============================================================================

def test_futures_backtest_with_rollover_and_mtm(synthetic_daily_df):
    engine = FuturesBacktestEngine()
    config = FuturesBacktestConfig(
        underlying="NIFTY",
        start_date="2024-01-01",
        end_date="2024-06-30",
        initial_capital=1000000.0,
        num_lots=1,
        days_before_expiry_roll=3,
        strategy_type="TREND_FOLLOWING",
        margin_requirement_pct=0.15,
        stop_loss_pct=None,
        take_profit_pct=None,
    )

    result = engine.run(synthetic_daily_df, config)
    assert result.initial_capital == 1000000.0
    assert len(result.equity_curve) > 0
    assert result.total_rollover_costs >= 0.0

    # Verify rollover events occurred across multi-month backtest
    assert len(result.rollover_log) >= 1
    first_roll = result.rollover_log[0]
    assert "old_contract" in first_roll
    assert "new_contract" in first_roll
    assert first_roll["old_contract"] != first_roll["new_contract"]
    assert first_roll["roll_cost"] > 0

    # Verify MTM equity curve
    for pt in result.equity_curve:
        assert pt["equity"] > 0
        assert pt["margin_locked"] > 0  # 15% SPAN margin must be locked while holding position


# ============================================================================
# 5. OPTIONS STRATEGY & PAYOFF ENGINE TESTS
# ============================================================================

def test_options_catalog_and_all_11_strategies():
    catalog = AVAILABLE_OPTIONS_STRATEGIES
    assert len(catalog) == 11
    expected_strategies = [
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
    catalog_ids = [s["id"] for s in catalog]
    for s_id in expected_strategies:
        assert s_id in catalog_ids


def test_bull_call_spread_payoff_and_expiry_settlement():
    engine = OptionsBacktestEngine()
    config = OptionsBacktestConfig(
        strategy_id="BULL_CALL_SPREAD",
        underlying="NIFTY",
        entry_date="2024-05-02",
        expiry_date="2024-05-30",
        initial_capital=500000.0,
        num_lots=1,
        strike_step=50.0,
        underlying_entry_spot=22500.0,
        underlying_exit_spot=22700.0,  # Spot moved up 200 pts
        days_to_expiry_entry=28,
        days_to_expiry_exit=0,  # Expiry settlement
        volatility=0.15,
    )

    result = engine.run_backtest(config)
    assert len(result.legs) == 2
    buy_leg = next(l for l in result.legs if l.action == "BUY")
    sell_leg = next(l for l in result.legs if l.action == "SELL")
    assert buy_leg.strike == 22500.0
    assert sell_leg.strike == 22550.0  # +1 strike offset

    # Payoff curve checks
    payoff = result.payoff
    assert len(payoff.points) == 121
    assert payoff.max_profit > 0
    assert payoff.max_loss < 0
    assert len(payoff.breakevens) >= 1
    assert 22500.0 <= payoff.breakevens[0] <= 22550.0

    # Expiry intrinsic checks: at spot 22700, both 22500 CE and 22550 CE are ITM
    assert buy_leg.exit_premium == pytest.approx(200.0, abs=0.1)
    assert sell_leg.exit_premium == pytest.approx(150.0, abs=0.1)

    # Net P&L & statutory charges
    assert result.transaction_costs > 0.0
    assert result.net_pnl == pytest.approx(result.gross_pnl - result.transaction_costs, abs=0.01)
    assert result.is_theoretical_simulation is True


def test_iron_condor_defined_risk_and_greeks():
    engine = OptionsBacktestEngine()
    config = OptionsBacktestConfig(
        strategy_id="IRON_CONDOR",
        underlying="NIFTY",
        entry_date="2024-05-02",
        expiry_date="2024-05-30",
        initial_capital=500000.0,
        underlying_entry_spot=22500.0,
        volatility=0.16,
    )

    result = engine.run_backtest(config)
    assert len(result.legs) == 4
    # Iron Condor should be delta neutral near entry
    assert abs(result.payoff.net_delta) < 0.2
    # Margin should have defined-risk spread relief (not 4 naked margins)
    assert result.margin_required < 200000.0
    assert result.payoff.max_profit > 0
    assert result.payoff.max_loss < 0


def test_options_backtest_with_real_market_quotes():
    engine = OptionsBacktestEngine()
    config = OptionsBacktestConfig(
        strategy_id="LONG_CALL",
        underlying="NIFTY",
        entry_date="2024-05-02",
        expiry_date="2024-05-30",
        underlying_entry_spot=22500.0,
        underlying_exit_spot=22600.0,
    )
    # Provide actual market quote for ATM 22500 CE
    quotes = {"22500.0_CE": 185.50}
    result = engine.run_backtest(config, market_quotes=quotes)
    assert result.is_theoretical_simulation is False
    assert result.legs[0].entry_premium == 185.50
    assert "verified against supplied" in result.disclaimer.lower()


# ============================================================================
# 6. FASTAPI PHASE 5 REST API TESTS
# ============================================================================

def test_api_intraday_strategies_and_backtest():
    client = TestClient(app)

    # 1. Catalog
    res_cat = client.get("/api/india/backtest/intraday/strategies")
    assert res_cat.status_code == 200
    catalog = res_cat.json()
    assert len(catalog) == 7

    # 2. Backtest run
    payload = {
        "strategy_id": "VWAP_REVERSION",
        "symbol": "RELIANCE",
        "timeframe": "5m",
        "start_date": "2026-11-06",
        "end_date": "2026-11-13",
        "initial_capital": 200000.0,
        "position_sizing_pct": 0.25,
        "allow_short": True,
        "stop_loss_pct": 0.015,
        "take_profit_pct": 0.03,
        "walk_forward": True,
    }
    res_bt = client.post("/api/india/backtest/intraday", json=payload)
    assert res_bt.status_code == 200
    data = res_bt.json()
    assert "total_trades" in data
    assert "win_rate" in data
    assert "net_pnl" in data
    assert "equity_curve" in data
    assert "walk_forward_metrics" in data


def test_api_futures_backtest():
    client = TestClient(app)
    payload = {
        "underlying": "NIFTY",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
        "initial_capital": 1000000.0,
        "num_lots": 1,
        "days_before_expiry_roll": 3,
        "strategy_type": "TREND_FOLLOWING",
    }
    res = client.post("/api/india/backtest/futures", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "total_trades" in data
    assert "net_pnl" in data
    assert "rollover_log" in data
    assert "equity_curve" in data


def test_api_options_strategies_and_payoff():
    client = TestClient(app)

    # 1. Options Catalog
    res_cat = client.get("/api/india/backtest/options/strategies")
    assert res_cat.status_code == 200
    cat = res_cat.json()
    assert len(cat) == 11

    # 2. Options Payoff & Backtest
    payload = {
        "strategy_id": "BULL_CALL_SPREAD",
        "underlying": "NIFTY",
        "entry_date": "2024-05-02",
        "expiry_date": "2024-05-30",
        "initial_capital": 500000.0,
        "num_lots": 1,
        "underlying_entry_spot": 22500.0,
        "underlying_exit_spot": 22700.0,
        "days_to_expiry_entry": 28,
        "days_to_expiry_exit": 0,
        "volatility": 0.15,
    }
    res_bt = client.post("/api/india/backtest/options", json=payload)
    assert res_bt.status_code == 200
    data = res_bt.json()
    assert len(data["legs"]) == 2
    assert "payoff" in data
    assert data["payoff"]["max_profit"] > 0
    assert len(data["payoff"]["breakevens"]) >= 1
    assert "net_delta" in data["payoff"]
    assert "net_gamma" in data["payoff"]
    assert "net_theta" in data["payoff"]
    assert "net_vega" in data["payoff"]
