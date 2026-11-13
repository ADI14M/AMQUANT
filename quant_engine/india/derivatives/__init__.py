"""AMQUANT INDIA - Derivatives Subpackage."""

from quant_engine.india.derivatives.futures import (
    ContinuousFuturesBuilder,
    ContinuousFuturesResult,
    RolloverEvent,
    RolloverMethod,
)
from quant_engine.india.derivatives.master import (
    ContractType,
    DerivativesContract,
    HISTORICAL_LOT_SIZES,
    LotSizeSchedule,
    OptionType,
    build_contract_symbol,
    generate_contract_master_catalog,
    get_historical_lot_size,
    get_lot_size_history,
    get_monthly_expiry_date,
)
from quant_engine.india.derivatives.options import (
    OptionChain,
    OptionChainBuilder,
    OptionChainRow,
    OptionQuote,
    calculate_implied_volatility,
    calculate_max_pain,
    compute_option_greeks_for_quote,
)

__all__ = [
    "ContractType",
    "OptionType",
    "DerivativesContract",
    "LotSizeSchedule",
    "HISTORICAL_LOT_SIZES",
    "get_historical_lot_size",
    "get_lot_size_history",
    "get_monthly_expiry_date",
    "build_contract_symbol",
    "generate_contract_master_catalog",
    "RolloverMethod",
    "RolloverEvent",
    "ContinuousFuturesResult",
    "ContinuousFuturesBuilder",
    "OptionQuote",
    "OptionChainRow",
    "OptionChain",
    "OptionChainBuilder",
    "calculate_implied_volatility",
    "compute_option_greeks_for_quote",
    "calculate_max_pain",
]

