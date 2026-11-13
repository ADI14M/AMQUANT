"""Tests for AMQUANT INDIA Quantitative Engine and API Endpoints."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from quant_engine.india.backtest import run_indian_backtest
from quant_engine.india.costs import calculate_indian_cost
from quant_engine.india.features import (
    compute_cross_asset_correlation,
    compute_market_breadth,
    compute_price_features,
)
from quant_engine.india.model_ready import (
    get_bayesian_regime_inputs,
    get_correlated_gbm_parameters,
    get_crr_model_inputs,
    get_information_flow_inputs,
    get_ito_sde_calibration,
)
from quant_engine.india.quality import audit_and_clean_ohlcv
from quant_engine.india.regime_detection import BayesianRegimeDetector
from quant_engine.india.storage import IndiaStorageEngine
from quant_engine.india.universe import (
    get_instrument,
    get_sectors,
    get_supported_indices,
    list_instruments,
)

client = TestClient(app)


# ── Universe & Master Catalog Tests ──────────────────────────────────
def test_instrument_universe_lookup():
    reliance = get_instrument("RELIANCE")
    assert reliance is not None
    assert reliance.exchange == "NSE"
    assert reliance.isin == "INE002A01018"
    assert reliance.has_derivatives is True
    assert reliance.lot_size == 250

    nifty = get_instrument("NIFTY 50")
    assert nifty is not None
    assert nifty.instrument_type == "INDEX"
    assert nifty.lot_size == 25

    tatainvest = get_instrument("TATAINVEST")
    assert tatainvest is not None
    assert tatainvest.exchange == "BSE"


def test_instrument_filtering_and_search():
    large_caps = list_instruments(market_cap_category="LARGE_CAP")
    assert len(large_caps) >= 10
    assert all(i.market_cap_category == "LARGE_CAP" for i in large_caps)

    it_stocks = list_instruments(sector="Information Technology")
    assert any(i.symbol == "TCS" for i in it_stocks)
    assert any(i.symbol == "INFY" for i in it_stocks)

    etfs = list_instruments(instrument_type="ETF")
    assert any(i.symbol == "NIFTYBEES" for i in etfs)
    assert any(i.symbol == "GOLDBEES" for i in etfs)

    query_res = list_instruments(query="HDFC")
    assert len(query_res) >= 1
    assert any("HDFC" in i.symbol for i in query_res)


# ── Transaction Cost Tests ───────────────────────────────────────────
def test_indian_transaction_costs_delivery_buy():
    # Buy 100 shares of Reliance at ₹2500 = ₹250,000
    cost = calculate_indian_cost(price=2500.0, quantity=100, side="BUY", segment="DELIVERY")
    assert cost.gross_value == 250000.0
    # Brokerage capped at ₹20
    assert cost.brokerage == 20.0
    # STT on delivery buy: 0.1% = ₹250
    assert cost.stt == 250.0
    # Stamp duty on delivery buy: 0.015% = ₹37.50
    assert cost.stamp_duty == 37.50
    # Exchange charge NSE (0.00297%) = ₹7.425
    assert cost.exchange_charges == 7.42
    # Net cost should be greater than gross value
    assert cost.net_value > cost.gross_value
    assert cost.total_friction > 300.0


def test_indian_transaction_costs_delivery_sell():
    # Sell 100 shares of Reliance at ₹2500 = ₹250,000
    cost = calculate_indian_cost(price=2500.0, quantity=100, side="SELL", segment="DELIVERY")
    # Stamp duty on SELL should be 0.0
    assert cost.stamp_duty == 0.0
    # STT on delivery sell: 0.1% = ₹250
    assert cost.stt == 250.0
    # Net value should be less than gross value
    assert cost.net_value < cost.gross_value


def test_invalid_cost_parameters_raise():
    with pytest.raises(ValueError, match="strictly positive"):
        calculate_indian_cost(price=-10.0, quantity=10)
    with pytest.raises(ValueError, match="strictly positive"):
        calculate_indian_cost(price=100.0, quantity=0)


# ── Data Quality Tests ───────────────────────────────────────────────
def test_quality_auditor_deduplication_and_ohlc():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Date": list(dates) + [dates[0]],  # duplicate date
        "Open": [100.0] * 11,
        "High": [90.0] * 11,  # Invalid: High < Open!
        "Low": [80.0] * 11,
        "Close": [95.0] * 11,
        "Volume": [1000] * 11,
    })

    cleaned, report = audit_and_clean_ohlcv(df, symbol="TEST_SYM")
    assert report.duplicates_removed == 1
    assert report.invalid_ohlc_count == 10
    # Check that High was clamped to >= max(Open, Close)
    assert (cleaned["high"] >= cleaned["open"]).all()
    assert (cleaned["high"] >= cleaned["close"]).all()
    assert report.is_valid is True


# ── Feature Engine Tests ─────────────────────────────────────────────
def test_feature_engine_calculations():
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    prices = 1000.0 * np.cumprod(1.0 + np.random.normal(0.0005, 0.015, n))
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices * 0.99,
        "high": prices * 1.01,
        "low": prices * 0.98,
        "close": prices,
        "volume": np.random.randint(10000, 50000, n),
    })

    feat = compute_price_features(df)
    assert "daily_return" in feat.columns
    assert "log_return" in feat.columns
    assert "rolling_vol_20d" in feat.columns
    assert "drawdown" in feat.columns
    assert "sma_20" in feat.columns
    assert "sma_50" in feat.columns
    assert "amihud_illiq" in feat.columns
    assert "vol_regime" in feat.columns

    # Invariants
    assert (feat["drawdown"] <= 0.0).all()
    assert (feat["rolling_vol_20d"] >= 0.0).all()


def test_cross_asset_correlation():
    df_ret = pd.DataFrame({
        "RELIANCE": np.random.normal(0, 0.01, 50),
        "TCS": np.random.normal(0, 0.01, 50),
    })
    res = compute_cross_asset_correlation(df_ret)
    assert res["symbols"] == ["RELIANCE", "TCS"]
    assert len(res["correlation_matrix"]) == 2
    # Diagonal correlation should be 1.0
    assert abs(res["correlation_matrix"][0][0] - 1.0) < 1e-3
    assert abs(res["correlation_matrix"][1][1] - 1.0) < 1e-3


# ── Storage & DuckDB Tests ───────────────────────────────────────────
def test_storage_engine_parquet_and_duckdb(tmp_path):
    storage_eng = IndiaStorageEngine(base_dir=tmp_path)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=5, freq="D"),
        "open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "high": [105.0, 106.0, 107.0, 108.0, 109.0],
        "low": [98.0, 99.0, 100.0, 101.0, 102.0],
        "close": [102.0, 103.0, 104.0, 105.0, 106.0],
        "volume": [5000, 6000, 7000, 8000, 9000],
    })

    meta = storage_eng.save_parquet("TEST_STOCK", df, stage="cleaned")
    assert meta.records_count == 5
    assert meta.symbol == "TEST_STOCK"

    loaded = storage_eng.load_parquet("TEST_STOCK", stage="cleaned")
    assert loaded is not None
    assert len(loaded) == 5

    # Run DuckDB query
    audit = storage_eng.get_coverage_audit()
    assert audit["total_parquet_files"] >= 1
    assert "cleaned" in audit["stages"]


# ── Model-Ready Data Tests ───────────────────────────────────────────
def test_model_ready_data_interfaces():
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    prices = np.linspace(2000, 2500, 60)
    df = pd.DataFrame({
        "timestamp": dates,
        "close": prices,
        "volume": [50000] * 60,
    })
    feat = compute_price_features(df)

    crr = get_crr_model_inputs(feat)
    assert crr["spot"] == 2500.0
    assert crr["strike"] > 0
    assert crr["volatility"] > 0
    assert crr["risk_free_rate"] > 0

    info_flow = get_information_flow_inputs(feat)
    assert "kyle_lambda" in info_flow
    assert "avg_daily_turnover_cr" in info_flow

    bayes_in = get_bayesian_regime_inputs(feat)
    assert bayes_in["trials"] == 59
    assert bayes_in["posterior_alpha"] > bayes_in["prior_alpha"]

    ito = get_ito_sde_calibration(feat)
    assert "drift_mu" in ito
    assert "diffusion_sigma" in ito


# ── First Research Experiment Tests ──────────────────────────────────
def test_bayesian_regime_detector_experiment():
    np.random.seed(123)
    n = 150
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    rets = np.concatenate([
        np.random.normal(0.001, 0.008, 75),  # Bull regime
        np.random.normal(-0.001, 0.015, 75),  # Bear regime
    ])
    prices = 1000.0 * np.cumprod(1.0 + rets)
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices * 0.995,
        "high": prices * 1.005,
        "low": prices * 0.99,
        "close": prices,
        "volume": [100000] * n,
    })

    detector = BayesianRegimeDetector()
    res = detector.run_experiment(df, symbol="TEST_INDEX", train_ratio=0.6)

    assert res.symbol == "TEST_INDEX"
    assert res.current_regime in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert 0.0 <= res.current_bullish_prob <= 1.0
    assert 0.0 <= res.current_bearish_prob <= 1.0
    assert 0.0 <= res.current_neutral_prob <= 1.0
    assert abs((res.current_bullish_prob + res.current_bearish_prob + res.current_neutral_prob) - 1.0) < 0.05
    assert res.brier_score_test >= 0.0
    assert res.log_loss_test >= 0.0
    assert "cagr_pct" in res.strategy_metrics
    assert "cagr_pct" in res.benchmark_metrics
    assert len(res.limitations) >= 3


# ── Backtesting Engine Tests ─────────────────────────────────────────
def test_indian_backtest_execution():
    np.random.seed(42)
    n = 80
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    prices = 1000.0 * np.cumprod(1.0 + np.random.normal(0.001, 0.01, n))
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices * 0.998,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": [50000] * n,
    })

    summary = run_indian_backtest(df, symbol="RELIANCE", initial_capital=500_000.0)
    assert summary.symbol == "RELIANCE"
    assert summary.initial_capital_inr == 500_000.0
    assert summary.ending_capital_inr > 0
    assert isinstance(summary.sharpe_ratio, float)
    assert isinstance(summary.max_drawdown_pct, float)
    assert len(summary.equity_curve) > 0


# ── FastAPI Endpoints Tests ──────────────────────────────────────────
def test_api_instruments_endpoints():
    r = client.get("/api/india/instruments?query=RELIANCE")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["symbol"] == "RELIANCE"

    r_indices = client.get("/api/india/indices")
    assert r_indices.status_code == 200
    assert len(r_indices.json()) >= 5

    r_sectors = client.get("/api/india/sectors")
    assert r_sectors.status_code == 200
    assert "Information Technology" in r_sectors.json()


def test_api_market_overview_endpoint():
    r = client.get("/api/india/market-overview")
    assert r.status_code == 200
    data = r.json()
    assert "macro_snapshot" in data
    assert data["macro_snapshot"]["rbi_repo_rate"] == 6.50
    assert "headline_quotes" in data
    assert "market_breadth" in data


def test_api_data_coverage_endpoint():
    r = client.get("/api/india/data-coverage")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "operational"
    assert "stages" in data
    assert "missing_coverage" in data


def test_api_history_and_model_ready_endpoints():
    r_hist = client.get("/api/india/history/NIFTY 50")
    assert r_hist.status_code == 200
    hist_data = r_hist.json()
    assert hist_data["symbol"] == "NIFTY 50"
    assert len(hist_data["series"]) > 0

    r_model = client.get("/api/india/model-ready/NIFTY 50")
    assert r_model.status_code == 200
    m_data = r_model.json()
    assert "week_1_crr" in m_data
    assert "week_3_bayesian" in m_data


def test_api_bayesian_regime_experiment_endpoint():
    payload = {
        "symbol": "NIFTY 50",
        "mu_bull": 0.18,
        "mu_bear": -0.22,
        "mu_neut": 0.04,
        "sigma_bull": 0.14,
        "sigma_bear": 0.28,
        "regime_persistence": 0.92,
        "entry_threshold": 0.50,
    }
    r = client.post("/api/india/experiment/bayesian-regime", json=payload)
    assert r.status_code == 200
    res = r.json()
    assert res["symbol"] == "NIFTY 50"
    assert res["current_regime"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert "brier_score_test" in res
    assert "strategy_metrics" in res
    assert "benchmark_metrics" in res
    assert "cost_summary" in res


def test_api_backtest_endpoint():
    payload = {
        "symbol": "NIFTY 50",
        "strategy_type": "SMA_CROSS",
        "fast_period": 20,
        "slow_period": 50,
        "initial_capital": 1000000.0,
    }
    r = client.post("/api/india/backtest", json=payload)
    assert r.status_code == 200
    res = r.json()
    assert res["symbol"] == "NIFTY 50"
    assert "cagr_pct" in res
    assert "sharpe_ratio" in res
    assert "total_friction_inr" in res
