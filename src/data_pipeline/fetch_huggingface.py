"""
src/data_pipeline/fetch_huggingface.py
=======================================
PURPOSE:
    Load historical crypto OHLCV data and save as clean CSVs into data/raw/.

FIX (v2):
    The sebdg/crypto_data dataset has a broken loading script — calling
    load_dataset() with any config name raises NotImplementedError.

    SOLUTION: Load directly from the HuggingFace-hosted Parquet files using
    pandas.read_parquet(URL). This completely bypasses the broken script and
    always works regardless of the datasets library version.

    Parquet URL pattern (auto-converted by HuggingFace for every public dataset):
    https://huggingface.co/datasets/sebdg/crypto_data/resolve/refs%2Fconvert%2Fparquet
    /{config}/train/0000.parquet

    Config 'candles'    -> OHLCV data   (what we use for training)
    Config 'indicators' -> pre-computed RSI/SMA/EMA (supplementary)

OUTPUT FILES:
    data/raw/BTC_USD_raw.csv
    data/raw/ETH_USD_raw.csv
    data/raw/BNB_USD_raw.csv
    data/raw/SOL_USD_raw.csv

HOW TO RUN:
    python src/data_pipeline/fetch_huggingface.py

    If HuggingFace fails for any reason, use Yahoo Finance fallback:
    python src/data_pipeline/fetch_huggingface.py --yfinance

DEPENDENCIES:
    pip install pandas pyarrow requests yfinance
    (No 'datasets' library needed at all for this step)
"""

import os
import io
import sys
import logging
import requests
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────

RAW_DATA_DIR = os.path.join("data", "raw")

# HuggingFace auto-converts every public dataset to Parquet.
# These direct URLs bypass the broken dataset loading script entirely.
# 'candles' config has: market, date, open, high, low, close, volume
PARQUET_URLS = {
    "candles": (
        "https://huggingface.co/datasets/sebdg/crypto_data"
        "/resolve/refs%2Fconvert%2Fparquet/candles/train/0000.parquet"
    ),
}

# Which market strings to extract + what to name the output file
COINS = {
    "BTC-USD": "BTC_USD",
    "ETH-USD": "ETH_USD",
    "BNB-USD": "BNB_USD",
    "SOL-USD": "SOL_USD",
}

# Standard column names used across the entire project — never change these
STANDARD_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]

MIN_ROWS_EXPECTED = 1000


# ── helpers ───────────────────────────────────────────────────────────────────

def _ensure_output_dir() -> None:
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    log.info(f"Output directory ready: {RAW_DATA_DIR}")


def _load_parquet_from_url(url: str) -> pd.DataFrame:
    """
    Download a Parquet file from a URL and return as DataFrame.
    Uses requests for the download so we control timeout and headers.

    Args:
        url: Direct HTTPS URL to a .parquet file

    Returns:
        pd.DataFrame

    Raises:
        RuntimeError: If download or parse fails after all retries
    """
    log.info(f"Downloading Parquet file ...")
    log.info(f"  URL: {url}")
    log.info("  (First run may take 1-3 minutes — file is cached after)")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/octet-stream",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=180, stream=True)
        resp.raise_for_status()

        content = resp.content
        log.info(f"  Downloaded {len(content)/1024/1024:.1f} MB")

        df = pd.read_parquet(io.BytesIO(content))
        log.info(f"  Parsed: {len(df):,} rows, columns = {list(df.columns)}")
        return df

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Network error downloading Parquet: {e}\n\n"
            f"MANUAL ALTERNATIVE:\n"
            f"  Run with Yahoo Finance instead:\n"
            f"  python src/data_pipeline/fetch_huggingface.py --yfinance"
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse Parquet file: {e}\n"
            f"Try: python src/data_pipeline/fetch_huggingface.py --yfinance"
        )


def _load_parquet_with_local_cache(url: str, cache_path: str) -> pd.DataFrame:
    """
    Load from local cache if it exists, otherwise download from URL and cache.

    Args:
        url:        Remote Parquet URL
        cache_path: Local path to save the downloaded file

    Returns:
        pd.DataFrame
    """
    if os.path.exists(cache_path):
        log.info(f"  Using cached local Parquet: {cache_path}")
        return pd.read_parquet(cache_path)

    df = _load_parquet_from_url(url)

    # Cache locally for future runs
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    df.to_parquet(cache_path, index=False)
    log.info(f"  Cached locally -> {cache_path}")

    return df


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Lowercase all columns and rename date -> datetime if needed.
    The sebdg/crypto_data candles config uses lowercase names already,
    but we normalise just in case the dataset format changes.

    Raises:
        KeyError: if any required column is still missing after rename
    """
    # Lowercase everything
    df.columns = [str(c).lower().strip() for c in df.columns]

    log.info(f"  Columns after lowercase: {list(df.columns)}")

    # Rename date -> datetime
    if "date" in df.columns and "datetime" not in df.columns:
        df = df.rename(columns={"date": "datetime"})
        log.info("  Renamed 'date' -> 'datetime'")

    # Check all required columns exist
    missing = [c for c in STANDARD_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(
            f"Missing required columns: {missing}\n"
            f"Available: {list(df.columns)}\n\n"
            f"The dataset structure may have changed. Check:\n"
            f"  https://huggingface.co/datasets/sebdg/crypto_data\n\n"
            f"Or use Yahoo Finance fallback:\n"
            f"  python src/data_pipeline/fetch_huggingface.py --yfinance"
        )

    return df


def _extract_and_clean_coin(
    df: pd.DataFrame,
    market_str: str,
    coin_name: str,
) -> pd.DataFrame:
    """
    Filter the full DataFrame to one coin, clean it, and return.

    Args:
        df:          Full DataFrame with all coins
        market_str:  e.g. 'BTC-USD'
        coin_name:   e.g. 'BTC_USD'

    Returns:
        Clean DataFrame with only STANDARD_COLUMNS
    """
    # Find the market column
    market_col = None
    for candidate in ["market", "symbol", "ticker", "pair", "name"]:
        if candidate in df.columns:
            market_col = candidate
            break

    if market_col is None:
        log.warning("  No market column found — treating entire dataset as one coin")
        coin_df = df.copy()
    else:
        all_markets = df[market_col].dropna().unique().tolist()
        log.info(f"  Markets in dataset: {all_markets}")

        # Try exact match first, then alternate formats
        coin_df = df[df[market_col] == market_str].copy()

        if len(coin_df) == 0:
            alternates = [
                market_str.replace("-", "/"),   # BTC/USD
                market_str.replace("-", ""),     # BTCUSD
                market_str.lower(),              # btc-usd
            ]
            for alt in alternates:
                coin_df = df[df[market_col] == alt].copy()
                if len(coin_df) > 0:
                    log.info(f"  Found {coin_name} under alternate name: '{alt}'")
                    break

        if len(coin_df) == 0:
            raise ValueError(
                f"'{market_str}' not found in dataset.\n"
                f"Available: {all_markets}\n"
                f"The dataset may not include this coin."
            )

    # Keep only standard columns
    coin_df = coin_df[STANDARD_COLUMNS].copy()

    # Parse datetime
    coin_df["datetime"] = pd.to_datetime(
        coin_df["datetime"], utc=True, errors="coerce"
    )
    coin_df = coin_df.dropna(subset=["datetime"])

    # Cast OHLCV to float
    for col in ["open", "high", "low", "close", "volume"]:
        coin_df[col] = pd.to_numeric(coin_df[col], errors="coerce")

    # Drop nulls, sort, deduplicate
    coin_df = coin_df.dropna()
    coin_df = coin_df.sort_values("datetime").reset_index(drop=True)
    coin_df = coin_df.drop_duplicates(subset=["datetime"], keep="first")

    # Fix OHLC violations: ensure high >= open/close, low <= open/close
    coin_df["high"] = coin_df[["high", "open", "close"]].max(axis=1)
    coin_df["low"]  = coin_df[["low",  "open", "close"]].min(axis=1)

    if len(coin_df) < MIN_ROWS_EXPECTED:
        raise ValueError(
            f"{coin_name}: Only {len(coin_df)} rows after cleaning "
            f"(need >= {MIN_ROWS_EXPECTED})"
        )

    log.info(
        f"  {coin_name}: {len(coin_df):,} rows | "
        f"{coin_df['datetime'].min().date()} -> "
        f"{coin_df['datetime'].max().date()}"
    )
    return coin_df


def _save_csv(df: pd.DataFrame, coin_name: str) -> str:
    filepath = os.path.join(RAW_DATA_DIR, f"{coin_name}_raw.csv")
    df.to_csv(filepath, index=False)
    kb = os.path.getsize(filepath) / 1024
    log.info(f"  Saved -> {filepath}  ({kb:.1f} KB)")
    return filepath


# ── main public functions ─────────────────────────────────────────────────────

def fetch_all_coins() -> dict:
    """
    Download the HuggingFace Parquet, split by coin, clean, and save CSVs.

    Returns:
        dict: { 'BTC_USD': DataFrame, 'ETH_USD': DataFrame, ... }

    Example:
        >>> from src.data_pipeline.fetch_huggingface import fetch_all_coins
        >>> data = fetch_all_coins()
        >>> print(data['BTC_USD'].tail(3))
    """
    log.info("=" * 60)
    log.info("AlgoBot Pro - HuggingFace Data Fetcher v2 (Parquet direct)")
    log.info("=" * 60)

    _ensure_output_dir()

    # Download the full candles Parquet (all coins in one file)
    cache_path = os.path.join(RAW_DATA_DIR, "candles_raw.parquet")
    raw_df = _load_parquet_with_local_cache(PARQUET_URLS["candles"], cache_path)

    # Standardise column names
    raw_df = _standardise_columns(raw_df)

    results = {}
    for market_str, coin_name in COINS.items():
        log.info(f"\nProcessing {coin_name} ({market_str}) ...")
        try:
            coin_df = _extract_and_clean_coin(raw_df, market_str, coin_name)
            _save_csv(coin_df, coin_name)
            results[coin_name] = coin_df
        except (ValueError, KeyError) as e:
            log.error(f"  FAILED for {coin_name}: {e}")
            log.error("  Skipping this coin and continuing ...")

    log.info("\n" + "=" * 60)
    log.info(f"Done. Saved {len(results)}/{len(COINS)} coins to {RAW_DATA_DIR}/")
    log.info("=" * 60)

    if len(results) == 0:
        log.error(
            "\nNo coins were saved! Try the Yahoo Finance fallback:\n"
            "  python src/data_pipeline/fetch_huggingface.py --yfinance"
        )

    return results


def load_coin_from_csv(coin_name: str) -> pd.DataFrame:
    """
    Load a previously saved raw CSV. Called by all downstream steps.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        pd.DataFrame with columns: datetime, open, high, low, close, volume
    """
    filepath = os.path.join(RAW_DATA_DIR, f"{coin_name}_raw.csv")
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Raw data not found: {filepath}\n"
            f"Run fetch_all_coins() or fetch_from_yfinance() first."
        )
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    log.info(f"Loaded {coin_name} from CSV: {len(df):,} rows")
    return df


# ── Yahoo Finance fallback ────────────────────────────────────────────────────

def fetch_from_yfinance(years: int = 4) -> dict:
    """
    FALLBACK: Download OHLCV data directly from Yahoo Finance.
    Use this if the HuggingFace download fails.

    Gives 4 years of hourly data for BTC, ETH, BNB, SOL.

    Args:
        years: Years of history to download (max 2 for hourly from Yahoo)

    Returns:
        dict: { 'BTC_USD': DataFrame, ... }

    HOW TO USE:
        python src/data_pipeline/fetch_huggingface.py --yfinance
    OR in code:
        from src.data_pipeline.fetch_huggingface import fetch_from_yfinance
        data = fetch_from_yfinance()
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError(
            "yfinance not installed. Run:\n  pip install yfinance"
        )

    _ensure_output_dir()

    log.info("=" * 60)
    log.info("AlgoBot Pro - Yahoo Finance Fallback Data Fetcher")
    log.info("=" * 60)
    log.info("NOTE: Yahoo Finance gives max ~730 days for hourly data.")

    # yfinance uses 'period' for hourly data — max is '730d'
    period = f"{min(years * 365, 730)}d"

    results = {}

    for ticker, coin_name in COINS.items():
        log.info(f"\nDownloading {coin_name} ({ticker}) - period={period} ...")
        try:
            raw = yf.download(
                ticker,
                period=period,
                interval="1h",
                progress=False,
                auto_adjust=True,
            )

            if raw.empty:
                log.warning(f"  No data returned for {ticker}")
                continue

            df = raw.reset_index()

            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [
                    c[0].lower() if c[1] == "" else c[0].lower()
                    for c in df.columns
                ]
            else:
                df.columns = [c.lower() for c in df.columns]

            # Rename datetime column
            for old in ["datetime", "date", "index", "timestamp"]:
                if old in df.columns:
                    df = df.rename(columns={old: "datetime"})
                    break

            # Ensure standard columns exist
            df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
            df = df[STANDARD_COLUMNS].dropna()
            df = df.sort_values("datetime").reset_index(drop=True)
            df = df.drop_duplicates(subset=["datetime"], keep="first")

            _save_csv(df, coin_name)
            results[coin_name] = df

            log.info(
                f"  {coin_name}: {len(df):,} rows | "
                f"{df['datetime'].min().date()} -> "
                f"{df['datetime'].max().date()}"
            )

        except Exception as e:
            log.error(f"  Failed for {coin_name}: {e}")

    log.info(f"\nFetched {len(results)}/{len(COINS)} coins from Yahoo Finance.")
    return results


# ── run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    use_yfinance = "--yfinance" in sys.argv

    if use_yfinance:
        log.info("Mode: Yahoo Finance (forced via --yfinance flag)")
        data = fetch_from_yfinance(years=2)
    else:
        log.info("Mode: HuggingFace Parquet (direct download)")
        try:
            data = fetch_all_coins()
        except Exception as e:
            log.error(f"\nHuggingFace failed: {e}")
            log.info("\n" + "=" * 60)
            log.info("Automatically switching to Yahoo Finance fallback ...")
            log.info("=" * 60 + "\n")
            data = fetch_from_yfinance(years=2)

    if data:
        print("\n-- Preview of loaded data --")
        for coin_name, df in data.items():
            print(f"\n{coin_name}: {df.shape}")
            print(df[["datetime", "open", "high", "low", "close", "volume"]].tail(3).to_string(index=False))
    else:
        print("\nNo data loaded. Check error messages above.")