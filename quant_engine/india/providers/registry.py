"""AMQUANT INDIA - Data Provider Registry & Specification Audit.

Manages all supported Indian market data providers:
1. Yahoo Finance (Free Public Endpoint - active collector)
2. Zerodha Kite Connect (Broker API adapter)
3. Upstox API v2 (Broker API adapter)
4. Angel One SmartAPI (Broker API adapter)
5. NSE Official Bhavcopy Archive (Exchange archival parser)

Guarantees £0 cost operation by default.
"""

from __future__ import annotations

from typing import Any

from quant_engine.india.providers.angel_one import AngelOneSmartAPIProvider
from quant_engine.india.providers.base import BaseMarketDataProvider, ProviderSpecification
from quant_engine.india.providers.nse_bhavcopy import NSEBhavcopyProvider
from quant_engine.india.providers.upstox import UpstoxProvider
from quant_engine.india.providers.yahoo import YahooFinanceProvider
from quant_engine.india.providers.zerodha import ZerodhaKiteProvider

ALL_PROVIDERS: dict[str, BaseMarketDataProvider] = {
    "yahoo": YahooFinanceProvider(),
    "zerodha": ZerodhaKiteProvider(mock_mode=True),
    "upstox": UpstoxProvider(mock_mode=True),
    "angel_one": AngelOneSmartAPIProvider(mock_mode=True),
    "nse_bhavcopy": NSEBhavcopyProvider(),
}


def list_all_provider_specs() -> list[dict[str, Any]]:
    """Return comprehensive specifications and status for all 5 providers."""
    return [p.get_provider_spec().to_dict() for p in ALL_PROVIDERS.values()]


def get_provider(provider_id: str) -> BaseMarketDataProvider:
    """Retrieve provider instance by ID."""
    clean_id = provider_id.strip().lower()
    if clean_id not in ALL_PROVIDERS:
        raise ValueError(f"Unknown provider '{provider_id}'. Available: {list(ALL_PROVIDERS.keys())}")
    return ALL_PROVIDERS[clean_id]

