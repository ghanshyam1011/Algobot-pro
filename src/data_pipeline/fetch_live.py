"""
src/data_pipeline/fetch_live.py
=================================
PURPOSE:
    Fetch the latest live OHLCV candles from Yahoo Finance every hour.
    This is the real-time data source used by the live signal engine.

    Unlike fetch_huggingface.py (which downloads years of history once),
    this file runs EVERY HOUR and fetches only the most recent candles
    needed to calculate indicators and generate a signal.

HOW IT FITS IN THE PIPELINE:
    fetch_huggingface.py  →  historical training data (runs once)
    fetch_live.py         →  live hourly data (runs every hour)

WHAT IT FETCHES:
    Last 200 hourly candles for each coin via Yahoo Finance API.
    200 candles = enough history to calculate all indicators
    (EMA-50 needs 50, MACD needs 35, lags need 3 → 200 gives headroom)

OUTPUT:
    Returns a clean DataFrame with columns:
    datetime | open | high | low | close | volume

    Also saves to data/live/{coin}_live.csv for caching.

DEPENDENCIES:
    pip install yfinance pandas
"""

import os
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

from config.settings import (
    COINS,
    YAHOO_TICKERS,
    LIVE_DIR,
    LOOKBACK_CANDLES,
    STANDARD_COLUMNS if hasattr(__import__('config.settings', fromlist=['STANDARD_COLUMNS']), 'STANDARD_COLUMNS') else None,
)

log = logging.getLogger(__name__)

STANDARD_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


def fetch_live_candles(
    coin_name: str,
    candles: int = LOOKBACK_CANDLES,
    save_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch the latest N hourly candles for one coin from Yahoo Finance.

    Args:
        coin_name:   e.g. 'BTC_USD'
        candles:     How many historical candles to fetch (default 200)
        save_cache:  If True, saves to data/live/ for debugging

    Returns:
        pd.DataFrame with columns: datetime, open, high, low, close, volume
        Sorted oldest → newest, no nulls.

    Raises:
        ValueError: If Yahoo Finance returns insufficient data

    Example:
        >>> from src.data_pipeline.fetch_live import fetch_live_candles
        >>> df = fetch_live_candles('BTC_USD')
        >>> print(df.tail(3))
    """
    ticker = YAHOO_TICKERS.get(coin_name)
    if not ticker:
        raise ValueError(
            f"Unknown coin: {coin_name}\n"
            f"Available: {list(YAHOO_TICKERS.keys())}"
        )

    # yfinance hourly data: max lookback is ~730 days
    # We request enough days to get our candles (1 day = ~24 candles)
    days_needed = max(10, (candles // 20) + 2)

    log.info(f"Fetching live data: {coin_name} ({ticker}) — last {candles} candles ...")

    try:
        raw = yf.download(
            ticker,
            period=f"{days_needed}d",
            interval="1h",
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        raise ValueError(f"Yahoo Finance download failed for {ticker}: {e}")

    if raw is None or raw.empty:
        raise ValueError(
            f"Yahoo Finance returned no data for {ticker}.\n"
            f"Check your internet connection and try again."
        )

    # ── Clean and standardise ─────────────────────────────────────────────────
    df = raw.reset_index()

    # Flatten MultiIndex columns (yfinance sometimes returns these)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() if c[1] == "" else c[0].lower()
                      for c in df.columns]
    else:
        df.columns = [str(c).lower().strip() for c in df.columns]

    # Rename datetime column (yfinance uses 'Datetime' or 'Date')
    for old in ["datetime", "date", "index", "timestamp"]:
        if old in df.columns:
            df = df.rename(columns={old: "datetime"})
            break

    # Parse datetime with UTC timezone
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")

    # Cast OHLCV to float
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep only standard columns
    missing = [c for c in STANDARD_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns after processing: {missing}\n"
            f"Available: {list(df.columns)}"
        )

    df = df[STANDARD_COLUMNS].copy()

    # Drop nulls, sort, deduplicate
    df = df.dropna()
    df = df.sort_values("datetime").reset_index(drop=True)
    df = df.drop_duplicates(subset=["datetime"], keep="last")

    # Fix OHLC violations
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"]  = df[["low",  "open", "close"]].min(axis=1)

    # Take only the last N candles we need
    df = df.tail(candles).reset_index(drop=True)

    if len(df) < 60:
        raise ValueError(
            f"Insufficient live data for {coin_name}: got {len(df)} rows, need >= 60.\n"
            f"Yahoo Finance may have rate-limited you. Try again in a few minutes."
        )

    latest_time  = df["datetime"].iloc[-1]
    latest_price = df["close"].iloc[-1]
    log.info(
        f"  {coin_name}: {len(df)} candles fetched | "
        f"latest: {latest_time.strftime('%Y-%m-%d %H:%M UTC')} "
        f"@ {latest_price:,.2f}"
    )

    # ── Save cache ────────────────────────────────────────────────────────────
    if save_cache:
        os.makedirs(LIVE_DIR, exist_ok=True)
        cache_path = os.path.join(LIVE_DIR, f"{coin_name}_live.csv")
        df.to_csv(cache_path, index=False)

    return df


def fetch_all_live(candles: int = LOOKBACK_CANDLES) -> dict:
    """
    Fetch live candles for all coins.

    Args:
        candles: Number of candles to fetch per coin

    Returns:
        dict: { 'BTC_USD': DataFrame, 'ETH_USD': DataFrame, ... }
        Only includes coins that were fetched successfully.

    Example:
        >>> from src.data_pipeline.fetch_live import fetch_all_live
        >>> data = fetch_all_live()
        >>> print(data.keys())
    """
    results = {}
    for coin_name in COINS.values():
        try:
            results[coin_name] = fetch_live_candles(coin_name, candles=candles)
        except Exception as e:
            log.error(f"  Failed to fetch {coin_name}: {e}")
    return results


def load_live_cache(coin_name: str) -> pd.DataFrame:
    """
    Load the most recently cached live data from disk.
    Used when Yahoo Finance is temporarily unavailable.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        pd.DataFrame or empty DataFrame if cache doesn't exist

    Example:
        >>> from src.data_pipeline.fetch_live import load_live_cache
        >>> df = load_live_cache('BTC_USD')
    """
    cache_path = os.path.join(LIVE_DIR, f"{coin_name}_live.csv")
    if not os.path.exists(cache_path):
        log.warning(f"No live cache found for {coin_name}: {cache_path}")
        return pd.DataFrame()

    df = pd.read_csv(cache_path, parse_dates=["datetime"])

    # Check how stale the cache is
    if not df.empty:
        latest   = pd.to_datetime(df["datetime"].iloc[-1], utc=True)
        now      = datetime.now(timezone.utc)
        age_h    = (now - latest).total_seconds() / 3600
        if age_h > 3:
            log.warning(
                f"  {coin_name} cache is {age_h:.1f}h old — "
                f"data may be stale. Recommend re-fetching."
            )

    log.info(f"  Loaded {coin_name} from live cache: {len(df)} rows")
    return df


def get_current_price(coin_name: str) -> float:
    """
    Get just the current price for a coin — fast, single call.
    Used for quick price checks without full candle history.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        float: Current price, or 0.0 if fetch fails

    Example:
        >>> from src.data_pipeline.fetch_live import get_current_price
        >>> price = get_current_price('BTC_USD')
        >>> print(f"BTC: {price:,.2f}")
    """
    ticker = YAHOO_TICKERS.get(coin_name)
    if not ticker:
        return 0.0

    try:
        data = yf.download(ticker, period="1d", interval="1h",
                           progress=False, auto_adjust=True)
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception:
        pass

    # Fallback: use cached live data
    df = load_live_cache(coin_name)
    if not df.empty:
        return float(df["close"].iloc[-1])

    return 0.0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )

    print("Fetching live data for all coins ...")
    data = fetch_all_live(candles=200)

    print("\n── Live Data Summary ──")
    for coin, df in data.items():
        print(f"  {coin}: {len(df)} candles | "
              f"latest price: {df['close'].iloc[-1]:,.2f} | "
              f"at: {df['datetime'].iloc[-1]}")