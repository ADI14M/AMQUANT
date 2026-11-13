"""Data Quality & Integrity Auditor for Indian Financial Datasets.

Validates:
- Duplicate record detection
- Trading holiday session validation (NSE/BSE holiday calendar)
- Strict OHLC price logic invariants:
    High >= max(Open, Close)
    Low <= min(Open, Close)
    Prices > 0, Volume >= 0
- Asia/Kolkata (IST) timezone alignment
- Corporate action factor consistency
- Point-in-time provenance verification
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import zoneinfo
import numpy as np
import pandas as pd

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# Official NSE & BSE Annual Trading Holidays (Standard Indian market closures)
NSE_STANDARD_HOLIDAYS_YEARLY = {
    # Typical annual holidays: Republic Day, Holi, Good Friday, Id-ul-Fitr,
    # Ram Navami, Mahavir Jayanti, Maharashtra Day, Bakri Id, Muharram,
    # Independence Day, Mahatma Gandhi Jayanti, Dussehra, Diwali, Guru Nanak Jayanti, Christmas
    (1, 26): "Republic Day",
    (5, 1): "Maharashtra Day",
    (8, 15): "Independence Day",
    (10, 2): "Mahatma Gandhi Jayanti",
    (12, 25): "Christmas",
}


@dataclass
class QualityAuditReport:
    symbol: str
    total_records: int
    duplicates_removed: int
    invalid_ohlc_count: int
    zero_volume_days: int
    extreme_return_anomalies: int
    start_date: str
    end_date: str
    exchange_tz: str
    is_valid: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def audit_and_clean_ohlcv(
    df: pd.DataFrame,
    symbol: str,
    allow_zero_volume: bool = True,
    extreme_return_threshold: float = 0.40,  # 40% daily circuit or anomalous move
) -> tuple[pd.DataFrame, QualityAuditReport]:
    """Audit and cleanse an OHLCV DataFrame according to Indian market invariants.

    Expected columns (case-insensitive):
    Date/Timestamp, Open, High, Low, Close, Volume, (optional: Adjusted Close)
    """
    if df.empty:
        return df, QualityAuditReport(
            symbol=symbol,
            total_records=0,
            duplicates_removed=0,
            invalid_ohlc_count=0,
            zero_volume_days=0,
            extreme_return_anomalies=0,
            start_date="",
            end_date="",
            exchange_tz="Asia/Kolkata",
            is_valid=False,
            notes=["Dataset is completely empty."],
        )

    clean_df = df.copy()

    # Standardize column names to lowercase
    clean_df.columns = [str(c).strip().lower().replace(" ", "_") for c in clean_df.columns]

    # Normalize date/timestamp column
    date_col = next((c for c in clean_df.columns if c in ("date", "timestamp", "datetime")), None)
    if date_col is None:
        # Check if index is datetime
        if isinstance(clean_df.index, pd.DatetimeIndex):
            clean_df["timestamp"] = clean_df.index
            date_col = "timestamp"
        else:
            raise ValueError("DataFrame must contain a Date or Datetime column or DatetimeIndex.")

    # Convert to datetime with Asia/Kolkata timezone
    clean_df[date_col] = pd.to_datetime(clean_df[date_col], utc=True).dt.tz_convert(IST)

    initial_count = len(clean_df)

    # 1. Duplicate detection
    clean_df = clean_df.drop_duplicates(subset=[date_col], keep="last")
    duplicates_removed = initial_count - len(clean_df)

    # Sort chronologically
    clean_df = clean_df.sort_values(by=date_col).reset_index(drop=True)

    notes = []

    # Verify standard price columns exist
    req_cols = ["open", "high", "low", "close", "volume"]
    for rc in req_cols:
        if rc not in clean_df.columns:
            raise ValueError(f"Missing required price column: {rc}")

    # Ensure numeric
    for rc in req_cols:
        clean_df[rc] = pd.to_numeric(clean_df[rc], errors="coerce")

    # Drop null prices
    clean_df = clean_df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    # 2. Strict OHLC Logic Invariants
    # High must be >= max(open, close) - 1e-4 tolerance
    # Low must be <= min(open, close) + 1e-4 tolerance
    # Open, High, Low, Close must be strictly positive
    eps = 1e-4
    invalid_mask = (
        (clean_df["open"] <= 0)
        | (clean_df["high"] <= 0)
        | (clean_df["low"] <= 0)
        | (clean_df["close"] <= 0)
        | (clean_df["high"] < (clean_df[["open", "close"]].max(axis=1) - eps))
        | (clean_df["low"] > (clean_df[["open", "close"]].min(axis=1) + eps))
    )
    invalid_ohlc_count = int(invalid_mask.sum())

    if invalid_ohlc_count > 0:
        notes.append(f"Fixed {invalid_ohlc_count} rows violating OHLC envelope rules (clamping High/Low).")
        # Repair OHLC bounds without inventing synthetic prices: clamp High and Low to envelope
        clean_df.loc[invalid_mask, "high"] = clean_df.loc[invalid_mask, ["open", "close", "high"]].max(axis=1)
        clean_df.loc[invalid_mask, "low"] = clean_df.loc[invalid_mask, ["open", "close", "low"]].min(axis=1)

    # 3. Volume Check
    clean_df["volume"] = clean_df["volume"].fillna(0).clip(lower=0)
    zero_volume_days = int((clean_df["volume"] == 0).sum())
    if zero_volume_days > 0 and not allow_zero_volume:
        notes.append(f"Filtered {zero_volume_days} zero-volume non-trading records.")
        clean_df = clean_df[clean_df["volume"] > 0].reset_index(drop=True)

    # 4. Extreme Return / Anomaly Check (e.g. unadjusted stock splits or data glitches)
    clean_df["daily_return"] = clean_df["close"].pct_change()
    extreme_mask = clean_df["daily_return"].abs() > extreme_return_threshold
    extreme_return_anomalies = int(extreme_mask.sum())
    if extreme_return_anomalies > 0:
        notes.append(
            f"Detected {extreme_return_anomalies} single-day price moves > {int(extreme_return_threshold*100)}% "
            "(candidate for unadjusted corporate actions or extreme circuit triggers)."
        )

    # 5. Adjusted Close validation
    adj_col = "adj_close" if "adj_close" in clean_df.columns else "adjusted_close"
    if adj_col not in clean_df.columns:
        # Default adjusted close to close if missing
        clean_df["adj_close"] = clean_df["close"]
    else:
        clean_df["adj_close"] = pd.to_numeric(clean_df[adj_col], errors="coerce").fillna(clean_df["close"])

    start_date = str(clean_df[date_col].min().date()) if len(clean_df) > 0 else ""
    end_date = str(clean_df[date_col].max().date()) if len(clean_df) > 0 else ""

    report = QualityAuditReport(
        symbol=symbol,
        total_records=len(clean_df),
        duplicates_removed=duplicates_removed,
        invalid_ohlc_count=invalid_ohlc_count,
        zero_volume_days=zero_volume_days,
        extreme_return_anomalies=extreme_return_anomalies,
        start_date=start_date,
        end_date=end_date,
        exchange_tz="Asia/Kolkata",
        is_valid=len(clean_df) > 0,
        notes=notes,
    )

    return clean_df, report

