"""AMQUANT INDIA - Phase 5 Intraday, Futures and Options Backtesting Module."""

from quant_engine.india.backtest import run_indian_backtest
from quant_engine.india.backtesting.futures_engine import (
    FuturesBacktestConfig,
    FuturesBacktestEngine,
    FuturesBacktestResult,
    FuturesTradeRecord,
)
from quant_engine.india.backtesting.intraday_engine import (
    IntradayBacktestConfig,
    IntradayBacktestResult,
    IntradayEquityBacktester,
    IntradayTrade,
)
from quant_engine.india.backtesting.intraday_strategies import (
    BaseIntradayStrategy,
    EMA9_21CrossoverStrategy,
    OpeningRangeBreakoutStrategy,
    PreviousDayHighLowBreakoutStrategy,
    RSIIntradayMeanReversionStrategy,
    VolumeBreakoutStrategy,
    VWAPReversionStrategy,
    VWAPTrendStrategy,
    get_intraday_strategy,
    list_intraday_strategies,
)
from quant_engine.india.backtesting.options_engine import (
    AVAILABLE_OPTIONS_STRATEGIES,
    OptionLeg,
    OptionsBacktestConfig,
    OptionsBacktestEngine,
    OptionsBacktestResult,
    PayoffAnalysis,
    PayoffPoint,
)
from quant_engine.india.backtesting.risk_manager import (
    RiskCheckResult,
    RiskLimits,
    RiskManager,
)

__all__ = [
    # Risk Management
    "RiskLimits",
    "RiskManager",
    "RiskCheckResult",
    # Intraday Strategies
    "BaseIntradayStrategy",
    "VWAPReversionStrategy",
    "VWAPTrendStrategy",
    "OpeningRangeBreakoutStrategy",
    "EMA9_21CrossoverStrategy",
    "RSIIntradayMeanReversionStrategy",
    "VolumeBreakoutStrategy",
    "PreviousDayHighLowBreakoutStrategy",
    "list_intraday_strategies",
    "get_intraday_strategy",
    # Intraday Backtester
    "IntradayEquityBacktester",
    "IntradayBacktestConfig",
    "IntradayBacktestResult",
    "IntradayTrade",
    # Futures Backtester
    "FuturesBacktestEngine",
    "FuturesBacktestConfig",
    "FuturesBacktestResult",
    "FuturesTradeRecord",
    # Options Backtester
    "OptionsBacktestEngine",
    "OptionsBacktestConfig",
    "OptionsBacktestResult",
    "OptionLeg",
    "PayoffAnalysis",
    "PayoffPoint",
    "AVAILABLE_OPTIONS_STRATEGIES",
]
