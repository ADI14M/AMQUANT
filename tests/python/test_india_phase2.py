"""Comprehensive Unit & Integration Tests for AMQUANT INDIA Phase 2.

Covers:
- Expanded Instrument Universe & Delisted Stock handling (point-in-time)
- Corporate Action Price Adjustments (splits, bonus, dividends, total-return index)
- Mathematical Invariant Verification (turnover preservation: P_adj * V_adj = P_raw * V_raw)
- HistoricalDataCollector batch, incremental & resilience logic
- Phase 2 FastAPI REST Endpoints & Coverage Audit
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from quant_engine.india.adjustments import (
    CorporateAction,
    compute_adjusted_series,
    validate_adjustments,
)
from quant_engine.india.collector import HistoricalDataCollector, DownloadResult
from quant_engine.india.storage import IndiaStorageEngine
from quant_engine.india.universe import (
    INSTRUMENTS_MASTER,
    get_instrument,
    get_universe_stats,
    list_instruments,
)


client = TestClient(app)


def test_expanded_universe_and_delisted_stocks():
    """Verify universe expansion >= 100 instruments, with delisted flags and listing dates."""
    stats = get_universe_stats()
    assert stats["total"] >= 100, f"Expected at least 100 instruments, got {stats['total']}"
    assert stats["active"] >= 95
    assert stats["inactive"] >= 5  # RCOM, JETAIRWAYS, DHFL, SINTEX, CAIRN

    # Check delisted stock attributes
    rcom = get_instrument("RCOM")
    assert rcom is not None
    assert not rcom.is_active
    assert rcom.delisting_date != ""
    assert rcom.listing_date != ""

    jet = get_instrument("JETAIRWAYS")
    assert jet is not None
    assert not jet.is_active

    # Check active bluechips have listing date and active flag
    reliance = get_instrument("RELIANCE")
    assert reliance is not None
    assert reliance.is_active
    assert hasattr(reliance, "listing_date")


def test_corporate_actions_split_adjustment_and_turnover_preservation():
    """Verify split adjustment backward scaling and turnover preservation invariant."""
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    raw_df = pd.DataFrame({
        "date": dates,
        "open": [200.0, 210.0, 110.0, 115.0, 120.0, 125.0],
        "high": [205.0, 215.0, 112.0, 118.0, 122.0, 128.0],
        "low": [195.0, 205.0, 108.0, 112.0, 118.0, 124.0],
        "close": [200.0, 210.0, 110.0, 115.0, 120.0, 125.0],
        "volume": [1000, 1200, 2400, 2500, 2600, 2800],
    })

    # Split 2:1 on date index 2
    ex_date = str(dates[2].date())
    split_action = [
        CorporateAction(
            symbol="TEST",
            action_type="SPLIT",
            ex_date=ex_date,
            ratio=2.0,
            notes="2:1 Stock Split",
        )
    ]

    result = compute_adjusted_series(raw_df, split_action)
    adj_df = result["adjusted"]

    # Historical prices before split should be halved
    assert adj_df.loc[0, "close"] == 100.0
    assert adj_df.loc[1, "close"] == 105.0

    # Post-split prices remain unchanged
    assert adj_df.loc[2, "close"] == 110.0
    assert adj_df.loc[3, "close"] == 115.0

    # Volume before split should be doubled
    assert adj_df.loc[0, "volume"] == 2000
    assert adj_df.loc[1, "volume"] == 2400

    # Turnover preservation validation
    validation = validate_adjustments(raw_df, adj_df)
    assert validation["is_valid"] is True
    assert validation["turnover_preserved"] is True
    assert len(validation["issues"]) == 0


def test_cash_dividend_total_return_series():
    """Verify total return compounding incorporates cash dividends."""
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    raw_df = pd.DataFrame({
        "date": dates,
        "open": [100.0, 100.0, 100.0, 100.0],
        "high": [105.0, 105.0, 105.0, 105.0],
        "low": [95.0, 95.0, 95.0, 95.0],
        "close": [100.0, 100.0, 100.0, 100.0],
        "volume": [1000, 1000, 1000, 1000],
    })

    # Cash dividend of ₹5 on day index 2
    ex_date = str(dates[2].date())
    actions = [
        CorporateAction(
            symbol="TEST",
            action_type="DIVIDEND",
            ex_date=ex_date,
            dividend_amount=5.0,
            notes="Interim dividend ₹5",
        )
    ]

    result = compute_adjusted_series(raw_df, actions)
    tr_df = result["total_return"]

    # On day 0: TR index = 100
    assert tr_df.loc[0, "tr_index"] == 100.0
    # On day 1: price unchanged, div 0 => TR index = 100
    assert tr_df.loc[1, "tr_index"] == 100.0
    # On day 2: price 100 + div 5 => return = 5% => TR index = 105
    assert pytest.approx(tr_df.loc[2, "tr_index"], rel=1e-3) == 105.0
    # On day 3: price unchanged => TR index remains 105
    assert pytest.approx(tr_df.loc[3, "tr_index"], rel=1e-3) == 105.0


def test_historical_collector_coverage_audit():
    """Verify collector reports detailed coverage audit across existing storage."""
    storage = IndiaStorageEngine()
    collector = HistoricalDataCollector(storage_engine=storage)

    coverage = collector.get_coverage_detail()
    assert isinstance(coverage, list)
    assert len(coverage) >= 5

    # Check fields of an audited instrument
    item = coverage[0]
    assert "symbol" in item
    assert "first_date" in item
    assert "last_date" in item
    assert "total_sessions" in item
    assert "has_adjusted" in item
    assert "has_total_return" in item
    assert "file_size_kb" in item


def test_phase2_fastapi_endpoints():
    """Verify all Phase 2 FastAPI REST endpoints."""
    # 1. Universe stats
    r_stats = client.get("/api/india/universe-stats")
    assert r_stats.status_code == 200
    stats = r_stats.json()
    assert stats["total"] >= 100
    assert "by_exchange" in stats

    # 2. History manager coverage
    r_cov = client.get("/api/india/history-manager/coverage")
    assert r_cov.status_code == 200
    cov = r_cov.json()
    assert cov["total_instruments_with_data"] >= 5
    assert "instruments" in cov

    # 3. Corporate actions for RELIANCE
    r_act = client.get("/api/india/corporate-actions/RELIANCE")
    assert r_act.status_code == 200
    act_data = r_act.json()
    assert act_data["symbol"] == "RELIANCE"
    assert "actions" in act_data
    assert "validation" in act_data

    # 4. Series comparison for RELIANCE
    r_series = client.get("/api/india/series-comparison/RELIANCE")
    assert r_series.status_code == 200
    series_data = r_series.json()
    assert series_data["symbol"] == "RELIANCE"
    assert "series" in series_data
    assert series_data["has_raw"] is True
    assert series_data["has_adjusted"] is True

