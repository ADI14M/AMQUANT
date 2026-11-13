"""Yahoo Finance Data Provider for Indian Financial Markets.

Handles symbol mapping (.NS for NSE, .BO for BSE, ^NSEI for Nifty 50),
rate-limiting, multi-index response normalization, quality auditing,
and seamless Parquet caching.
"""
from __future__ import annotations

import logging
import time
from typing import Any
import numpy as np
import pandas as pd
import yfinance as yf

from quant_engine.india.intraday import (
    ExchangeSessionValidator,
    IntradayInterval,
    MissingCandleAuditor,
    merge_incremental_intraday,
)
from quant_engine.india.providers.base import BaseMarketDataProvider, ProviderSpecification
from quant_engine.india.quality import audit_and_clean_ohlcv
from quant_engine.india.storage import IndiaStorageEngine
from quant_engine.india.universe import get_instrument

logger = logging.getLogger("amquant.india.yahoo")


class YahooFinanceProvider(BaseMarketDataProvider):
    def __init__(self, storage_engine: IndiaStorageEngine | None = None):
        self.storage = storage_engine or IndiaStorageEngine()
        self.last_call_time = 0.0
        self.min_interval_seconds = 0.25  # respectful rate-limiting (max 4 calls/sec)
        self.validator = ExchangeSessionValidator()

    def get_provider_name(self) -> str:
        return "Yahoo Finance (Free Public Endpoint)"

    def get_provider_spec(self) -> ProviderSpecification:
        return ProviderSpecification(
            provider_id="yahoo",
            name="Yahoo Finance (Free Public Endpoint)",
            auth_requirements="None (Public Endpoints)",
            historical_depth_daily="5 to 10+ years daily OHLCV",
            historical_depth_intraday="1m: 7 days | 5m/15m/30m: 60 days | 60m: 730 days",
            supported_intervals=["1m", "5m", "15m", "30m", "60m", "1d"],
            rate_limits="Respectful 0.25s throttle (~4 requests/second)",
            cost_inr_gbp="£0 / ₹0 (Zero subscription cost)",
            licensing_restrictions="Personal non-commercial research use only",
            status="ACTIVE_FREE",
            notes="Primary zero-cost historical collector for AMQUANT INDIA. Subject to provider upstream uptime.",
        )

    def _resolve_ticker(self, symbol: str) -> str:
        clean = symbol.strip().upper()
        if clean in ("NIFTY", "NIFTY50", "NIFTY 50"):
            return "^NSEI"
        if clean in ("BANKNIFTY", "NIFTYBANK", "NIFTY BANK", "BANK NIFTY"):
            return "^NSEBANK"
        if clean in ("SENSEX", "^BSESN"):
            return "^BSESN"

        inst = get_instrument(symbol)
        if inst and inst.yahoo_ticker:
            return inst.yahoo_ticker

        if clean.startswith("^"):
            return clean
        if clean.endswith(".NS") or clean.endswith(".BO"):
            return clean
        # Default to NSE
        return f"{clean}.NS"

    def _rate_limit(self) -> None:
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self.last_call_time = time.time()

    def fetch_historical_ohlcv(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "2y",
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data for an Indian instrument.

        Checks local cleaned Parquet cache first unless force_refresh is True.
        """
        # 1. Check local Parquet cache first for high speed & zero network load
        if not force_refresh:
            cached_df = self.storage.load_parquet(symbol, stage="cleaned", dataset_type="ohlcv")
            if cached_df is not None and not cached_df.empty:
                logger.debug("Loaded %s from local Parquet storage", symbol)
                return cached_df

        ticker_str = self._resolve_ticker(symbol)
        self._rate_limit()

        try:
            logger.info("Fetching %s (%s) from Yahoo Finance", symbol, ticker_str)
            ticker = yf.Ticker(ticker_str)
            if start_date and end_date:
                df = ticker.history(start=start_date, end=end_date, interval=interval, auto_adjust=False)
            else:
                df = ticker.history(period=period, interval=interval, auto_adjust=False)

            if df.empty:
                logger.warning("Empty response received from Yahoo Finance for %s", ticker_str)
                # Check if we have cached data before giving up
                cached_df = self.storage.load_parquet(symbol, stage="cleaned", dataset_type="ohlcv")
                if cached_df is not None:
                    return cached_df
                raise ValueError(f"No market data available for Indian symbol: {symbol} ({ticker_str})")

            # Flatten MultiIndex columns if present (yfinance >= 0.2.40)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            # Reset index so 'Date' is a column
            df = df.reset_index()

            # Audit and clean using our Indian market quality rules
            cleaned_df, report = audit_and_clean_ohlcv(df, symbol=symbol)

            # Save raw and cleaned versions into Parquet storage
            self.storage.save_parquet(
                symbol=symbol,
                df=df,
                stage="raw",
                dataset_type="ohlcv",
                source=self.get_provider_name(),
            )
            self.storage.save_parquet(
                symbol=symbol,
                df=cleaned_df,
                stage="cleaned",
                dataset_type="ohlcv",
                source=self.get_provider_name(),
            )

            return cleaned_df

        except Exception as exc:
            logger.error("Failed to fetch %s from Yahoo Finance: %s", ticker_str, exc)
            # Try to return cached data if available
            cached_df = self.storage.load_parquet(symbol, stage="cleaned", dataset_type="ohlcv")
            if cached_df is not None and not cached_df.empty:
                logger.info("Serving from local Parquet cache after network failure for %s", symbol)
                return cached_df
            raise

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch current quote details."""
        ticker_str = self._resolve_ticker(symbol)
        self._rate_limit()
        try:
            t = yf.Ticker(ticker_str)
            fast_info = getattr(t, "fast_info", None)
            if fast_info:
                last_price = float(fast_info.last_price or 0.0)
                prev_close = float(fast_info.previous_close or last_price)
                change = last_price - prev_close
                change_pct = (change / prev_close) * 100.0 if prev_close > 0 else 0.0
                return {
                    "symbol": symbol,
                    "ticker": ticker_str,
                    "price": round(last_price, 2),
                    "previous_close": round(prev_close, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "market_cap": getattr(fast_info, "market_cap", None),
                    "currency": "INR",
                    "exchange": "NSE" if ".NS" in ticker_str or "^NSE" in ticker_str else "BSE",
                }
        except Exception as exc:
            logger.warning("Could not fetch live quote for %s: %s", symbol, exc)

        # Fallback to last row of cleaned parquet data
        df = self.storage.load_parquet(symbol, stage="cleaned")
        if df is not None and not df.empty:
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2] if len(df) > 1 else last_row
            close = float(last_row["close"])
            prev_close = float(prev_row["close"])
            change = close - prev_close
            change_pct = (change / prev_close) * 100.0 if prev_close > 0 else 0.0
            return {
                "symbol": symbol,
                "ticker": ticker_str,
                "price": round(close, 2),
                "previous_close": round(prev_close, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "currency": "INR",
                "exchange": "NSE",
            }

        return {
            "symbol": symbol,
            "ticker": ticker_str,
            "price": 0.0,
            "previous_close": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "currency": "INR",
            "exchange": "NSE",
        }

    def fetch_intraday_ohlcv(
        self,
        symbol: str,
        interval: str = "5m",
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "5d",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Fetch historical intraday OHLCV for Indian equity/index, audited and normalized to IST."""
        valid_intervals = ["1m", "5m", "15m", "30m", "60m"]
        if interval not in valid_intervals:
            raise ValueError(f"Invalid intraday interval '{interval}'. Supported: {valid_intervals}")

        ticker_str = self._resolve_ticker(symbol)
        self._rate_limit()

        try:
            logger.info("Fetching intraday %s (%s) [%s]", symbol, ticker_str, interval)
            ticker = yf.Ticker(ticker_str)
            if start_date and end_date:
                df = ticker.history(start=start_date, end=end_date, interval=interval, auto_adjust=False)
            else:
                df = ticker.history(period=period, interval=interval, auto_adjust=False)

            if df.empty:
                logger.warning("No intraday bars returned for %s [%s]", ticker_str, interval)
                return pd.DataFrame()

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            df = df.reset_index()

            # Normalize column names to lowercase
            df.columns = [str(c).lower() for c in df.columns]

            # Rename Datetime/Date column to datetime
            dt_col = next((c for c in df.columns if c in ("datetime", "date", "timestamp")), None)
            if dt_col and dt_col != "datetime":
                df = df.rename(columns={dt_col: "datetime"})

            # Validate Indian exchange sessions and localize to IST
            cleaned_df, dup_dropped, oos_dropped = self.validator.normalize_and_filter_session(df)

            return cleaned_df

        except Exception as exc:
            logger.warning("Intraday download error for %s [%s]: %s", symbol, interval, exc)
            return pd.DataFrame()

    def fetch_option_chain(
        self,
        symbol: str,
        expiry: str | None = None,
    ) -> dict[str, Any]:
        """Fetch option chain for Indian symbol via Yahoo Finance or model synthesis."""
        ticker_str = self._resolve_ticker(symbol)
        self._rate_limit()

        try:
            t = yf.Ticker(ticker_str)
            available_expiries = list(getattr(t, "options", []) or [])
            target_exp = expiry if (expiry and expiry in available_expiries) else (available_expiries[0] if available_expiries else None)

            if target_exp:
                opt_chain = t.option_chain(target_exp)
                calls_df = opt_chain.calls
                puts_df = opt_chain.puts

                quotes: list[dict[str, Any]] = []
                for _, r in calls_df.iterrows():
                    quotes.append({
                        "strike": float(r["strike"]),
                        "option_type": "CE",
                        "last_price": float(r.get("lastPrice", 0.0)),
                        "open": float(r.get("lastPrice", 0.0)),
                        "high": float(r.get("lastPrice", 0.0)),
                        "low": float(r.get("lastPrice", 0.0)),
                        "close": float(r.get("lastPrice", 0.0)),
                        "volume": int(r.get("volume", 0) or 0),
                        "open_interest": int(r.get("openInterest", 0) or 0),
                        "lot_size": 25,
                    })
                for _, r in puts_df.iterrows():
                    quotes.append({
                        "strike": float(r["strike"]),
                        "option_type": "PE",
                        "last_price": float(r.get("lastPrice", 0.0)),
                        "open": float(r.get("lastPrice", 0.0)),
                        "high": float(r.get("lastPrice", 0.0)),
                        "low": float(r.get("lastPrice", 0.0)),
                        "close": float(r.get("lastPrice", 0.0)),
                        "volume": int(r.get("volume", 0) or 0),
                        "open_interest": int(r.get("openInterest", 0) or 0),
                        "lot_size": 25,
                    })

                return {
                    "symbol": symbol,
                    "expiry": target_exp,
                    "available_expiries": available_expiries,
                    "quotes": quotes,
                    "source": "Yahoo Finance (Live Options)",
                }

        except Exception as exc:
            logger.info("Live option chain unavailable from Yahoo for %s: %s", symbol, exc)

        return {
            "symbol": symbol,
            "expiry": expiry or "2024-12-26",
            "available_expiries": [expiry or "2024-12-26"],
            "quotes": [],
            "source": "Yahoo Finance (Options Unavailable)",
        }

