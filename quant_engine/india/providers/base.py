"""Abstract Base Class for AMQUANT INDIA Data Providers.

Defines standardized, provider-independent interfaces for:
- Daily OHLCV data
- Intraday multi-interval data (1m, 5m, 15m, 30m, 60m)
- Real-time / delayed quotes
- Historical and current Option Chains
- Provider specifications and limitations audit
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any
import pandas as pd


@dataclass
class ProviderSpecification:
    provider_id: str
    name: str
    auth_requirements: str
    historical_depth_daily: str
    historical_depth_intraday: str
    supported_intervals: list[str]
    rate_limits: str
    cost_inr_gbp: str
    licensing_restrictions: str
    status: str  # 'ACTIVE_FREE' | 'ADAPTER_CONFIGURED' | 'OFFICIAL_ARCHIVE'
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseMarketDataProvider(ABC):
    @abstractmethod
    def fetch_historical_ohlcv(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical daily OHLCV dataframe. Must not fabricate missing rows."""
        pass

    def fetch_intraday_ohlcv(
        self,
        symbol: str,
        interval: str = "5m",
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "5d",
    ) -> pd.DataFrame:
        """Fetch historical intraday OHLCV dataframe."""
        raise NotImplementedError(f"Intraday data not implemented for {self.get_provider_name()}")

    def fetch_option_chain(
        self,
        symbol: str,
        expiry: str | None = None,
    ) -> dict[str, Any]:
        """Fetch option chain for an underlying Indian equity/index."""
        raise NotImplementedError(f"Option chains not implemented for {self.get_provider_name()}")

    @abstractmethod
    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch real-time or delayed quote for an Indian instrument."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the unique name of the provider."""
        pass

    def get_provider_spec(self) -> ProviderSpecification:
        """Return comprehensive metadata regarding authentication, limits, and costs."""
        return ProviderSpecification(
            provider_id="base",
            name=self.get_provider_name(),
            auth_requirements="None",
            historical_depth_daily="Unknown",
            historical_depth_intraday="Unknown",
            supported_intervals=["1d"],
            rate_limits="Standard",
            cost_inr_gbp="£0",
            licensing_restrictions="Personal research use only",
            status="ACTIVE_FREE",
            notes="Base provider interface",
        )
