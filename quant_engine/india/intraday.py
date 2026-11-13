"""AMQUANT INDIA - Intraday Historical Data Infrastructure.

Features:
1. Supported intervals: 1m, 5m, 15m, 30m, 60m.
2. Exchange Session Validator:
   - Validates Indian market hours (09:15:00 to 15:30:00 IST).
   - Timezone localization to Asia/Kolkata.
   - Pre-market / post-market tick filtering.
   - Standard Indian exchange holidays calendar.
3. Missing Candle Auditor:
   - Computes expected candles per session by interval (1m: 375, 5m: 75, 15m: 25, 30m: 13, 60m: 7).
   - Identifies gaps, missing session counts, and session completeness percentage.
4. Incremental Intraday Downloader & Resumption:
   - Deduplicates by timestamp.
   - Merges delta records with existing Parquet partitions.
   - Preserves provider provenance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time as dtime, timezone
import logging
from typing import Any, Literal
import numpy as np
import pandas as pd

logger = logging.getLogger("amquant.india.intraday")

IntradayInterval = Literal["1m", "5m", "15m", "30m", "60m"]

# Expected number of intraday bars in a standard 375-minute Indian market session (09:15 - 15:30 IST)
EXPECTED_BARS_PER_SESSION: dict[str, int] = {
    "1m": 375,
    "5m": 75,
    "15m": 25,
    "30m": 13,
    "60m": 7,
}

# Standard Indian Trading Session Times (IST)
MARKET_OPEN_TIME = dtime(9, 15, 0)
MARKET_CLOSE_TIME = dtime(15, 30, 0)

# Major Indian Market Holidays (National / Exchange holidays)
STANDARD_INDIAN_HOLIDAYS_2024_2026 = {
    "2024-01-22", "2024-01-26", "2024-03-08", "2024-03-25", "2024-03-29",
    "2024-04-11", "2024-04-17", "2024-05-01", "2024-05-20", "2024-06-17",
    "2024-07-17", "2024-08-15", "2024-10-02", "2024-11-01", "2024-11-15",
    "2024-12-25",
    "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10",
    "2025-04-14", "2025-04-18", "2025-05-01", "2025-08-15", "2025-08-27",
    "2025-10-02", "2025-10-21", "2025-10-22", "2025-11-05", "2025-12-25",
    "2026-01-26", "2026-03-03", "2026-03-20", "2026-04-03", "2026-04-14",
    "2026-05-01", "2026-08-15", "2026-10-02", "2026-10-19", "2026-11-09",
    "2026-12-25",
}


@dataclass
class IntradaySessionAudit:
    date: str
    bars_found: int
    bars_expected: int
    completeness_pct: float
    first_candle_time: str
    last_candle_time: str
    is_complete: bool
    missing_bars_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntradayQualityReport:
    symbol: str
    interval: str
    total_bars: int
    total_sessions: int
    start_timestamp: str
    end_timestamp: str
    overall_completeness_pct: float
    total_missing_bars: int
    duplicate_bars_removed: int
    out_of_session_bars_filtered: int
    sessions_audit: list[IntradaySessionAudit]
    provider: str

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["sessions_audit"] = [s.to_dict() if isinstance(s, IntradaySessionAudit) else s for s in self.sessions_audit]
        return res


class ExchangeSessionValidator:
    """Validates that intraday timestamps conform strictly to Indian exchange operating hours."""

    def __init__(self, holidays: set[str] | None = None):
        self.holidays = holidays or STANDARD_INDIAN_HOLIDAYS_2024_2026

    def is_trading_day(self, dt: datetime | pd.Timestamp) -> bool:
        """Check if date is Monday-Friday and not a declared exchange holiday."""
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        date_str = dt.strftime("%Y-%m-%d")
        return date_str not in self.holidays

    def is_in_market_hours(self, dt: datetime | pd.Timestamp) -> bool:
        """Verify timestamp falls strictly between 09:15:00 and 15:30:00 IST."""
        t = dt.time()
        return MARKET_OPEN_TIME <= t <= MARKET_CLOSE_TIME

    def normalize_and_filter_session(
        self,
        df: pd.DataFrame,
        time_column: str = "datetime",
    ) -> tuple[pd.DataFrame, int, int]:
        """Normalize timezone to Asia/Kolkata, filter out-of-session ticks and drop duplicates.

        Returns:
            (cleaned_df, duplicates_dropped, out_of_session_dropped)
        """
        if df.empty:
            return df, 0, 0

        d = df.copy()
        target_col = None
        for col in [time_column, "Datetime", "date", "Date", "timestamp"]:
            if col in d.columns:
                target_col = col
                break

        if not target_col:
            raise ValueError(f"No timestamp column found. Looked for {time_column}, Datetime, date, timestamp")

        # Convert to datetime and localize to Asia/Kolkata
        ts = pd.to_datetime(d[target_col])
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("Asia/Kolkata")
        else:
            ts = ts.dt.tz_convert("Asia/Kolkata")

        d["datetime_ist"] = ts
        d["date_ist"] = ts.dt.strftime("%Y-%m-%d")
        d["time_ist"] = ts.dt.time

        initial_len = len(d)

        # 1. Deduplicate by exact timestamp
        d = d.drop_duplicates(subset=["datetime_ist"]).sort_values("datetime_ist").reset_index(drop=True)
        duplicates_dropped = initial_len - len(d)

        # 2. Filter out-of-session bars (before 09:15, after 15:30, or weekend)
        before_session_filter = len(d)
        mask = (
            (d["time_ist"] >= MARKET_OPEN_TIME)
            & (d["time_ist"] <= MARKET_CLOSE_TIME)
            & (d["datetime_ist"].dt.weekday < 5)
        )
        d = d[mask].reset_index(drop=True)
        out_of_session_dropped = before_session_filter - len(d)

        # Clean column naming: format datetime_ist as ISO string
        d["datetime"] = d["datetime_ist"].dt.strftime("%Y-%m-%d %H:%M:%S")

        return d, duplicates_dropped, out_of_session_dropped


class MissingCandleAuditor:
    """Audits intraday time series for missing candles and session gaps."""

    def __init__(self, interval: IntradayInterval = "5m"):
        self.interval = interval
        self.expected_bars = EXPECTED_BARS_PER_SESSION.get(interval, 75)

    def audit(
        self,
        df: pd.DataFrame,
        symbol: str,
        provider: str = "Yahoo Finance",
        duplicates_removed: int = 0,
        out_of_session_filtered: int = 0,
    ) -> IntradayQualityReport:
        """Analyze completeness and gaps per trading session."""
        if df.empty:
            return IntradayQualityReport(
                symbol=symbol,
                interval=self.interval,
                total_bars=0,
                total_sessions=0,
                start_timestamp="",
                end_timestamp="",
                overall_completeness_pct=0.0,
                total_missing_bars=0,
                duplicate_bars_removed=duplicates_removed,
                out_of_session_bars_filtered=out_of_session_filtered,
                sessions_audit=[],
                provider=provider,
            )

        d = df.copy()
        if "date_ist" not in d.columns:
            ts = pd.to_datetime(d["datetime"])
            d["date_ist"] = ts.dt.strftime("%Y-%m-%d")

        sessions: list[IntradaySessionAudit] = []
        total_missing = 0
        total_expected = 0

        grouped = d.groupby("date_ist")
        for date_str, grp in grouped:
            bars_count = len(grp)
            missing = max(0, self.expected_bars - bars_count)
            total_missing += missing
            total_expected += self.expected_bars

            comp_pct = round((bars_count / self.expected_bars) * 100.0, 1)
            comp_pct = min(100.0, comp_pct)

            first_t = str(grp["datetime"].min())[-8:]
            last_t = str(grp["datetime"].max())[-8:]

            sessions.append(
                IntradaySessionAudit(
                    date=date_str,
                    bars_found=bars_count,
                    bars_expected=self.expected_bars,
                    completeness_pct=comp_pct,
                    first_candle_time=first_t,
                    last_candle_time=last_t,
                    is_complete=bars_count >= self.expected_bars,
                    missing_bars_count=missing,
                )
            )

        overall_comp = round((len(d) / max(1, total_expected)) * 100.0, 2)
        overall_comp = min(100.0, overall_comp)

        return IntradayQualityReport(
            symbol=symbol,
            interval=self.interval,
            total_bars=len(d),
            total_sessions=len(sessions),
            start_timestamp=str(d["datetime"].min()),
            end_timestamp=str(d["datetime"].max()),
            overall_completeness_pct=overall_comp,
            total_missing_bars=total_missing,
            duplicate_bars_removed=duplicates_removed,
            out_of_session_bars_filtered=out_of_session_filtered,
            sessions_audit=sessions,
            provider=provider,
        )


def merge_incremental_intraday(
    existing_df: pd.DataFrame | None,
    new_df: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Merge newly fetched intraday candles with existing historical dataset.

    Returns:
        (merged_df, new_records_added_count)
    """
    if existing_df is None or existing_df.empty:
        cleaned = new_df.copy()
        if "datetime" in cleaned.columns:
            cleaned["datetime"] = pd.to_datetime(cleaned["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        cleaned = cleaned.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
        return cleaned, len(cleaned)

    if new_df.empty:
        return existing_df, 0

    combined = pd.concat([existing_df, new_df], ignore_index=True)
    if "datetime" in combined.columns:
        combined["datetime"] = pd.to_datetime(combined["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    deduped = combined.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)

    new_added = len(deduped) - len(existing_df)
    return deduped, max(0, new_added)

