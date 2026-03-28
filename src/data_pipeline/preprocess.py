"""
src/data_pipeline/preprocess.py
=================================
PURPOSE:
    Take the raw CSV files saved by fetch_huggingface.py and produce
    clean, gap-filled, outlier-handled DataFrames ready for indicator
    calculation.

WHAT IT DOES:
    1. Loads raw CSV for a given coin
    2. Fills missing hourly candles (forward-fill gaps <= 3 hours)
    3. Removes extreme price outliers (z-score > 4)
    4. Resets index to a clean integer index
    5. Saves processed CSV to data/processed/

INPUT:  data/raw/BTC_USD_raw.csv
OUTPUT: data/processed/BTC_USD_processed.csv

HOW TO RUN:
    python src/data_pipeline/preprocess.py

DEPENDENCIES:
    pip install pandas numpy scipy
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_pipeline.fetch_huggingface import load_coin_from_csv, COINS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

PROCESSED_DIR = os.path.join("data", "processed")
MAX_GAP_FILL_HOURS = 3       # Forward-fill gaps up to this many hours
OUTLIER_ZSCORE_THRESHOLD = 4  # Remove rows where close price z-score exceeds this


def _fill_missing_candles(df: pd.DataFrame, coin_name: str) -> pd.DataFrame:
    """
    Resample to hourly frequency and forward-fill short gaps.
    Gaps longer than MAX_GAP_FILL_HOURS are left as NaN and dropped.
    """
    df = df.set_index("datetime")
    df.index = pd.DatetimeIndex(df.index)

    # Resample to 1-hour frequency — inserts NaN rows for missing candles
    df_resampled = df.resample("1h").first()

    # Count how many candles were missing
    missing = df_resampled["close"].isna().sum()
    if missing > 0:
        log.info(f"  {coin_name}: {missing} missing hourly candles found")

    # Forward-fill gaps up to MAX_GAP_FILL_HOURS consecutive NaNs
    df_resampled = df_resampled.fillna(method="ffill", limit=MAX_GAP_FILL_HOURS)

    # Drop any remaining NaN rows (gaps longer than limit)
    remaining_nulls = df_resampled["close"].isna().sum()
    if remaining_nulls > 0:
        log.warning(f"  {coin_name}: Dropping {remaining_nulls} rows with gaps > {MAX_GAP_FILL_HOURS}h")
        df_resampled = df_resampled.dropna(subset=["close"])

    df_resampled = df_resampled.reset_index()
    log.info(f"  {coin_name}: After gap fill → {len(df_resampled):,} rows")
    return df_resampled


def _remove_outliers(df: pd.DataFrame, coin_name: str) -> pd.DataFrame:
    """
    Remove rows where the close price is a statistical outlier.
    Uses z-score on log-returns (not raw price) to detect anomalies.
    """
    # Calculate log returns — outliers appear in returns, not absolute price
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))
    df = df.dropna(subset=["log_return"])

    z_scores = np.abs(stats.zscore(df["log_return"]))
    outlier_mask = z_scores > OUTLIER_ZSCORE_THRESHOLD

    outlier_count = outlier_mask.sum()
    if outlier_count > 0:
        log.warning(f"  {coin_name}: Removing {outlier_count} outlier rows (z > {OUTLIER_ZSCORE_THRESHOLD})")
        df = df[~outlier_mask]

    df = df.drop(columns=["log_return"])
    return df.reset_index(drop=True)


def _fix_ohlc_violations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fix rows where OHLC relationships are violated.
    e.g. if high < close, set high = close.
    These are rare data errors from the source.
    """
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"]  = df[["low",  "open", "close"]].min(axis=1)
    return df


def preprocess_coin(coin_name: str) -> pd.DataFrame:
    """
    Full preprocessing pipeline for one coin.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        pd.DataFrame: Clean processed DataFrame saved to data/processed/

    Example:
        >>> from src.data_pipeline.preprocess import preprocess_coin
        >>> df = preprocess_coin('BTC_USD')
        >>> print(df.shape)
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    log.info(f"Preprocessing {coin_name} ...")
    df = load_coin_from_csv(coin_name)

    df = _fill_missing_candles(df, coin_name)
    df = _remove_outliers(df, coin_name)
    df = _fix_ohlc_violations(df)

    # Final dtype enforcement
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype("float64")

    # Save
    out_path = os.path.join(PROCESSED_DIR, f"{coin_name}_processed.csv")
    df.to_csv(out_path, index=False)
    log.info(f"  Saved → {out_path}  ({len(df):,} rows)")

    return df


def load_processed_coin(coin_name: str) -> pd.DataFrame:
    """
    Load a previously preprocessed CSV.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        pd.DataFrame with columns: datetime, open, high, low, close, volume
    """
    path = os.path.join(PROCESSED_DIR, f"{coin_name}_processed.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Processed file not found: {path}\n"
            f"Run preprocess_coin('{coin_name}') first."
        )
    df = pd.read_csv(path, parse_dates=["datetime"])
    return df


def preprocess_all() -> dict:
    """Preprocess all coins defined in COINS."""
    results = {}
    for coin_name in COINS.values():
        try:
            results[coin_name] = preprocess_coin(coin_name)
        except Exception as e:
            log.error(f"Failed to preprocess {coin_name}: {e}")
    return results


if __name__ == "__main__":
    preprocess_all()