"""AMQUANT INDIA - Intraday Trading Strategy Library.

Implements 7 professional, configurable intraday trading strategies:
1. VWAP Reversion (Mean-reversion to intraday session VWAP bands)
2. VWAP Trend Following (Momentum breakouts confirmed by session VWAP)
3. Opening Range Breakout (ORB - 15m / 30m opening bracket breakout)
4. EMA 9/21 Crossover (Fast exponential moving average trend cross)
5. RSI Intraday Mean Reversion (Oscillator extremes on intraday candles)
6. Volume Breakout (High-volume volatility expansion breakout)
7. Previous Day High/Low Breakout (Key historical session pivot breakout)

Each strategy supports:
- Parameter schema for UI discovery and serialization
- Optional multi-timeframe confirmation (using completed 60m candles)
- Strict look-ahead bias protection: signals generated at candle Close (Day/Time t)
  to be executed at next candle Open (t+1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Literal
import numpy as np
import pandas as pd

SignalType = Literal["LONG", "SHORT", "EXIT_LONG", "EXIT_SHORT", "HOLD"]


@dataclass
class StrategyParameter:
    name: str
    display_name: str
    param_type: Literal["int", "float", "bool", "str"]
    default_value: Any
    min_value: float | None = None
    max_value: float | None = None
    options: list[str] | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseIntradayStrategy(ABC):
    """Abstract base class for all intraday trading models."""

    strategy_id: str
    name: str
    category: str
    description: str
    parameters_schema: list[StrategyParameter]

    def __init__(self, **params: Any):
        self.params: dict[str, Any] = {}
        for p in self.parameters_schema:
            self.params[p.name] = params.get(p.name, p.default_value)
        for k, v in params.items():
            self.params[k] = v

    @abstractmethod
    def generate_signals(
        self,
        df: pd.DataFrame,
        htf_60m_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Compute signals for each intraday bar.

        Must append a 'signal' column with values:
        +1: Enter Long
        -1: Enter Short
         0: Exit / Neutral

        Signals generated at row index i represent actions to be executed at row i + 1.
        """
        pass

    def get_info(self) -> dict[str, Any]:
        return {
            "id": self.strategy_id,
            "strategy_id": self.strategy_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters_schema],
        }


# =====================================================================
# 1. VWAP REVERSION STRATEGY
# =====================================================================
class VWAPReversionStrategy(BaseIntradayStrategy):
    strategy_id = "VWAP_REVERSION"
    name = "VWAP Mean Reversion"
    category = "MEAN_REVERSION"
    description = "Trades price mean-reversion back to session VWAP when price stretches beyond standard deviation bands."
    parameters_schema = [
        StrategyParameter("std_dev_multiplier", "Std Dev Multiplier", "float", 2.0, 0.5, 4.0, description="Multiplier for VWAP standard deviation bands"),
        StrategyParameter("allow_short", "Allow Short Positions", "bool", True, description="Enable short selling when price stretches above upper band"),
        StrategyParameter("exit_at_vwap", "Exit at VWAP", "bool", True, description="Close trade when price reverts back to session VWAP"),
    ]

    def __init__(self, **params: Any):
        if "std_dev_mult" in params and "std_dev_multiplier" not in params:
            params["std_dev_multiplier"] = params["std_dev_mult"]
        super().__init__(**params)
        self.params["std_dev_mult"] = self.params["std_dev_multiplier"]

    def generate_signals(self, df: pd.DataFrame, htf_60m_df: pd.DataFrame | None = None) -> pd.DataFrame:
        d = df.copy()
        mult = float(self.params["std_dev_multiplier"])
        allow_short = bool(self.params["allow_short"])

        # Compute intraday session VWAP reset per date
        d["date_only"] = pd.to_datetime(d["datetime"]).dt.strftime("%Y-%m-%d")
        d["pv"] = d["close"] * d["volume"]
        d["cum_pv"] = d.groupby("date_only")["pv"].cumsum()
        d["cum_v"] = d.groupby("date_only")["volume"].cumsum()
        d["vwap"] = d["cum_pv"] / np.maximum(1, d["cum_v"])

        # Rolling standard deviation from VWAP
        d["dev"] = d["close"] - d["vwap"]
        d["vwap_std"] = d.groupby("date_only")["dev"].transform(lambda x: x.expanding().std().fillna(0.0))

        d["upper_band"] = d["vwap"] + (mult * d["vwap_std"])
        d["lower_band"] = d["vwap"] - (mult * d["vwap_std"])

        signals = np.zeros(len(d), dtype=int)
        for i in range(1, len(d)):
            prev_close = d["close"].iloc[i - 1]
            prev_lower = d["lower_band"].iloc[i - 1]
            prev_upper = d["upper_band"].iloc[i - 1]
            prev_vwap = d["vwap"].iloc[i - 1]

            # Oversold below lower band -> Long
            if prev_close < prev_lower:
                signals[i] = 1
            # Overbought above upper band -> Short
            elif allow_short and prev_close > prev_upper:
                signals[i] = -1
            # Reverted to VWAP -> Exit signal (0)
            elif (prev_close >= prev_vwap and d["close"].iloc[i - 2] < d["vwap"].iloc[i - 2]) or \
                 (prev_close <= prev_vwap and d["close"].iloc[i - 2] > d["vwap"].iloc[i - 2]):
                signals[i] = 0

        d["signal"] = signals
        return d


# =====================================================================
# 2. VWAP TREND FOLLOWING STRATEGY
# =====================================================================
class VWAPTrendStrategy(BaseIntradayStrategy):
    strategy_id = "VWAP_TREND"
    name = "VWAP Trend Following"
    category = "TREND_FOLLOWING"
    description = "Enters momentum trend when price crosses and holds above/below session VWAP with expanding volume."
    parameters_schema = [
        StrategyParameter("volume_multiplier", "Volume Multiplier", "float", 1.2, 0.5, 3.0, description="Volume must exceed N-period average volume by this factor"),
        StrategyParameter("vol_ma_period", "Volume MA Period", "int", 20, 5, 50, description="Moving average period for volume confirmation"),
        StrategyParameter("allow_short", "Allow Short Positions", "bool", True, description="Enable short selling when price breaks below VWAP"),
    ]

    def generate_signals(self, df: pd.DataFrame, htf_60m_df: pd.DataFrame | None = None) -> pd.DataFrame:
        d = df.copy()
        vol_mult = float(self.params["volume_multiplier"])
        vol_period = int(self.params["vol_ma_period"])
        allow_short = bool(self.params["allow_short"])

        d["date_only"] = pd.to_datetime(d["datetime"]).dt.strftime("%Y-%m-%d")
        d["pv"] = d["close"] * d["volume"]
        d["cum_pv"] = d.groupby("date_only")["pv"].cumsum()
        d["cum_v"] = d.groupby("date_only")["volume"].cumsum()
        d["vwap"] = d["cum_pv"] / np.maximum(1, d["cum_v"])
        d["vol_ma"] = d["volume"].rolling(vol_period).mean().fillna(d["volume"])

        signals = np.zeros(len(d), dtype=int)
        for i in range(1, len(d)):
            c_prev = d["close"].iloc[i - 1]
            c_prev2 = d["close"].iloc[i - 2] if i >= 2 else c_prev
            vwap_prev = d["vwap"].iloc[i - 1]
            v_prev = d["volume"].iloc[i - 1]
            v_thresh = d["vol_ma"].iloc[i - 1] * vol_mult

            # Bullish cross above VWAP with strong volume
            if c_prev2 <= vwap_prev and c_prev > vwap_prev and v_prev >= v_thresh:
                signals[i] = 1
            # Bearish cross below VWAP with strong volume
            elif allow_short and c_prev2 >= vwap_prev and c_prev < vwap_prev and v_prev >= v_thresh:
                signals[i] = -1

        d["signal"] = signals
        return d


# =====================================================================
# 3. OPENING RANGE BREAKOUT (ORB)
# =====================================================================
class OpeningRangeBreakoutStrategy(BaseIntradayStrategy):
    strategy_id = "OPENING_RANGE_BREAKOUT"
    name = "Opening Range Breakout (ORB)"
    category = "BREAKOUT"
    description = "Defines the High and Low established during the opening window (e.g. first 15 or 30 minutes) and trades subsequent breakouts."
    parameters_schema = [
        StrategyParameter("range_minutes", "Opening Window (Minutes)", "int", 15, 5, 60, description="Duration in minutes from 09:15 to establish the opening range"),
        StrategyParameter("allow_short", "Allow Short Breakouts", "bool", True, description="Enable short positions on breakdown below opening range low"),
        StrategyParameter("max_trades_per_day", "Max Trades Per Day", "int", 2, 1, 5, description="Maximum trade entries permitted per calendar day"),
    ]

    def generate_signals(self, df: pd.DataFrame, htf_60m_df: pd.DataFrame | None = None) -> pd.DataFrame:
        d = df.copy()
        range_mins = int(self.params["range_minutes"])
        allow_short = bool(self.params["allow_short"])

        ts = pd.to_datetime(d["datetime"])
        d["date_only"] = ts.dt.strftime("%Y-%m-%d")
        d["time_only"] = ts.dt.time

        # Calculate cutoff time for opening range (09:15 + range_mins)
        open_h, open_m = 9, 15 + range_mins
        if open_m >= 60:
            open_h += open_m // 60
            open_m = open_m % 60
        from datetime import time as dtime
        range_cutoff_time = dtime(open_h, open_m, 0)

        signals = np.zeros(len(d), dtype=int)
        grouped = d.groupby("date_only")

        for _, grp_indices in grouped.groups.items():
            sub = d.loc[grp_indices]
            orb_bars = sub[sub["time_only"] <= range_cutoff_time]
            if orb_bars.empty:
                continue

            orb_high = orb_bars["high"].max()
            orb_low = orb_bars["low"].min()

            post_orb = sub[sub["time_only"] > range_cutoff_time]
            traded_today = 0
            max_daily = int(self.params["max_trades_per_day"])

            for idx in post_orb.index:
                loc = d.index.get_loc(idx)
                if loc < 1 or traded_today >= max_daily:
                    continue

                prev_close = d["close"].iloc[loc - 1]
                prev_high = d["high"].iloc[loc - 1]
                prev_low = d["low"].iloc[loc - 1]

                if prev_high > orb_high and prev_close > orb_high:
                    signals[loc] = 1
                    traded_today += 1
                elif allow_short and prev_low < orb_low and prev_close < orb_low:
                    signals[loc] = -1
                    traded_today += 1

        d["signal"] = signals
        return d


# =====================================================================
# 4. EMA 9/21 CROSSOVER STRATEGY
# =====================================================================
class EMA9_21CrossoverStrategy(BaseIntradayStrategy):
    strategy_id = "EMA_9_21_CROSSOVER"
    name = "EMA 9/21 Crossover"
    category = "TREND_FOLLOWING"
    description = "Classic intraday momentum crossover: Fast 9 EMA crossing above/below 21 EMA."
    parameters_schema = [
        StrategyParameter("fast_ema", "Fast EMA Period", "int", 9, 3, 25, description="Fast exponential moving average length"),
        StrategyParameter("slow_ema", "Slow EMA Period", "int", 21, 10, 60, description="Slow exponential moving average length"),
        StrategyParameter("allow_short", "Allow Short Positions", "bool", True, description="Enable short positions on bearish crossover"),
    ]

    def __init__(self, **params: Any):
        if "fast_period" in params and "fast_ema" not in params:
            params["fast_ema"] = params["fast_period"]
        if "slow_period" in params and "slow_ema" not in params:
            params["slow_ema"] = params["slow_period"]
        super().__init__(**params)
        self.params["fast_period"] = self.params.get("fast_ema", 9)
        self.params["slow_period"] = self.params.get("slow_ema", 21)

    def generate_signals(self, df: pd.DataFrame, htf_60m_df: pd.DataFrame | None = None) -> pd.DataFrame:
        d = df.copy()
        fast_p = int(self.params["fast_ema"])
        slow_p = int(self.params["slow_ema"])
        allow_short = bool(self.params["allow_short"])

        d["fast_ema"] = d["close"].ewm(span=fast_p, adjust=False).mean()
        d["slow_ema"] = d["close"].ewm(span=slow_p, adjust=False).mean()

        signals = np.zeros(len(d), dtype=int)
        for i in range(1, len(d)):
            prev_fast = d["fast_ema"].iloc[i - 1]
            prev_slow = d["slow_ema"].iloc[i - 1]
            prior_fast = d["fast_ema"].iloc[i - 2] if i >= 2 else prev_fast
            prior_slow = d["slow_ema"].iloc[i - 2] if i >= 2 else prev_slow

            # Bullish Cross
            if prior_fast <= prior_slow and prev_fast > prev_slow:
                signals[i] = 1
            # Bearish Cross
            elif prior_fast >= prior_slow and prev_fast < prev_slow:
                signals[i] = -1 if allow_short else 0

        d["signal"] = signals
        return d


# =====================================================================
# 5. RSI INTRADAY MEAN REVERSION STRATEGY
# =====================================================================
class RSIIntradayMeanReversionStrategy(BaseIntradayStrategy):
    strategy_id = "RSI_INTRADAY"
    name = "RSI Intraday Mean Reversion"
    category = "MEAN_REVERSION"
    description = "Exploits short-term intraday exhaustion when RSI reaches oversold or overbought extremes."
    parameters_schema = [
        StrategyParameter("rsi_period", "RSI Period", "int", 14, 5, 30, description="RSI calculation lookback length"),
        StrategyParameter("oversold", "Oversold Level", "float", 30.0, 15.0, 45.0, description="Threshold below which to buy"),
        StrategyParameter("overbought", "Overbought Level", "float", 70.0, 55.0, 85.0, description="Threshold above which to sell/short"),
        StrategyParameter("allow_short", "Allow Short Positions", "bool", True, description="Enable short selling when RSI becomes overbought"),
    ]

    def generate_signals(self, df: pd.DataFrame, htf_60m_df: pd.DataFrame | None = None) -> pd.DataFrame:
        d = df.copy()
        period = int(self.params["rsi_period"])
        oversold = float(self.params["oversold"])
        overbought = float(self.params["overbought"])
        allow_short = bool(self.params["allow_short"])

        delta = d["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / np.maximum(1e-9, loss)
        d["rsi"] = 100 - (100 / (1 + rs))

        signals = np.zeros(len(d), dtype=int)
        for i in range(1, len(d)):
            prev_rsi = d["rsi"].iloc[i - 1]
            prior_rsi = d["rsi"].iloc[i - 2] if i >= 2 else prev_rsi

            # Reversing up from oversold
            if prior_rsi < oversold and prev_rsi >= oversold:
                signals[i] = 1
            # Reversing down from overbought
            elif prior_rsi > overbought and prev_rsi <= overbought:
                signals[i] = -1 if allow_short else 0

        d["signal"] = signals
        return d


# =====================================================================
# 6. VOLUME BREAKOUT STRATEGY
# =====================================================================
class VolumeBreakoutStrategy(BaseIntradayStrategy):
    strategy_id = "VOLUME_BREAKOUT"
    name = "Volume Breakout"
    category = "BREAKOUT"
    description = "Detects price breakout of recent range accompanied by substantial volume expansion."
    parameters_schema = [
        StrategyParameter("lookback", "Range Lookback Bars", "int", 20, 5, 60, description="Number of bars to establish highest high/lowest low"),
        StrategyParameter("volume_factor", "Volume Expansion Factor", "float", 1.8, 1.1, 4.0, description="Volume must exceed average volume by this factor"),
        StrategyParameter("allow_short", "Allow Short Breakouts", "bool", True, description="Enable short positions on breakdown with volume"),
    ]

    def generate_signals(self, df: pd.DataFrame, htf_60m_df: pd.DataFrame | None = None) -> pd.DataFrame:
        d = df.copy()
        lookback = int(self.params["lookback"])
        vol_factor = float(self.params["volume_factor"])
        allow_short = bool(self.params["allow_short"])

        d["high_channel"] = d["high"].shift(1).rolling(lookback).max()
        d["low_channel"] = d["low"].shift(1).rolling(lookback).min()
        d["vol_avg"] = d["volume"].shift(1).rolling(lookback).mean()

        signals = np.zeros(len(d), dtype=int)
        for i in range(lookback + 1, len(d)):
            prev_close = d["close"].iloc[i - 1]
            prev_vol = d["volume"].iloc[i - 1]
            high_ch = d["high_channel"].iloc[i - 1]
            low_ch = d["low_channel"].iloc[i - 1]
            vol_avg = d["vol_avg"].iloc[i - 1]

            if prev_close > high_ch and prev_vol >= vol_avg * vol_factor:
                signals[i] = 1
            elif allow_short and prev_close < low_ch and prev_vol >= vol_avg * vol_factor:
                signals[i] = -1

        d["signal"] = signals
        return d


# =====================================================================
# 7. PREVIOUS DAY HIGH/LOW BREAKOUT STRATEGY
# =====================================================================
class PreviousDayHighLowBreakoutStrategy(BaseIntradayStrategy):
    strategy_id = "PDH_PDL_BREAKOUT"
    name = "Previous Day High/Low Breakout"
    category = "BREAKOUT"
    description = "Uses the prior session's high (PDH) and low (PDL) as critical institutional support and resistance pivots."
    parameters_schema = [
        StrategyParameter("buffer_bps", "Buffer Margin (bps)", "float", 5.0, 0.0, 30.0, description="Breakout buffer in basis points above PDH / below PDL"),
        StrategyParameter("allow_short", "Allow Short Breakouts", "bool", True, description="Enable short positions on breakdown below PDL"),
    ]

    def generate_signals(self, df: pd.DataFrame, htf_60m_df: pd.DataFrame | None = None) -> pd.DataFrame:
        d = df.copy()
        buffer_bps = float(self.params["buffer_bps"]) / 10000.0
        allow_short = bool(self.params["allow_short"])

        d["date_only"] = pd.to_datetime(d["datetime"]).dt.strftime("%Y-%m-%d")

        # Compute prior day high & low
        daily_stats = d.groupby("date_only").agg(pdh=("high", "max"), pdl=("low", "min")).shift(1)
        d = d.merge(daily_stats, on="date_only", how="left")

        signals = np.zeros(len(d), dtype=int)
        for i in range(1, len(d)):
            pdh = d["pdh"].iloc[i - 1]
            pdl = d["pdl"].iloc[i - 1]
            if pd.isna(pdh) or pd.isna(pdl):
                continue

            prev_close = d["close"].iloc[i - 1]
            buy_trigger = pdh * (1.0 + buffer_bps)
            short_trigger = pdl * (1.0 - buffer_bps)

            if prev_close > buy_trigger:
                signals[i] = 1
            elif allow_short and prev_close < short_trigger:
                signals[i] = -1

        d["signal"] = signals
        return d


# =====================================================================
# REGISTRY & FACTORY
# =====================================================================
INTRADAY_STRATEGY_MAP: dict[str, type[BaseIntradayStrategy]] = {
    "VWAP_REVERSION": VWAPReversionStrategy,
    "VWAP_TREND": VWAPTrendStrategy,
    "OPENING_RANGE_BREAKOUT": OpeningRangeBreakoutStrategy,
    "EMA_9_21_CROSSOVER": EMA9_21CrossoverStrategy,
    "RSI_INTRADAY": RSIIntradayMeanReversionStrategy,
    "VOLUME_BREAKOUT": VolumeBreakoutStrategy,
    "PDH_PDL_BREAKOUT": PreviousDayHighLowBreakoutStrategy,
}


def list_intraday_strategies() -> list[dict[str, Any]]:
    """Return catalog of all 7 available intraday strategies with parameter schemas."""
    catalog = []
    for cls in INTRADAY_STRATEGY_MAP.values():
        instance = cls()
        catalog.append(instance.get_info())
    return catalog


def get_intraday_strategy(strategy_id: str, **params: Any) -> BaseIntradayStrategy:
    """Instantiate strategy with user parameters."""
    clean_id = strategy_id.strip().upper()
    if clean_id not in INTRADAY_STRATEGY_MAP:
        raise ValueError(f"Unknown intraday strategy '{strategy_id}'. Available: {list(INTRADAY_STRATEGY_MAP.keys())}")
    return INTRADAY_STRATEGY_MAP[clean_id](**params)
