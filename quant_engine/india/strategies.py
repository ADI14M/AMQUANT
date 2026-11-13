"""Strategy Library for AMQUANT INDIA Historical Backtesting Engine.

Provides modular, configurable strategy classes with explicit entry and exit rules,
parameter schemas, and zero look-ahead signal generation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import numpy as np
import pandas as pd


@dataclass
class ParameterSpec:
    name: str
    display_name: str
    param_type: str  # 'int' | 'float' | 'str'
    default_value: Any
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "param_type": self.param_type,
            "default_value": self.default_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step": self.step,
            "description": self.description,
        }


class BaseStrategy(ABC):
    """Abstract base class for all backtestable Indian trading strategies."""

    id: str = "base"
    name: str = "Base Strategy"
    description: str = ""
    entry_rule_description: str = ""
    exit_rule_description: str = ""

    def __init__(self, **params: Any):
        self.params: dict[str, Any] = {}
        specs = self.get_parameter_specs()
        for spec in specs:
            self.params[spec.name] = params.get(spec.name, spec.default_value)

    @classmethod
    @abstractmethod
    def get_parameter_specs(cls) -> list[ParameterSpec]:
        """Return parameter specifications and constraints."""
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Generate binary position signals (1.0 = Long, 0.0 = Cash).
        
        Strictly calculated using close / high / low prices up to date t.
        The execution engine will execute orders on date t+1 Open to prevent look-ahead bias.
        """
        pass

    def to_metadata_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": getattr(self, "category", "TREND_FOLLOWING"),
            "description": self.description,
            "entry_rule": self.entry_rule_description,
            "exit_rule": self.exit_rule_description,
            "parameters": [s.to_dict() for s in self.get_parameter_specs()],
            "current_params": self.params,
        }


class SMA20_50Strategy(BaseStrategy):
    """Dual Moving Average Trend Following Strategy (SMA 20 / 50)."""

    id = "SMA_20_50"
    name = "SMA 20/50 Trend Following"
    category = "TREND_FOLLOWING"
    description = "Captures medium-term trends by holding long positions when short-term momentum dominates."
    entry_rule_description = "Enter Long when Fast SMA (default 20) crosses above Slow SMA (default 50)."
    exit_rule_description = "Exit to Cash when Fast SMA crosses below or equals Slow SMA."

    @classmethod
    def get_parameter_specs(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec("fast_period", "Fast SMA Period", "int", 20, min_value=5, max_value=100, step=1, description="Lookback sessions for fast moving average"),
            ParameterSpec("slow_period", "Slow SMA Period", "int", 50, min_value=15, max_value=250, step=1, description="Lookback sessions for slow moving average"),
        ]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        fast_p = int(self.params["fast_period"])
        slow_p = int(self.params["slow_period"])
        fast_sma = close.rolling(fast_p).mean()
        slow_sma = close.rolling(slow_p).mean()
        signal = (fast_sma > slow_sma).astype(float)
        return signal.fillna(0.0)


class SMA50_200Strategy(BaseStrategy):
    """Classic Institutional Golden Cross Strategy (SMA 50 / 200)."""

    id = "SMA_50_200"
    name = "SMA 50/200 Golden Cross"
    category = "TREND_FOLLOWING"
    description = "Institutional long-term macro trend following filter using the 50-day and 200-day simple moving averages."
    entry_rule_description = "Enter Long on Golden Cross (50 SMA > 200 SMA)."
    exit_rule_description = "Exit to Cash on Death Cross (50 SMA <= 200 SMA)."

    @classmethod
    def get_parameter_specs(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec("fast_period", "Fast SMA Period", "int", 50, min_value=20, max_value=100, step=1, description="Fast moving average period"),
            ParameterSpec("slow_period", "Slow SMA Period", "int", 200, min_value=100, max_value=400, step=1, description="Slow moving average period"),
        ]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        fast_p = int(self.params["fast_period"])
        slow_p = int(self.params["slow_period"])
        fast_sma = close.rolling(fast_p).mean()
        slow_sma = close.rolling(slow_p).mean()
        signal = (fast_sma > slow_sma).astype(float)
        return signal.fillna(0.0)


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI Mean Reversion Strategy."""

    id = "RSI_MEAN_REVERSION"
    name = "RSI Mean Reversion"
    category = "MEAN_REVERSION"
    description = "Buys temporary oversold market conditions and takes profit when price reverts to overbought levels."
    entry_rule_description = "Enter Long when 14-session RSI drops below oversold threshold (default 30)."
    exit_rule_description = "Exit to Cash when RSI recovers above overbought threshold (default 70)."

    @classmethod
    def get_parameter_specs(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec("rsi_period", "RSI Period", "int", 14, min_value=5, max_value=50, step=1, description="Lookback window for relative strength index"),
            ParameterSpec("oversold", "Oversold Threshold", "float", 30.0, min_value=10.0, max_value=45.0, step=1.0, description="RSI entry trigger"),
            ParameterSpec("overbought", "Overbought Threshold", "float", 70.0, min_value=55.0, max_value=90.0, step=1.0, description="RSI exit trigger"),
        ]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        period = int(self.params["rsi_period"])
        oversold = float(self.params["oversold"])
        overbought = float(self.params["overbought"])

        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        n = len(df)
        signals = np.zeros(n, dtype=float)
        in_pos = False

        for i in range(n):
            val = rsi.iloc[i]
            if np.isnan(val):
                continue
            if not in_pos and val < oversold:
                in_pos = True
            elif in_pos and val > overbought:
                in_pos = False
            signals[i] = 1.0 if in_pos else 0.0

        return pd.Series(signals, index=df.index)


class MACDCrossoverStrategy(BaseStrategy):
    """Moving Average Convergence Divergence (MACD) Momentum Strategy."""

    id = "MACD_CROSSOVER"
    name = "MACD Crossover"
    category = "TREND_FOLLOWING"
    description = "Captures shifts in directional momentum via exponential moving average convergence and divergence."
    entry_rule_description = "Enter Long when MACD Line (12 EMA - 26 EMA) crosses above Signal Line (9 EMA)."
    exit_rule_description = "Exit to Cash when MACD Line crosses below Signal Line."

    @classmethod
    def get_parameter_specs(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec("fast_period", "Fast EMA Period", "int", 12, min_value=5, max_value=30, step=1, description="Fast exponential moving average period"),
            ParameterSpec("slow_period", "Slow EMA Period", "int", 26, min_value=15, max_value=60, step=1, description="Slow exponential moving average period"),
            ParameterSpec("signal_period", "Signal EMA Period", "int", 9, min_value=3, max_value=25, step=1, description="Signal smoothing period"),
        ]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        fast_p = int(self.params["fast_period"])
        slow_p = int(self.params["slow_period"])
        sig_p = int(self.params["signal_period"])

        ema_fast = close.ewm(span=fast_p, adjust=False).mean()
        ema_slow = close.ewm(span=slow_p, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=sig_p, adjust=False).mean()

        signals = (macd_line > signal_line).astype(float)
        return signals.fillna(0.0)


class DonchianBreakoutStrategy(BaseStrategy):
    """Donchian Channel Breakout (Turtle Trading Pattern)."""

    id = "DONCHIAN_BREAKOUT"
    name = "Donchian Channel Breakout"
    category = "TREND_FOLLOWING"
    description = "Classic systematic trend following strategy entering on multi-week highs and exiting on multi-week lows."
    entry_rule_description = "Enter Long when Close exceeds the highest High of the past N days (default 20)."
    exit_rule_description = "Exit to Cash when Close drops below the lowest Low of the past M days (default 10)."

    @classmethod
    def get_parameter_specs(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec("entry_lookback", "Entry High Lookback", "int", 20, min_value=10, max_value=60, step=1, description="Sessions for breakout high channel"),
            ParameterSpec("exit_lookback", "Exit Low Lookback", "int", 10, min_value=5, max_value=30, step=1, description="Sessions for exit low channel"),
        ]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        entry_lb = int(self.params["entry_lookback"])
        exit_lb = int(self.params["exit_lookback"])

        # Shift by 1 to compare current close against PRIOR channel boundary
        upper_channel = high.rolling(entry_lb).max().shift(1)
        lower_channel = low.rolling(exit_lb).min().shift(1)

        n = len(df)
        signals = np.zeros(n, dtype=float)
        in_pos = False

        for i in range(n):
            c = close.iloc[i]
            u = upper_channel.iloc[i]
            l = lower_channel.iloc[i]
            if np.isnan(u) or np.isnan(l):
                continue
            if not in_pos and c > u:
                in_pos = True
            elif in_pos and c < l:
                in_pos = False
            signals[i] = 1.0 if in_pos else 0.0

        return pd.Series(signals, index=df.index)


class MomentumRankingStrategy(BaseStrategy):
    """Momentum Rate of Change Strategy."""

    id = "MOMENTUM_RANKING"
    name = "Momentum Trend"
    category = "MOMENTUM"
    description = "Captures persistent price momentum by measuring rate of change over a defined multi-session horizon."
    entry_rule_description = "Enter Long when N-session cumulative return exceeds the threshold (default > 0%)."
    exit_rule_description = "Exit to Cash when momentum turns negative or drops below threshold."

    @classmethod
    def get_parameter_specs(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec("momentum_period", "Momentum Lookback (Days)", "int", 60, min_value=10, max_value=180, step=5, description="Lookback period for momentum calculation"),
            ParameterSpec("min_momentum_pct", "Minimum Return Threshold (%)", "float", 0.0, min_value=-5.0, max_value=15.0, step=0.5, description="Minimum rate of change required to hold"),
        ]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        period = int(self.params["momentum_period"])
        threshold = float(self.params["min_momentum_pct"]) / 100.0

        mom = close.pct_change(period)
        signals = (mom > threshold).astype(float)
        return signals.fillna(0.0)


# Strategy Registry
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    SMA20_50Strategy.id: SMA20_50Strategy,
    SMA50_200Strategy.id: SMA50_200Strategy,
    RSIMeanReversionStrategy.id: RSIMeanReversionStrategy,
    MACDCrossoverStrategy.id: MACDCrossoverStrategy,
    DonchianBreakoutStrategy.id: DonchianBreakoutStrategy,
    MomentumRankingStrategy.id: MomentumRankingStrategy,
}


def get_strategy(strategy_id: str, **params: Any) -> BaseStrategy:
    """Instantiate a strategy by identifier."""
    cls = STRATEGY_REGISTRY.get(strategy_id)
    if cls is None:
        raise ValueError(f"Unknown strategy ID: '{strategy_id}'. Available: {list(STRATEGY_REGISTRY.keys())}")
    return cls(**params)


def list_available_strategies() -> list[dict[str, Any]]:
    """Return metadata and parameter specifications for all registered strategies."""
    result = []
    for strat_cls in STRATEGY_REGISTRY.values():
        instance = strat_cls()
        result.append(instance.to_metadata_dict())
    return result
