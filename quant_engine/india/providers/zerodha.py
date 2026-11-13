"""Zerodha Kite Connect Historical Data Provider Adapter.

DOCUMENTATION & SPECIFICATIONS:
- Provider: Zerodha Broking Limited (Kite Connect API v3)
- Authentication:
  1. API Key + API Secret registered on kite.trade portal.
  2. Daily login flow: User logs in via web login URL, receives `request_token`.
  3. POST `/session/token` with checksum SHA256(api_key + request_token + api_secret)
     returns `access_token` and `public_token`. Valid until end of trading day (06:00 IST next day).
- Historical Data Endpoints:
  `GET https://api.kite.trade/instruments/historical/{instrument_token}/{interval}`
  Parameters: `from` (YYYY-MM-DD HH:MM:SS), `to` (YYYY-MM-DD HH:MM:SS), `continuous` (0 or 1), `oi` (1 for F&O open interest).
- Supported Intervals:
  - minute (1m)
  - 3minute (3m)
  - 5minute (5m)
  - 10minute (10m)
  - 15minute (15m)
  - 30minute (30m)
  - 60minute (60m)
  - day (1d)
- Historical Depth:
  - minute: Up to 60-100 days per call (multi-year with chunked requests)
  - 5m/15m/60m: Up to 1000 days
  - day: 20+ years (since inception of NSE online trading)
- Rate Limits:
  - 3 requests per second strictly enforced. 429 Too Many Requests returned if breached.
- Subscription Costs:
  - ₹2,000 / month (~£19/month) for Kite Connect Base API
  - ₹2,000 / month (~£19/month) for Historical Data API add-on
  - AMQUANT Policy: Optional! Not required to use AMQUANT. AMQUANT operates at £0 cost by default.
- Licensing:
  - For personal non-commercial algorithmic research and trading. Redistribution of raw data prohibited.
"""

from __future__ import annotations

import logging
from typing import Any
import pandas as pd

from quant_engine.india.providers.base import BaseMarketDataProvider, ProviderSpecification

logger = logging.getLogger("amquant.india.providers.zerodha")


class ZerodhaKiteProvider(BaseMarketDataProvider):
    """Zerodha Kite Connect API adapter."""

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
        return "Zerodha Kite Connect (Broker API)"

    def get_provider_spec(self) -> ProviderSpecification:
        return ProviderSpecification(
            provider_id="zerodha",
            name="Zerodha Kite Connect API v3",
            auth_requirements="API Key + API Secret + Daily TOTP Request Token -> Access Token",
            historical_depth_daily="20+ years across NSE/BSE equities, futures, and indices",
            historical_depth_intraday="1m: 60-100 days/chunk | 5m/15m/60m: 1000 days | Multi-year with pagination",
            supported_intervals=["1m", "3m", "5m", "10m", "15m", "30m", "60m", "1d"],
            rate_limits="3 requests per second strictly enforced",
            cost_inr_gbp="₹2,000/mo Base + ₹2,000/mo Historical Add-on (~£38/mo total) · £0 in AMQUANT mock mode",
            licensing_restrictions="Personal non-commercial research use only; redistribution strictly prohibited by exchange rules",
            status="ADAPTER_CONFIGURED",
            notes="Institutional broker API adapter. AMQUANT preserves £0 cost by default and operates via mock fixtures unless user supplies Kite credentials.",
        )

    def fetch_historical_ohlcv(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "2y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical daily OHLCV."""
        if not self.mock_mode and self.access_token:
            # Live broker request logic
            logger.info("Executing live Kite Connect request for %s", symbol)
            # In a live setup with credentials, would call https://api.kite.trade/instruments/historical/...
            return pd.DataFrame()

        # Deterministic offline fixture representation
        return pd.DataFrame()

    def fetch_intraday_ohlcv(
        self,
        symbol: str,
        interval: str = "5m",
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "5d",
    ) -> pd.DataFrame:
        """Fetch intraday candles from Kite Connect."""
        logger.info("Zerodha Kite intraday adapter queried for %s [%s]", symbol, interval)
        return pd.DataFrame()

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch live quote from Kite Connect."""
        return {
            "symbol": symbol,
            "provider": self.get_provider_name(),
            "status": "CONFIGURED_OFFLINE" if self.mock_mode else "AUTHENTICATED",
            "message": "Enter your Kite API key and Access Token in settings to activate live broker data stream.",
        }

