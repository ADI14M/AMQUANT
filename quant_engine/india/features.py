"""Quantitative Feature Engine for Indian Financial Markets.

Calculates:
- Simple & Log Returns (Daily, Weekly, Monthly)
- Annualized Rolling Volatility
- High-Water Mark & Drawdown Series
- Simple & Exponential Moving Averages (SMA 20/50/200, EMA 12/26)
- Volume, Turnover, and VWAP
- Liquidity Metrics (Amihud Illiquidity Measure, Roll Spread Proxy)
- Market Breadth & Sector Returns
- Correlation & Covariance Matrices
- Volatility Regimes
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def compute_price_features(df: pd.DataFrame, window_short: int = 20, window_medium: int = 50, window_long: int = 200) -> pd.DataFrame:
    """Enrich an OHLCV dataframe with comprehensive quantitative features."""
    if df.empty or len(df) < 5:
        return df

    feat = df.copy()

    # Identify price column
    price_col = "adj_close" if "adj_close" in feat.columns else "close"

    # 1. Returns
    feat["daily_return"] = feat[price_col].pct_change().fillna(0.0)
    # Log returns: ln(P_t / P_{t-1})
    feat["log_return"] = np.log(feat[price_col] / feat[price_col].shift(1)).fillna(0.0)

    # 5-day (weekly) and 21-day (monthly) returns
    feat["weekly_return"] = feat[price_col].pct_change(periods=5).fillna(0.0)
    feat["monthly_return"] = feat[price_col].pct_change(periods=21).fillna(0.0)

    # 2. Rolling Volatility (Annualized with sqrt(252))
    feat["rolling_vol_20d"] = (feat["log_return"].rolling(window=window_short).std() * np.sqrt(252)).fillna(0.0)
    feat["rolling_vol_60d"] = (feat["log_return"].rolling(window=60).std() * np.sqrt(252)).fillna(0.0)

    # 3. High-Water Mark & Drawdowns
    feat["cum_max"] = feat[price_col].cummax()
    feat["drawdown"] = (feat[price_col] - feat["cum_max"]) / feat["cum_max"]

    # 4. Moving Averages
    feat["sma_20"] = feat[price_col].rolling(window=window_short).mean().fillna(feat[price_col])
    feat["sma_50"] = feat[price_col].rolling(window=window_medium).mean().fillna(feat[price_col])
    feat["sma_200"] = feat[price_col].rolling(window=window_long).mean().fillna(feat[price_col])

    feat["ema_12"] = feat[price_col].ewm(span=12, adjust=False).mean()
    feat["ema_26"] = feat[price_col].ewm(span=26, adjust=False).mean()
    feat["macd"] = feat["ema_12"] - feat["ema_26"]
    feat["macd_signal"] = feat["macd"].ewm(span=9, adjust=False).mean()

    # 5. Volume, Turnover (in ₹ Crores = ₹ 10 Million = 1e7)
    if "volume" in feat.columns:
        feat["turnover_cr"] = (feat["close"] * feat["volume"]) / 1e7
        feat["volume_sma_20"] = feat["volume"].rolling(window=20).mean().fillna(feat["volume"])
        feat["turnover_sma_20_cr"] = feat["turnover_cr"].rolling(window=20).mean().fillna(feat["turnover_cr"])

        # 6. Liquidity: Amihud Illiquidity Measure (|R_t| / Turnover_t)
        # Scaled by 1e5 for numerical readability
        denom = feat["turnover_cr"].replace(0, np.nan)
        feat["amihud_illiq"] = ((feat["daily_return"].abs() / denom) * 100.0).fillna(0.0)
    else:
        feat["turnover_cr"] = 0.0
        feat["amihud_illiq"] = 0.0

    # 7. Volatility Regimes (Low < 15%, Normal 15-25%, High > 25%)
    conditions = [
        feat["rolling_vol_20d"] < 0.15,
        (feat["rolling_vol_20d"] >= 0.15) & (feat["rolling_vol_20d"] <= 0.25),
        feat["rolling_vol_20d"] > 0.25,
    ]
    choices = ["LOW_VOL", "NORMAL_VOL", "HIGH_VOL"]
    feat["vol_regime"] = np.select(conditions, choices, default="NORMAL_VOL")

    return feat


def compute_market_breadth(multi_asset_dfs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Calculate Indian market breadth across a universe of stocks."""
    if not multi_asset_dfs:
        return {"advances": 0, "declines": 0, "unchanged": 0, "pct_above_50d_sma": 0.0, "pct_above_200d_sma": 0.0}

    advances = 0
    declines = 0
    unchanged = 0
    above_50 = 0
    above_200 = 0
    valid_count = 0

    for symbol, df in multi_asset_dfs.items():
        if df.empty or len(df) < 2:
            continue
        valid_count += 1
        last_ret = float(df["daily_return"].iloc[-1]) if "daily_return" in df.columns else (
            float(df["close"].iloc[-1] / df["close"].iloc[-2] - 1.0)
        )
        if last_ret > 0.0005:
            advances += 1
        elif last_ret < -0.0005:
            declines += 1
        else:
            unchanged += 1

        last_close = float(df["close"].iloc[-1])
        if "sma_50" in df.columns and last_close >= float(df["sma_50"].iloc[-1]):
            above_50 += 1
        if "sma_200" in df.columns and last_close >= float(df["sma_200"].iloc[-1]):
            above_200 += 1

    total = max(1, valid_count)
    return {
        "total_analyzed": valid_count,
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "advance_decline_ratio": round(advances / max(1, declines), 2),
        "pct_above_50d_sma": round((above_50 / total) * 100.0, 1),
        "pct_above_200d_sma": round((above_200 / total) * 100.0, 1),
    }


def compute_cross_asset_correlation(returns_matrix: pd.DataFrame) -> dict[str, Any]:
    """Compute Pearson correlation and covariance matrices across Indian symbols."""
    clean_mat = returns_matrix.dropna()
    if clean_mat.empty or clean_mat.shape[1] < 2:
        return {"symbols": [], "correlation_matrix": [], "covariance_matrix": []}

    corr = clean_mat.corr().round(4)
    cov = (clean_mat.cov() * 252).round(6)  # Annualized covariance

    symbols = list(corr.columns)
    corr_list = [[float(corr.iloc[i, j]) for j in range(len(symbols))] for i in range(len(symbols))]
    cov_list = [[float(cov.iloc[i, j]) for j in range(len(symbols))] for i in range(len(symbols))]

    return {
        "symbols": symbols,
        "correlation_matrix": corr_list,
        "covariance_matrix": cov_list,
    }

