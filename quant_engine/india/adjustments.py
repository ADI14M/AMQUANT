"""Corporate Action Price Adjustments for AMQUANT INDIA.

Handles stock splits, bonus issues, cash dividends, rights issues,
symbol changes, and total return series computation.

Backward-adjusts raw OHLCV prices and volumes so that the most recent
price is always the unadjusted market price and historical prices are
scaled down by cumulative split/bonus factors.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger("amquant.india.adjustments")

CorporateActionType = Literal[
    "SPLIT", "BONUS", "DIVIDEND", "RIGHTS", "SYMBOL_CHANGE"
]


@dataclass
class CorporateAction:
    """A single corporate action event for an Indian equity."""

    symbol: str
    action_type: CorporateActionType
    ex_date: str  # ISO date string, e.g. '2023-09-15'
    ratio: float = 1.0  # split/bonus ratio (e.g. 2.0 for 2:1 split)
    dividend_amount: float = 0.0  # cash dividend per share in INR
    old_symbol: str = ""  # for SYMBOL_CHANGE actions
    new_symbol: str = ""
    source: str = "Yahoo Finance"
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Fetching corporate actions from Yahoo Finance
# ---------------------------------------------------------------------------


def fetch_corporate_actions(
    symbol: str,
    yahoo_ticker: str = "",
) -> list[CorporateAction]:
    """Fetch splits and dividends from yfinance for a given symbol.

    Uses ``yf.Ticker(ticker).splits`` and ``yf.Ticker(ticker).dividends``
    to build a list of :class:`CorporateAction` instances.

    Parameters
    ----------
    symbol:
        Canonical AMQUANT symbol (e.g. ``'RELIANCE'``).
    yahoo_ticker:
        Override Yahoo ticker string.  When empty the function resolves
        the ticker from the universe catalog, falling back to
        ``SYMBOL.NS``.

    Returns
    -------
    list[CorporateAction]
        Sorted by ``ex_date`` ascending.
    """
    if not yahoo_ticker:
        # Lazy import to avoid circular dependency at module level
        from quant_engine.india.universe import get_instrument

        inst = get_instrument(symbol)
        yahoo_ticker = inst.yahoo_ticker if inst and inst.yahoo_ticker else f"{symbol.strip().upper()}.NS"

    actions: list[CorporateAction] = []
    try:
        ticker = yf.Ticker(yahoo_ticker)

        # --- Splits ---
        time.sleep(0.25)
        splits = ticker.splits
        if splits is not None and not splits.empty:
            for dt, ratio in splits.items():
                ex_date_str = pd.Timestamp(dt).strftime("%Y-%m-%d")
                actions.append(
                    CorporateAction(
                        symbol=symbol,
                        action_type="SPLIT",
                        ex_date=ex_date_str,
                        ratio=float(ratio),
                        source="Yahoo Finance",
                        notes=f"Split ratio {ratio}:1",
                    )
                )

        # --- Dividends ---
        time.sleep(0.25)
        dividends = ticker.dividends
        if dividends is not None and not dividends.empty:
            for dt, amount in dividends.items():
                ex_date_str = pd.Timestamp(dt).strftime("%Y-%m-%d")
                actions.append(
                    CorporateAction(
                        symbol=symbol,
                        action_type="DIVIDEND",
                        ex_date=ex_date_str,
                        dividend_amount=float(amount),
                        source="Yahoo Finance",
                        notes=f"Cash dividend ₹{amount:.2f}/share",
                    )
                )

    except Exception as exc:
        logger.warning(
            "Could not fetch corporate actions for %s (%s): %s",
            symbol,
            yahoo_ticker,
            exc,
        )

    # Sort chronologically
    actions.sort(key=lambda a: a.ex_date)
    return actions


# ---------------------------------------------------------------------------
# Computing adjusted price series
# ---------------------------------------------------------------------------


def compute_adjusted_series(
    raw_df: pd.DataFrame,
    actions: list[CorporateAction],
) -> dict:
    """Backward-adjust raw OHLCV prices and compute a total return index.

    Parameters
    ----------
    raw_df:
        Raw OHLCV DataFrame with columns ``date``, ``open``, ``high``,
        ``low``, ``close``, ``volume`` (at minimum).
    actions:
        List of :class:`CorporateAction` instances for this symbol.

    Returns
    -------
    dict with keys:
        - ``'adjusted'``: pd.DataFrame — adjusted OHLCV
        - ``'total_return'``: pd.DataFrame — date + ``tr_index`` columns
        - ``'actions_applied'``: list[dict] — serialised actions used
        - ``'adjustment_factors'``: pd.DataFrame — date + ``cum_factor``
    """
    df = raw_df.copy()

    # Identify the date column
    date_col = next(
        (c for c in df.columns if c in ("date", "timestamp", "datetime")),
        None,
    )
    if date_col is None:
        raise ValueError("DataFrame must contain a 'date', 'timestamp', or 'datetime' column.")

    # Normalize date_col so comparison doesn't fail on tz-aware vs tz-naive
    if hasattr(df[date_col].dt, "tz") and df[date_col].dt.tz is not None:
        df[date_col] = df[date_col].dt.tz_localize(None)
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(by=date_col).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 1. Cumulative split/bonus adjustment factor (backward adjustment)
    #    For each date t:
    #        CF_t = product of all split ratios where ex_date > t
    #    P_adj = P_raw / CF_t
    #    V_adj = V_raw * CF_t
    # ------------------------------------------------------------------
    split_actions = [
        a for a in actions if a.action_type in ("SPLIT", "BONUS") and a.ratio != 1.0
    ]

    # Build a cumulative factor series aligned to df dates
    cum_factor = np.ones(len(df), dtype=np.float64)

    for action in split_actions:
        ex_date = pd.Timestamp(action.ex_date)
        # All dates strictly before the ex_date get multiplied by the ratio
        mask = df[date_col] < ex_date
        cum_factor[mask.values] *= action.ratio

    factor_df = pd.DataFrame({
        "date": df[date_col].values,
        "cum_factor": cum_factor,
    })

    # Adjusted OHLCV
    adj_df = df.copy()
    price_cols = ["open", "high", "low", "close"]
    available_price_cols = [c for c in price_cols if c in adj_df.columns]

    for col in available_price_cols:
        adj_df[col] = adj_df[col].astype(np.float64) / cum_factor

    if "volume" in adj_df.columns:
        adj_df["volume"] = (adj_df["volume"].astype(np.float64) * cum_factor).astype(np.int64)

    # Also adjust adj_close if present
    if "adj_close" in adj_df.columns:
        adj_df["adj_close"] = adj_df["adj_close"].astype(np.float64) / cum_factor

    # ------------------------------------------------------------------
    # 2. Total return index incorporating cash dividends
    #    TR_0 = P_adj_0
    #    R_TR_t = (P_adj_t + D_t - P_adj_{t-1}) / P_adj_{t-1}
    #    TR_t  = TR_{t-1} * (1 + R_TR_t)
    # ------------------------------------------------------------------
    dividend_actions = [a for a in actions if a.action_type == "DIVIDEND"]

    # Map ex_date -> total dividend on that date (already in per-share INR)
    dividend_map: dict[str, float] = {}
    for a in dividend_actions:
        dividend_map[a.ex_date] = dividend_map.get(a.ex_date, 0.0) + a.dividend_amount

    adj_close = adj_df["close"].values.astype(np.float64)
    dates = df[date_col].values

    tr_index = np.empty(len(adj_close), dtype=np.float64)
    tr_index[0] = adj_close[0]

    for i in range(1, len(adj_close)):
        date_str = pd.Timestamp(dates[i]).strftime("%Y-%m-%d")
        div = dividend_map.get(date_str, 0.0)

        prev_price = adj_close[i - 1]
        if prev_price > 0:
            r_tr = (adj_close[i] + div - prev_price) / prev_price
        else:
            r_tr = 0.0

        tr_index[i] = tr_index[i - 1] * (1.0 + r_tr)

    tr_df = pd.DataFrame({
        "date": dates,
        "tr_index": tr_index,
    })

    actions_applied = [a.to_dict() for a in actions]

    return {
        "adjusted": adj_df,
        "total_return": tr_df,
        "actions_applied": actions_applied,
        "adjustment_factors": factor_df,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_adjustments(
    raw_df: pd.DataFrame,
    adjusted_df: pd.DataFrame,
) -> dict:
    """Verify adjustment quality.

    Checks performed:
    - **Turnover preservation**: ``P_raw × V_raw ≈ P_adj × V_adj``
      (within 0.01 % tolerance).
    - No NaN or negative prices in the adjusted series.
    - Dates are monotonically increasing.
    - Volume is non-negative.

    Returns
    -------
    dict
        ``{'is_valid': bool, 'turnover_preserved': bool, 'issues': list[str]}``
    """
    issues: list[str] = []

    # --- NaN / negative price check ---
    price_cols = [c for c in ("open", "high", "low", "close") if c in adjusted_df.columns]
    for col in price_cols:
        nan_count = int(adjusted_df[col].isna().sum())
        if nan_count > 0:
            issues.append(f"Adjusted '{col}' has {nan_count} NaN values.")
        neg_count = int((adjusted_df[col] < 0).sum())
        if neg_count > 0:
            issues.append(f"Adjusted '{col}' has {neg_count} negative values.")

    # --- Volume non-negative ---
    if "volume" in adjusted_df.columns:
        neg_vol = int((adjusted_df["volume"] < 0).sum())
        if neg_vol > 0:
            issues.append(f"Adjusted 'volume' has {neg_vol} negative values.")

    # --- Monotonic dates ---
    date_col = next(
        (c for c in adjusted_df.columns if c in ("date", "timestamp", "datetime")),
        None,
    )
    if date_col:
        dates = pd.to_datetime(adjusted_df[date_col])
        if not dates.is_monotonic_increasing:
            issues.append("Adjusted dates are not monotonically increasing.")

    # --- Turnover preservation ---
    turnover_preserved = True
    if "close" in raw_df.columns and "volume" in raw_df.columns:
        raw_turnover = raw_df["close"].astype(np.float64) * raw_df["volume"].astype(np.float64)
        adj_turnover = adjusted_df["close"].astype(np.float64) * adjusted_df["volume"].astype(np.float64)

        # Compare row-by-row where raw turnover > 0
        mask = raw_turnover > 0
        if mask.any():
            rel_diff = ((adj_turnover[mask] - raw_turnover[mask]).abs() / raw_turnover[mask])
            max_rel_diff = float(rel_diff.max())
            if max_rel_diff > 1e-4:  # 0.01 %
                turnover_preserved = False
                issues.append(
                    f"Turnover preservation violated: max relative diff = {max_rel_diff:.6f} "
                    f"(tolerance 0.0001)."
                )

    is_valid = len(issues) == 0

    return {
        "is_valid": is_valid,
        "turnover_preserved": turnover_preserved,
        "issues": issues,
    }
