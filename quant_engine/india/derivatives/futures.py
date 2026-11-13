"""AMQUANT INDIA - Historical Futures Data Pipeline & Continuous Series Builder.

Features:
1. Contract-specific historical storage (OHLCV + Open Interest).
2. Expiry-aware contract selection: Near-month (I), Next-month (II), Far-month (III).
3. Rollover date handling (e.g., N days prior to expiry, or on expiry session).
4. Continuous Futures Series Generation:
   - UNADJUSTED_CALENDAR (stitching front month with raw prices)
   - BACK_ADJUSTED_DIFFERENCE (additive roll spread adjustment)
   - RATIO_ADJUSTED (Panama Canal multiplicative ratio adjustment)
5. Strict Invariant: Continuous futures series carries is_continuous = True and
   an explicit warning: "Never treat a continuous futures series as an executable contract."
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal
import numpy as np
import pandas as pd

RolloverMethod = Literal["UNADJUSTED_CALENDAR", "BACK_ADJUSTED_DIFFERENCE", "RATIO_ADJUSTED"]


@dataclass
class RolloverEvent:
    roll_date: str
    from_contract: str
    to_contract: str
    near_close: float
    next_close: float
    roll_spread: float  # next_close - near_close
    ratio: float  # next_close / near_close

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContinuousFuturesResult:
    underlying: str
    method: RolloverMethod
    is_continuous: bool
    execution_disclaimer: str
    total_bars: int
    start_date: str
    end_date: str
    rollover_events: list[RolloverEvent]
    series: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["rollover_events"] = [e.to_dict() if isinstance(e, RolloverEvent) else e for e in self.rollover_events]
        return res


class ContinuousFuturesBuilder:
    """Builds continuous historical futures time series across sequential contract cycles."""

    DISCLAIMER = (
        "IMPORTANT: Continuous futures series is an analytical research construct. "
        "Never treat a continuous futures series as an executable contract. "
        "Real trading execution and actual backtest fills must map strictly to individual contract series."
    )

    def __init__(
        self,
        method: RolloverMethod = "BACK_ADJUSTED_DIFFERENCE",
        roll_days_before_expiry: int = 1,
    ):
        self.method = method
        self.roll_days_before_expiry = roll_days_before_expiry

    def build_continuous_series(
        self,
        underlying: str,
        contracts_data: dict[str, pd.DataFrame],  # {contract_symbol: df} with columns date, open, high, low, close, volume, oi, expiry_date
    ) -> ContinuousFuturesResult:
        """Construct continuous futures series from multiple contract time series."""
        if not contracts_data:
            raise ValueError(f"No futures contract data provided for underlying {underlying}")

        # Sort contracts by expiry date
        sorted_contracts: list[tuple[str, str, pd.DataFrame]] = []
        for symbol, df in contracts_data.items():
            if df.empty:
                continue
            d = df.copy()
            exp_col = next((c for c in d.columns if c in ("expiry_date", "expiry", "last_trading_date")), None)
            exp_val = str(d[exp_col].iloc[0])[:10] if exp_col else ""
            d["date_str"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d")
            d = d.sort_values("date_str").reset_index(drop=True)
            sorted_contracts.append((symbol, exp_val, d))

        sorted_contracts.sort(key=lambda x: x[1])

        if not sorted_contracts:
            raise ValueError(f"No valid contract data remained for underlying {underlying}")

        if len(sorted_contracts) == 1:
            sym, exp_date, df_single = sorted_contracts[0]
            records = df_single.to_dict(orient="records")
            return ContinuousFuturesResult(
                underlying=underlying,
                method=self.method,
                is_continuous=True,
                execution_disclaimer=self.DISCLAIMER,
                total_bars=len(records),
                start_date=records[0]["date_str"],
                end_date=records[-1]["date_str"],
                rollover_events=[],
                series=records,
            )

        # ─────────────────────────────────────────────────────────────
        # Multi-Contract Rollover Stitching
        # ─────────────────────────────────────────────────────────────
        rollover_events: list[RolloverEvent] = []
        stitched_slices: list[pd.DataFrame] = []

        for idx in range(len(sorted_contracts) - 1):
            curr_sym, curr_exp, curr_df = sorted_contracts[idx]
            next_sym, next_exp, next_df = sorted_contracts[idx + 1]

            # Determine roll date: roll_days_before_expiry trading sessions before curr_exp
            common_dates = sorted(list(set(curr_df["date_str"]).intersection(set(next_df["date_str"]))))
            if not common_dates:
                # If no overlap, stitch at end of current contract
                roll_date = curr_df["date_str"].max()
            else:
                roll_idx = max(0, len(common_dates) - 1 - self.roll_days_before_expiry)
                roll_date = common_dates[roll_idx]

            curr_row = curr_df[curr_df["date_str"] == roll_date]
            next_row = next_df[next_df["date_str"] == roll_date]

            if not curr_row.empty and not next_row.empty:
                p_near = float(curr_row["close"].iloc[0])
                p_next = float(next_row["close"].iloc[0])
                spread = p_next - p_near
                ratio = p_next / p_near if p_near > 0 else 1.0
            else:
                p_near = float(curr_df["close"].iloc[-1])
                p_next = float(next_df["close"].iloc[0])
                spread = p_next - p_near
                ratio = p_next / p_near if p_near > 0 else 1.0

            rollover_events.append(
                RolloverEvent(
                    roll_date=roll_date,
                    from_contract=curr_sym,
                    to_contract=next_sym,
                    near_close=round(p_near, 2),
                    next_close=round(p_next, 2),
                    roll_spread=round(spread, 2),
                    ratio=round(ratio, 4),
                )
            )

            # Slice current contract up to roll_date
            slice_df = curr_df[curr_df["date_str"] <= roll_date].copy()
            slice_df["active_contract"] = curr_sym
            stitched_slices.append(slice_df)

        # Final contract slice from last roll_date onward
        last_sym, _, last_df = sorted_contracts[-1]
        last_roll = rollover_events[-1].roll_date
        final_slice = last_df[last_df["date_str"] > last_roll].copy()
        final_slice["active_contract"] = last_sym
        stitched_slices.append(final_slice)

        # Concatenate stitched pieces
        combined = pd.concat(stitched_slices, ignore_index=True).drop_duplicates(subset=["date_str"]).reset_index(drop=True)

        # ─────────────────────────────────────────────────────────────
        # Adjustment Methodologies
        # ─────────────────────────────────────────────────────────────
        if self.method == "UNADJUSTED_CALENDAR":
            pass  # Raw unadjusted stitched quotes

        elif self.method == "BACK_ADJUSTED_DIFFERENCE":
            # Accumulate cumulative spreads backwards from the latest contract
            cum_spread = 0.0
            for event in reversed(rollover_events):
                cum_spread += event.roll_spread
                mask = combined["date_str"] <= event.roll_date
                for col in ["open", "high", "low", "close"]:
                    if col in combined.columns:
                        combined.loc[mask, col] = np.round(combined.loc[mask, col] + cum_spread, 2)

        elif self.method == "RATIO_ADJUSTED":
            # Multiplicative adjustment backwards
            cum_ratio = 1.0
            for event in reversed(rollover_events):
                cum_ratio *= event.ratio
                mask = combined["date_str"] <= event.roll_date
                for col in ["open", "high", "low", "close"]:
                    if col in combined.columns:
                        combined.loc[mask, col] = np.round(combined.loc[mask, col] * cum_ratio, 2)

        records = combined.to_dict(orient="records")
        return ContinuousFuturesResult(
            underlying=underlying,
            method=self.method,
            is_continuous=True,
            execution_disclaimer=self.DISCLAIMER,
            total_bars=len(records),
            start_date=records[0]["date_str"],
            end_date=records[-1]["date_str"],
            rollover_events=rollover_events,
            series=records,
        )

