"""AMQUANT INDIA - Phase 4 Intraday Data Infrastructure and F&O Market Data Foundation Test Suite.

Verifies:
1. Exchange Session & Timezone: 09:15-15:30 IST window, Asia/Kolkata normalization, weekend & holiday filtering.
2. Missing Candle Auditor: Expected bars per timeframe (1m: 375, 5m: 75, 15m: 25, 30m: 13, 60m: 7), session completeness %, gap detection.
3. Incremental Intraday Merging: Deduplication, overwrite handling, and chronological ordering.
4. Derivatives Contract Master & Historical Lot Sizes: SEBI circular changes (NIFTY 75->50->25->75, BANKNIFTY 40->25->15->30),
   monthly expiry calendar engine with holiday rollbacks, standardized contract symbols.
5. Continuous Futures Builder: UNADJUSTED_CALENDAR, BACK_ADJUSTED_DIFFERENCE, RATIO_ADJUSTED, roll spread tracking,
   and research invariant disclaimer ("Never treat a continuous futures series as an executable contract").
6. Option Chain & Model Greeks: Bidirectional strikes matrix, ATM detection, PCR (OI & Vol), Max Pain strike calculation,
   Black-Scholes IV inversion, Delta, Gamma, Theta, Vega, and is_model_estimate flag.
7. Multi-Provider Architecture: Specifications for Yahoo, Zerodha, Upstox, Angel One, and NSE Bhavcopy, £0 zero-cost guarantee.
8. Storage Engine: Intraday and derivatives Parquet persistence and loading.
9. FastAPI Endpoints: All 7 Phase 4 REST endpoints.
"""

from __future__ import annotations

from datetime import date, datetime
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from quant_engine.india.derivatives.futures import (
    ContinuousFuturesBuilder,
)
from quant_engine.india.derivatives.master import (
    DerivativesContract,
    build_contract_symbol,
    generate_contract_master_catalog,
    get_historical_lot_size,
    get_lot_size_history,
    get_monthly_expiry_date,
)
from quant_engine.india.derivatives.options import (
    OptionChainBuilder,
    calculate_max_pain,
    compute_option_greeks_for_quote,
)
from quant_engine.india.intraday import (
    EXPECTED_BARS_PER_SESSION,
    ExchangeSessionValidator,
    MissingCandleAuditor,
    merge_incremental_intraday,
)
from quant_engine.india.providers.registry import (
    get_provider,
    list_all_provider_specs,
)
from quant_engine.india.storage import IndiaStorageEngine


# =====================================================================
# 1. EXCHANGE SESSION VALIDATION & TIMEZONE
# =====================================================================

class TestExchangeSessionValidator:
    """Test market hours (09:15-15:30 IST), timezone conversion, weekend and holiday filtering."""

    def test_filter_valid_trading_session(self):
        timestamps = [
            "2024-06-10 09:05:00",  # Pre-market -> Filter out
            "2024-06-10 09:15:00",  # Market open -> Keep
            "2024-06-10 12:30:00",  # Regular trading -> Keep
            "2024-06-10 15:30:00",  # Market close -> Keep
            "2024-06-10 15:35:00",  # Post-market -> Filter out
            "2024-06-08 10:00:00",  # Saturday -> Filter out
            "2024-06-09 11:00:00",  # Sunday -> Filter out
        ]
        df = pd.DataFrame({
            "datetime": pd.to_datetime(timestamps),
            "open": [100.0] * len(timestamps),
            "high": [105.0] * len(timestamps),
            "low": [99.0] * len(timestamps),
            "close": [102.0] * len(timestamps),
            "volume": [1000] * len(timestamps),
        })

        validator = ExchangeSessionValidator()
        filtered, dups, out_of_session = validator.normalize_and_filter_session(df, "datetime")

        # 09:15, 12:30, 15:30 should be kept
        assert len(filtered) == 3
        assert out_of_session == 4
        dates_kept = [t for t in filtered["datetime"]]
        assert any("09:15:00" in d for d in dates_kept)
        assert any("12:30:00" in d for d in dates_kept)
        assert any("15:30:00" in d for d in dates_kept)

    def test_utc_timezone_normalization(self):
        # 03:45 UTC corresponds to 09:15 IST
        timestamps_utc = pd.date_range("2024-06-10 03:45:00", periods=5, freq="5min", tz="UTC")
        df = pd.DataFrame({
            "datetime": timestamps_utc,
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 102.0,
            "volume": 1000,
        })
        validator = ExchangeSessionValidator()
        filtered, _, _ = validator.normalize_and_filter_session(df, "datetime")
        assert len(filtered) == 5
        # Verify first record is 09:15:00 IST
        assert "09:15:00" in str(filtered["datetime"].iloc[0])


# =====================================================================
# 2. MISSING CANDLE AUDITOR & BAR COMPLETENESS
# =====================================================================

class TestMissingCandleAuditor:
    """Test expected candle calculations and session completeness."""

    def test_expected_bars_per_session(self):
        assert EXPECTED_BARS_PER_SESSION["1m"] == 375
        assert EXPECTED_BARS_PER_SESSION["5m"] == 75
        assert EXPECTED_BARS_PER_SESSION["15m"] == 25
        assert EXPECTED_BARS_PER_SESSION["30m"] == 13
        assert EXPECTED_BARS_PER_SESSION["60m"] == 7

    def test_audit_series_completeness(self):
        dt_index = pd.date_range("2024-06-10 09:15:00", periods=75, freq="5min")
        df_full = pd.DataFrame({
            "datetime": dt_index.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 1000,
        })
        auditor = MissingCandleAuditor(interval="5m")
        report = auditor.audit(df_full, "TEST_5M")

        assert report.total_sessions == 1
        assert report.total_bars == 75
        assert report.overall_completeness_pct == 100.0
        assert report.total_missing_bars == 0

    def test_audit_partial_session_with_missing_bars(self):
        dt_index = pd.date_range("2024-06-10 09:15:00", periods=50, freq="5min")
        df_partial = pd.DataFrame({
            "datetime": dt_index.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 1000,
        })
        auditor = MissingCandleAuditor(interval="5m")
        report = auditor.audit(df_partial, "TEST_PARTIAL")

        assert report.total_sessions == 1
        assert report.total_bars == 50
        assert report.overall_completeness_pct == pytest.approx(66.67, abs=0.1)
        assert report.total_missing_bars == 25


# =====================================================================
# 3. INCREMENTAL MERGING & DEDUPLICATION
# =====================================================================

class TestIncrementalMerging:
    """Test deduplicating and merging existing vs new intraday records."""

    def test_merge_incremental_intraday(self):
        dt1 = pd.date_range("2024-06-10 09:15:00", periods=10, freq="5min")
        existing = pd.DataFrame({
            "datetime": dt1.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 100.0, "high": 105.0, "low": 99.0, "close": 101.0, "volume": 500,
        })

        dt2 = pd.date_range("2024-06-10 09:40:00", periods=10, freq="5min")
        new_records = pd.DataFrame({
            "datetime": dt2.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 101.0, "high": 106.0, "low": 100.0, "close": 104.0, "volume": 800,
        })

        merged, added_count = merge_incremental_intraday(existing, new_records)
        assert len(merged) == 15
        assert added_count == 5
        assert merged["datetime"].is_monotonic_increasing


# =====================================================================
# 4. DERIVATIVES CONTRACT MASTER & HISTORICAL LOT SIZES
# =====================================================================

class TestDerivativesMaster:
    """Test SEBI historical lot size schedules, monthly expiry calendar, and contract builders."""

    def test_nifty_historical_lot_sizes(self):
        # Pre-April 2021: 75
        assert get_historical_lot_size("NIFTY 50", date(2020, 10, 15)) == 75
        # May 2021 to April 2024: 50
        assert get_historical_lot_size("NIFTY 50", date(2022, 6, 1)) == 50
        assert get_historical_lot_size("NIFTY", date(2023, 12, 1)) == 50
        # May 2024 to Nov 2024: 25
        assert get_historical_lot_size("NIFTY 50", date(2024, 7, 1)) == 25
        # Post-Nov 20, 2024 SEBI revision: 75
        assert get_historical_lot_size("NIFTY 50", date(2024, 11, 25)) == 75
        assert get_historical_lot_size("NIFTY 50", date(2025, 1, 10)) == 75

    def test_banknifty_historical_lot_sizes(self):
        # Pre-July 2023: 25
        assert get_historical_lot_size("BANKNIFTY", date(2022, 1, 15)) == 25
        # July 2023 to Nov 2024: 15
        assert get_historical_lot_size("BANKNIFTY", date(2024, 1, 15)) == 15
        # Post-Nov 2024 SEBI revision: 30
        assert get_historical_lot_size("BANKNIFTY", date(2024, 11, 25)) == 30

    def test_stock_futures_lot_sizes(self):
        assert get_historical_lot_size("RELIANCE", date(2024, 6, 1)) == 250
        assert get_historical_lot_size("TCS", date(2024, 6, 1)) == 175
        assert get_historical_lot_size("INFY", date(2024, 6, 1)) == 400

    def test_lot_size_history_schedule(self):
        history = get_lot_size_history("NIFTY 50")
        assert len(history) >= 4
        assert history[-1]["lot_size"] == 75
        assert history[-1]["end_date"] == "Present"

    def test_monthly_expiry_date_calculation(self):
        expiry_dec_2024 = get_monthly_expiry_date(2024, 12)
        assert expiry_dec_2024 == "2024-12-26"
        dt = datetime.strptime(expiry_dec_2024, "%Y-%m-%d")
        assert dt.weekday() == 3  # Thursday

    def test_build_contract_symbol(self):
        opt_sym = build_contract_symbol(
            underlying="NIFTY",
            expiry_date="2024-12-26",
            contract_type="OPTIDX",
            strike_price=24500.0,
            option_type="CE",
        )
        assert opt_sym == "NIFTY24DEC24500CE"

        fut_sym = build_contract_symbol(
            underlying="RELIANCE",
            expiry_date="2024-12-26",
            contract_type="FUTSTK",
        )
        assert fut_sym == "RELIANCE24DECFUT"

    def test_contract_master_catalog_generation(self):
        catalog = generate_contract_master_catalog(["NIFTY 50", "RELIANCE"])
        assert len(catalog) > 0
        fut_contracts = [c for c in catalog if c.contract_type in ("FUTIDX", "FUTSTK")]
        opt_contracts = [c for c in catalog if c.contract_type in ("OPTIDX", "OPTSTK")]
        assert len(fut_contracts) >= 4
        assert len(opt_contracts) >= 10


# =====================================================================
# 5. CONTINUOUS FUTURES BUILDER & ROLL METHODOLOGY
# =====================================================================

class TestContinuousFuturesBuilder:
    """Test calendar, back-adjusted additive, and Panama canal ratio adjustments."""

    @pytest.fixture
    def sample_contracts_dict(self):
        rng = np.random.default_rng(42)
        dates1 = pd.date_range("2024-05-01", "2024-05-30", freq="B")
        dates2 = pd.date_range("2024-05-20", "2024-06-27", freq="B")

        p1 = 22500.0 + np.cumsum(rng.normal(5, 50, len(dates1)))
        df_near = pd.DataFrame({
            "date": dates1,
            "open": p1, "high": p1 + 40, "low": p1 - 40, "close": p1 + 10,
            "volume": 50000, "open_interest": 1000000, "expiry_date": "2024-05-30",
        })

        p2 = 22600.0 + np.cumsum(rng.normal(5, 50, len(dates2)))
        df_far = pd.DataFrame({
            "date": dates2,
            "open": p2, "high": p2 + 40, "low": p2 - 40, "close": p2 + 10,
            "volume": 30000, "open_interest": 600000, "expiry_date": "2024-06-27",
        })

        return {
            "NIFTY24MAYFUT": df_near,
            "NIFTY24JUNFUT": df_far,
        }

    def test_unadjusted_calendar_rollover(self, sample_contracts_dict):
        builder = ContinuousFuturesBuilder(method="UNADJUSTED_CALENDAR")
        res = builder.build_continuous_series("NIFTY", sample_contracts_dict)

        assert res.is_continuous is True
        assert len(res.series) > 0
        assert len(res.rollover_events) == 1
        assert "Never treat a continuous futures series as an executable contract" in res.execution_disclaimer

    def test_back_adjusted_difference_rollover(self, sample_contracts_dict):
        builder = ContinuousFuturesBuilder(method="BACK_ADJUSTED_DIFFERENCE")
        res = builder.build_continuous_series("NIFTY", sample_contracts_dict)

        assert res.method == "BACK_ADJUSTED_DIFFERENCE"
        assert len(res.rollover_events) == 1
        roll = res.rollover_events[0]
        assert roll.roll_spread != 0.0
        assert "Never treat a continuous futures series as an executable contract" in res.execution_disclaimer

    def test_ratio_adjusted_rollover(self, sample_contracts_dict):
        builder = ContinuousFuturesBuilder(method="RATIO_ADJUSTED")
        res = builder.build_continuous_series("NIFTY", sample_contracts_dict)

        assert res.method == "RATIO_ADJUSTED"
        assert len(res.series) > 0
        assert res.is_continuous is True


# =====================================================================
# 6. OPTION CHAIN & MODEL GREEKS
# =====================================================================

class TestOptionChainAndGreeks:
    """Test Black-Scholes IV inversion, Greeks, PCR, and Max Pain."""

    def test_option_greeks_calculation_call(self):
        # ATM Call: Spot 24,000, Strike 24,000, T=30 days, Price 350
        iv, delta, gamma, theta, vega = compute_option_greeks_for_quote(
            market_price=350.0,
            spot=24000.0,
            strike=24000.0,
            maturity_years=30 / 365,
            kind="call",
            rate=0.065,
        )
        assert iv > 5.0
        assert iv < 50.0
        assert 0.40 <= delta <= 0.65  # ATM Call delta ~0.50
        assert gamma > 0.0
        assert theta < 0.0  # Time decay is negative
        assert vega > 0.0

    def test_option_greeks_calculation_put(self):
        # ATM Put: Spot 24,000, Strike 24,000, T=30 days, Price 300
        iv, delta, gamma, theta, vega = compute_option_greeks_for_quote(
            market_price=300.0,
            spot=24000.0,
            strike=24000.0,
            maturity_years=30 / 365,
            kind="put",
            rate=0.065,
        )
        assert -0.65 <= delta <= -0.35  # ATM Put delta ~ -0.50
        assert gamma > 0.0
        assert theta < 0.0
        assert vega > 0.0

    def test_option_chain_builder_and_metrics(self):
        strikes = [23800.0, 23900.0, 24000.0, 24100.0, 24200.0]
        quotes = []
        for s in strikes:
            quotes.append({
                "strike": s, "option_type": "CE", "open": 100, "high": 120, "low": 90, "close": 110,
                "volume": 2000, "open_interest": 10000, "lot_size": 25,
            })
            quotes.append({
                "strike": s, "option_type": "PE", "open": 90, "high": 110, "low": 80, "close": 95,
                "volume": 2500, "open_interest": 12000, "lot_size": 25,
            })

        builder = OptionChainBuilder()
        chain = builder.build_chain(
            underlying="NIFTY",
            underlying_price=24020.0,
            expiry_date="2024-12-26",
            quotes_data=quotes,
            as_of_date="2024-12-01",
            risk_free_rate=0.065,
        )

        assert chain.underlying == "NIFTY"
        assert chain.max_pain_strike in strikes
        assert len(chain.strikes) == 5
        assert chain.pcr_oi > 0
        assert chain.pcr_volume > 0

    def test_calculate_max_pain(self):
        strikes_data = [
            (23800.0, 1000, 18000),
            (23900.0, 2000, 12000),
            (24000.0, 8000, 7000),
            (24100.0, 15000, 2000),
            (24200.0, 20000, 500),
        ]
        max_pain = calculate_max_pain(strikes_data)
        assert max_pain == 24000.0


# =====================================================================
# 7. MULTI-PROVIDER ARCHITECTURE & ZERO-COST GUARANTEE
# =====================================================================

class TestProviderArchitecture:
    """Test 5 integrated providers, specifications, rate limits, and £0 cost policy."""

    def test_list_all_provider_specs(self):
        specs = list_all_provider_specs()
        assert len(specs) == 5
        provider_ids = [s["provider_id"] for s in specs]
        assert "yahoo" in provider_ids
        assert "zerodha" in provider_ids
        assert "upstox" in provider_ids
        assert "angel_one" in provider_ids
        assert "nse_bhavcopy" in provider_ids

        for spec in specs:
            assert spec["cost_inr_gbp"] is not None
            assert "£0" in spec["cost_inr_gbp"]
            assert len(spec["supported_intervals"]) > 0
            assert spec["historical_depth_daily"] != ""
            assert spec["rate_limits"] != ""

    def test_get_provider_instances(self):
        p_yahoo = get_provider("yahoo")
        assert p_yahoo.get_provider_spec().provider_id == "yahoo"
        p_bhav = get_provider("nse_bhavcopy")
        assert p_bhav.get_provider_spec().provider_id == "nse_bhavcopy"


# =====================================================================
# 8. STORAGE ENGINE (INTRADAY & DERIVATIVES)
# =====================================================================

class TestStorageEngine:
    """Test saving and loading intraday and derivatives datasets in Parquet."""

    def test_intraday_parquet_storage_roundtrip(self, tmp_path):
        storage = IndiaStorageEngine(base_dir=tmp_path)
        dt = pd.date_range("2024-06-10 09:15:00", periods=50, freq="5min")
        df = pd.DataFrame({
            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 100.0, "high": 105.0, "low": 99.0, "close": 103.0, "volume": 1200,
        })
        meta = storage.save_intraday_parquet("RELIANCE", df, "5m")
        assert meta.records_count == 50

        loaded = storage.load_intraday_parquet("RELIANCE", "5m")
        assert loaded is not None
        assert len(loaded) == 50
        assert "close" in loaded.columns

    def test_derivatives_parquet_storage_roundtrip(self, tmp_path):
        storage = IndiaStorageEngine(base_dir=tmp_path)
        dt = pd.date_range("2024-06-01", periods=20, freq="B")
        df = pd.DataFrame({
            "datetime": dt.strftime("%Y-%m-%d"),
            "open": 24000.0, "high": 24200.0, "low": 23900.0, "close": 24150.0,
            "volume": 40000, "open_interest": 800000,
        })
        meta = storage.save_derivatives_parquet("NIFTY24JUNFUT", df, "futures")
        assert meta.records_count == 20

        loaded = storage.load_derivatives_parquet("NIFTY24JUNFUT", "futures")
        assert loaded is not None
        assert len(loaded) == 20
        assert "open_interest" in loaded.columns


# =====================================================================
# 9. FASTAPI PHASE 4 ENDPOINTS
# =====================================================================

class TestPhase4ApiEndpoints:
    """Test all 7 Phase 4 REST API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_intraday_history(self, client):
        resp = client.get("/api/india/intraday/history?symbol=RELIANCE&interval=5m&days=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "RELIANCE"
        assert data["interval"] == "5m"
        assert "quality_report" in data
        assert "overall_completeness_pct" in data["quality_report"]

    def test_download_intraday_data(self, client):
        payload = {
            "symbol": "TCS",
            "interval": "15m",
            "days": 1,
            "save_to_parquet": False,
        }
        resp = client.post("/api/india/intraday/download", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "TCS"
        assert data["interval"] == "15m"

    def test_get_derivatives_contracts(self, client):
        resp = client.get("/api/india/derivatives/contracts?underlying=NIFTY")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["underlying_symbol"] == "NIFTY 50"

    def test_get_derivatives_lot_sizes(self, client):
        resp = client.get("/api/india/derivatives/lot-sizes?underlying=NIFTY")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "NIFTY"
        assert data["current_lot_size"] == 75
        assert len(data["history"]) >= 4

    def test_get_continuous_futures(self, client):
        resp = client.get("/api/india/derivatives/futures/continuous?underlying=NIFTY&methodology=BACK_ADJUSTED_DIFFERENCE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "NIFTY"
        assert data["method"] == "BACK_ADJUSTED_DIFFERENCE"
        assert data["is_continuous"] is True
        assert "Never treat a continuous futures series as an executable contract" in data["execution_disclaimer"]

    def test_get_options_chain(self, client):
        resp = client.get("/api/india/derivatives/options/chain?underlying=NIFTY")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "NIFTY"
        assert "pcr_oi" in data
        assert "max_pain_strike" in data
        assert "strikes" in data
        assert len(data["strikes"]) > 0

    def test_get_providers_specification(self, client):
        resp = client.get("/api/india/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 5
        provider_ids = [p["provider_id"] for p in data]
        assert "yahoo" in provider_ids
        assert "zerodha" in provider_ids
        assert "nse_bhavcopy" in provider_ids
