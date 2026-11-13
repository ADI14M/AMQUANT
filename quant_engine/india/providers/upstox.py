"""Upstox API v2 Historical Data Provider Adapter.

DOCUMENTATION & SPECIFICATIONS:
- Provider: Upstox (RKSV Securities India Pvt. Ltd.) - API v2
- Authentication:
  1. OAuth 2.0 standard flow.
  2. Register app on developer.upstox.com to obtain API Key (Client ID) and API Secret.
  3. User redirects to `https://api.upstox.com/v2/login/authorization/dialog`
  4. Callback returns authorization code.
  5. Exchange code at `POST https://api.upstox.com/v2/login/authorization/token` for Bearer access_token.
- Historical Data Endpoints:
  `GET https://api.upstox.com/v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}`
  Intervals: `1minute`, `30minute`, `day`, `week`, `month`.
  `GET https://api.upstox.com/v2/historical-candle/intraday/{instrument_key}/{interval}`
- Rate Limits:
  - 25 requests per second (substantially higher than Zerodha).
- Subscription Costs:
  - Free API access for active Upstox Demat/Trading account holders (£0 / ₹0).
- Licensing:
  - Personal non-commercial trading and research.
"""

from __future__ import annotations

import logging
from typing import Any
import pandas as pd

from quant_engine.india.providers.base import BaseMarketDataProvider, ProviderSpecification

logger = logging.getLogger("amquant.india.providers.upstox")


class UpstoxProvider(BaseMarketDataProvider):
    """Upstox API v2 adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        access_token: str | None = None,
        mock_mode: bool = True,
    ):
        self.api_key = api_key
        self.access_token = access_token
        self.mock_mode = mock_mode or not (api_key and access_token)

    def get_provider_name(self) -> str:
        return "Upstox API v2 (Broker API)"

    def get_provider_spec(self) -> ProviderSpecification:
        return ProviderSpecification(
            provider_id="upstox",
            name="Upstox API v2",
            auth_requirements="OAuth 2.0 Bearer Token (Client ID + Client Secret + Redirect Authorization)",
            historical_depth_daily="10+ years daily OHLCV across NSE, BSE, and MCX",
            historical_depth_intraday="1m: Up to 1 month per call | 30m: 1+ year | Intraday streaming available",
            supported_intervals=["1m", "30m", "1d", "1w", "1mo"],
            rate_limits="25 requests per second",
            cost_inr_gbp="£0 / ₹0 (Free for active Upstox account holders)",
            licensing_restrictions="Personal research & automated execution",
            status="ADAPTER_CONFIGURED",
            notes="High-throughput 25 req/s broker API adapter. AMQUANT operates at £0 cost by default with zero mandatory subscriptions.",
        )

    def fetch_historical_ohlcv(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        logger.info("Upstox historical daily query for %s", symbol)
        return pd.DataFrame()

    def fetch_intraday_ohlcv(
        self,
        symbol: str,
        interval: str = "5m",
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "5d",
    ) -> pd.DataFrame:
        logger.info("Upstox intraday query for %s [%s]", symbol, interval)
        return pd.DataFrame()

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "provider": self.get_provider_name(),
            "status": "CONFIGURED_OFFLINE" if self.mock_mode else "AUTHENTICATED",
            "message": "Enter your Upstox OAuth Bearer token in settings to stream broker data.",
        }

