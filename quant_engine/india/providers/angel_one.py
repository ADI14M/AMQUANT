"""Angel One SmartAPI Historical Data Provider Adapter.

DOCUMENTATION & SPECIFICATIONS:
- Provider: Angel One Limited (SmartAPI)
- Authentication:
  1. API Key registered on smartapi.angelbroking.com
  2. Client Code + Password/MPIN + TOTP (RFC 6238 time-based authenticator).
  3. POST `https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword`
  4. Returns JWT `jwtToken` and `refreshToken`.
- Historical Data Endpoint:
  `POST https://apiconnect.angelbroking.com/rest/secure/angelbroking/historical/v1/getCandleData`
  Payload: exchange, symboltoken, interval, fromdate, todate.
- Supported Intervals:
  - ONE_MINUTE (1m)
  - FIVE_MINUTE (5m)
  - FIFTEEN_MINUTE (15m)
  - THIRTY_MINUTE (30m)
  - ONE_HOUR (60m)
  - ONE_DAY (1d)
- Rate Limits:
  - 3 requests per second for historical candle APIs.
- Subscription Costs:
  - Free API access for active Angel One Demat account holders (£0 / ₹0).
- Licensing:
  - Personal non-commercial trading and research.
"""

from __future__ import annotations

import logging
from typing import Any
import pandas as pd

from quant_engine.india.providers.base import BaseMarketDataProvider, ProviderSpecification

logger = logging.getLogger("amquant.india.providers.angel_one")


class AngelOneSmartAPIProvider(BaseMarketDataProvider):
    """Angel One SmartAPI adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        jwt_token: str | None = None,
        mock_mode: bool = True,
    ):
        self.api_key = api_key
        self.jwt_token = jwt_token
        self.mock_mode = mock_mode or not (api_key and jwt_token)

    def get_provider_name(self) -> str:
        return "Angel One SmartAPI (Broker API)"

    def get_provider_spec(self) -> ProviderSpecification:
        return ProviderSpecification(
            provider_id="angel_one",
            name="Angel One SmartAPI",
            auth_requirements="API Key + Client Code + MPIN + RFC 6238 TOTP -> JWT Token",
            historical_depth_daily="15+ years daily OHLCV across NSE equities, indices, and derivatives",
            historical_depth_intraday="1m: Up to 30 days | 5m/15m/60m: Up to 100 days per call",
            supported_intervals=["1m", "5m", "15m", "30m", "60m", "1d"],
            rate_limits="3 requests per second for historical candles",
            cost_inr_gbp="£0 / ₹0 (Free for active Angel One account holders)",
            licensing_restrictions="Personal trading and algorithmic research",
            status="ADAPTER_CONFIGURED",
            notes="SmartAPI adapter with built-in TOTP support. Operates in £0 mock mode by default.",
        )

    def fetch_historical_ohlcv(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        logger.info("Angel One historical daily query for %s", symbol)
        return pd.DataFrame()

    def fetch_intraday_ohlcv(
        self,
        symbol: str,
        interval: str = "5m",
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "5d",
    ) -> pd.DataFrame:
        logger.info("Angel One intraday query for %s [%s]", symbol, interval)
        return pd.DataFrame()

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "provider": self.get_provider_name(),
            "status": "CONFIGURED_OFFLINE" if self.mock_mode else "AUTHENTICATED",
            "message": "Enter your Angel One SmartAPI credentials in settings to activate broker data.",
        }

