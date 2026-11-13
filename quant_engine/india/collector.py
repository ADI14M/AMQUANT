"""Batch Historical Data Collector for AMQUANT INDIA.

Orchestrates bulk download of Indian equity / ETF / index OHLCV data,
corporate-action adjustment, total return computation, and incremental
updates — all persisted to the layered Parquet storage architecture.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from quant_engine.india.adjustments import (
    compute_adjusted_series,
    fetch_corporate_actions,
    validate_adjustments,
)
from quant_engine.india.quality import audit_and_clean_ohlcv
from quant_engine.india.providers.yahoo import YahooFinanceProvider
from quant_engine.india.storage import IndiaStorageEngine
from quant_engine.india.universe import get_instrument

logger = logging.getLogger("amquant.india.collector")


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DownloadResult:
    """Outcome of downloading data for a single symbol."""

    symbol: str
    success: bool
    records: int = 0
    start_date: str = ""
    end_date: str = ""
    error: str = ""
    is_incremental: bool = False
    download_time_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BatchDownloadSummary:
    """Aggregate outcome of a batch download run."""

    total_requested: int = 0
    successful: int = 0
    failed: int = 0
    total_records: int = 0
    results: list = field(default_factory=list)  # list[DownloadResult dicts]
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class HistoricalDataCollector:
    """Batch download manager for Indian market data.

    Uses :class:`YahooFinanceProvider` to fetch OHLCV data,
    :func:`audit_and_clean_ohlcv` for quality cleaning, and the
    ``adjustments`` module for corporate-action adjustment and total
    return computation.

    Parameters
    ----------
    storage_engine:
        An :class:`IndiaStorageEngine` instance.  A new default engine
        is created when *None*.
    rate_limit_seconds:
        Minimum pause between consecutive Yahoo Finance API calls.
    """

    def __init__(
        self,
        storage_engine: IndiaStorageEngine | None = None,
        rate_limit_seconds: float = 0.5,
    ):
        self.storage = storage_engine or IndiaStorageEngine()
        self.provider = YahooFinanceProvider(storage_engine=self.storage)
        self.rate_limit_seconds = rate_limit_seconds

    # -----------------------------------------------------------------
    # Single symbol download
    # -----------------------------------------------------------------

    def download_single(
        self,
        symbol: str,
        period: str = "10y",
        incremental: bool = True,
    ) -> DownloadResult:
        """Download historical data for one symbol.

        Workflow
        --------
        1. If *incremental* and cleaned data already exists, download
           only the delta from ``max_date + 1 day`` to today.
        2. Otherwise download the full *period*.
        3. Audit & clean the raw data.
        4. Save to ``raw`` and ``cleaned`` Parquet layers.
        5. Fetch corporate actions, compute adjusted series &
           total-return index, validate, and persist to ``adjusted``,
           ``total_return``, and ``corporate_actions`` layers.

        Returns
        -------
        DownloadResult
        """
        t0 = time.monotonic()
        is_incremental = False

        try:
            # Resolve Yahoo ticker
            inst = get_instrument(symbol)
            yahoo_ticker = (
                inst.yahoo_ticker
                if inst and inst.yahoo_ticker
                else f"{symbol.strip().upper()}.NS"
            )

            existing_df: pd.DataFrame | None = None
            start_date: str | None = None
            end_date: str | None = None

            # ---- Incremental check ----
            if incremental:
                existing_df = self.storage.load_parquet(
                    symbol, stage="cleaned", dataset_type="ohlcv"
                )
                if existing_df is not None and not existing_df.empty:
                    date_col = next(
                        (c for c in existing_df.columns if c in ("date", "timestamp", "datetime")),
                        None,
                    )
                    if date_col:
                        max_date = pd.to_datetime(existing_df[date_col]).max()
                        start_date = (max_date + timedelta(days=1)).strftime("%Y-%m-%d")
                        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                        # If start_date is today or in the future, nothing to update
                        if start_date >= end_date:
                            elapsed = time.monotonic() - t0
                            return DownloadResult(
                                symbol=symbol,
                                success=True,
                                records=len(existing_df),
                                start_date=str(existing_df[date_col].min())[:10],
                                end_date=str(existing_df[date_col].max())[:10],
                                is_incremental=True,
                                download_time_seconds=round(elapsed, 3),
                            )

                        is_incremental = True

            # ---- Rate-limit ----
            time.sleep(self.rate_limit_seconds)

            # ---- Fetch from Yahoo ----
            import yfinance as yf

            ticker_obj = yf.Ticker(yahoo_ticker)
            if start_date and end_date:
                raw_new = ticker_obj.history(start=start_date, end=end_date, auto_adjust=False)
            else:
                raw_new = ticker_obj.history(period=period, auto_adjust=False)

            if raw_new.empty and existing_df is not None and not existing_df.empty:
                # No new data but we already have existing — skip update
                date_col = next(
                    (c for c in existing_df.columns if c in ("date", "timestamp", "datetime")),
                    None,
                )
                elapsed = time.monotonic() - t0
                return DownloadResult(
                    symbol=symbol,
                    success=True,
                    records=len(existing_df),
                    start_date=str(existing_df[date_col].min())[:10] if date_col else "",
                    end_date=str(existing_df[date_col].max())[:10] if date_col else "",
                    is_incremental=is_incremental,
                    download_time_seconds=round(elapsed, 3),
                )

            if raw_new.empty:
                raise ValueError(f"No data returned from Yahoo Finance for {symbol} ({yahoo_ticker})")

            # Flatten MultiIndex columns if present (yfinance >= 0.2.40)
            if isinstance(raw_new.columns, pd.MultiIndex):
                raw_new.columns = [col[0] for col in raw_new.columns]

            raw_new = raw_new.reset_index()

            # ---- Merge with existing if incremental ----
            if is_incremental and existing_df is not None and not existing_df.empty:
                # Standardise column names for concatenation
                raw_new.columns = [str(c).strip().lower().replace(" ", "_") for c in raw_new.columns]
                combined = pd.concat([existing_df, raw_new], ignore_index=True)
            else:
                combined = raw_new

            # ---- Audit & clean ----
            cleaned_df, _report = audit_and_clean_ohlcv(combined, symbol=symbol)

            # Deduplicate by date
            date_col = next(
                (c for c in cleaned_df.columns if c in ("date", "timestamp", "datetime")),
                None,
            )
            if date_col:
                cleaned_df = (
                    cleaned_df
                    .drop_duplicates(subset=[date_col], keep="last")
                    .sort_values(by=date_col)
                    .reset_index(drop=True)
                )

            # ---- Save raw + cleaned ----
            self.storage.save_parquet(
                symbol=symbol,
                df=combined if not is_incremental else cleaned_df,
                stage="raw",
                dataset_type="ohlcv",
                source="Yahoo Finance",
            )
            self.storage.save_parquet(
                symbol=symbol,
                df=cleaned_df,
                stage="cleaned",
                dataset_type="ohlcv",
                source="Yahoo Finance",
            )

            # ---- Corporate actions & adjustments ----
            time.sleep(self.rate_limit_seconds)
            corp_actions = fetch_corporate_actions(symbol, yahoo_ticker=yahoo_ticker)

            result = compute_adjusted_series(cleaned_df, corp_actions)

            adj_df = result["adjusted"]
            tr_df = result["total_return"]
            actions_applied = result["actions_applied"]

            # Validate
            validation = validate_adjustments(cleaned_df, adj_df)
            if not validation["is_valid"]:
                logger.warning(
                    "Adjustment validation issues for %s: %s",
                    symbol,
                    validation["issues"],
                )

            # ---- Persist adjusted layers ----
            self.storage.save_parquet(
                symbol=symbol,
                df=adj_df,
                stage="adjusted",
                dataset_type="ohlcv",
                source="Yahoo Finance",
            )
            self.storage.save_parquet(
                symbol=symbol,
                df=tr_df,
                stage="derived",
                dataset_type="total_return",
                source="Yahoo Finance",
            )

            # Save corporate actions as a small DataFrame
            if actions_applied:
                ca_df = pd.DataFrame(actions_applied)
                # Ensure a date column for storage compatibility
                ca_df["date"] = ca_df["ex_date"]
                self.storage.save_parquet(
                    symbol=symbol,
                    df=ca_df,
                    stage="derived",
                    dataset_type="corporate_actions",
                    source="Yahoo Finance",
                )

            # ---- Build result ----
            rec_count = len(cleaned_df)
            s_date = str(cleaned_df[date_col].min())[:10] if date_col and rec_count else ""
            e_date = str(cleaned_df[date_col].max())[:10] if date_col and rec_count else ""
            elapsed = time.monotonic() - t0

            return DownloadResult(
                symbol=symbol,
                success=True,
                records=rec_count,
                start_date=s_date,
                end_date=e_date,
                is_incremental=is_incremental,
                download_time_seconds=round(elapsed, 3),
            )

        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("Failed to download %s: %s", symbol, exc)
            return DownloadResult(
                symbol=symbol,
                success=False,
                error=str(exc),
                is_incremental=is_incremental,
                download_time_seconds=round(elapsed, 3),
            )

    # -----------------------------------------------------------------
    # Batch download
    # -----------------------------------------------------------------

    def download_batch(
        self,
        symbols: list[str],
        period: str = "10y",
        incremental: bool = True,
        progress_callback: Callable | None = None,
    ) -> BatchDownloadSummary:
        """Download historical data for multiple symbols sequentially.

        Each symbol is processed independently — one failure never stops
        the batch.  An optional *progress_callback* is invoked after
        every symbol with ``(current_index, total, symbol, result)``.

        Returns
        -------
        BatchDownloadSummary
        """
        t0 = time.monotonic()
        total = len(symbols)
        summary = BatchDownloadSummary(total_requested=total)

        for idx, symbol in enumerate(symbols):
            result = self.download_single(
                symbol=symbol,
                period=period,
                incremental=incremental,
            )

            if result.success:
                summary.successful += 1
                summary.total_records += result.records
            else:
                summary.failed += 1

            summary.results.append(result.to_dict())

            if progress_callback is not None:
                try:
                    progress_callback(idx, total, symbol, result)
                except Exception:
                    pass  # never let a callback crash the batch

            # Rate-limit between symbols (download_single already sleeps
            # before its own yfinance calls, but an extra pause between
            # symbols keeps us well within limits).
            if idx < total - 1:
                time.sleep(self.rate_limit_seconds)

        summary.elapsed_seconds = round(time.monotonic() - t0, 3)
        return summary

    # -----------------------------------------------------------------
    # Coverage inspection
    # -----------------------------------------------------------------

    def get_coverage_detail(self) -> list[dict]:
        """Return per-instrument coverage details by scanning Parquet files.

        For each symbol with cleaned data:
        ``first_date``, ``last_date``, ``total_sessions``,
        ``missing_sessions_estimate``, ``has_adjusted``, ``has_total_return``,
        ``has_corporate_actions``, ``file_size_kb``.
        """
        coverage: list[dict] = []

        cleaned_dir = self.storage.cleaned_dir / "ohlcv"
        if not cleaned_dir.exists():
            return coverage

        for pq_file in sorted(cleaned_dir.glob("*.parquet")):
            symbol_stem = pq_file.stem  # e.g. RELIANCE or IDX_NSEI
            # Reverse the storage sanitisation for display
            display_symbol = symbol_stem.replace("IDX_", "^").replace("_", ".")

            try:
                df = pd.read_parquet(pq_file, engine="pyarrow")
            except Exception:
                continue

            date_col = next(
                (c for c in df.columns if c in ("date", "timestamp", "datetime")),
                None,
            )
            if date_col is None or df.empty:
                continue

            dates = pd.to_datetime(df[date_col])
            first_date = str(dates.min())[:10]
            last_date = str(dates.max())[:10]
            total_sessions = len(df)

            # Rough estimate of missing sessions: calendar business days
            # minus actual sessions (a quick heuristic, not holiday-aware).
            bdays = len(pd.bdate_range(dates.min(), dates.max()))
            missing_sessions_estimate = max(0, bdays - total_sessions)

            # Check for adjusted / total_return / corporate_actions
            has_adjusted = (
                self.storage.load_parquet(display_symbol, stage="adjusted", dataset_type="ohlcv")
                is not None
            )
            has_total_return = (
                self.storage.load_parquet(display_symbol, stage="derived", dataset_type="total_return")
                is not None
            )
            has_corporate_actions = (
                self.storage.load_parquet(display_symbol, stage="derived", dataset_type="corporate_actions")
                is not None
            )

            file_size_kb = round(pq_file.stat().st_size / 1024, 2)

            coverage.append({
                "symbol": display_symbol,
                "first_date": first_date,
                "last_date": last_date,
                "total_sessions": total_sessions,
                "missing_sessions_estimate": missing_sessions_estimate,
                "has_adjusted": has_adjusted,
                "has_total_return": has_total_return,
                "has_corporate_actions": has_corporate_actions,
                "file_size_kb": file_size_kb,
            })

        return coverage
