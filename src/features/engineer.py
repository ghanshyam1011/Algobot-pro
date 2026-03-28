"""
src/features/engineer.py
==========================
PURPOSE:
    Assemble the final feature matrix used for training and live inference.
    Combines preprocessed OHLCV data + all indicators into one clean DataFrame
    with additional engineered features (lag features, ratio features).

WHAT IT ADDS ON TOP OF indicators.py:
    - Lag features:  rsi_lag1, rsi_lag2, macd_lag1  (what was the value 1-2 candles ago?)
    - Return features: return_1h, return_4h, return_24h (price change over N hours)
    - Time features: hour_of_day, day_of_week (markets behave differently at different times)
    - Normalised price: close_vs_ema50 (is price above or below long-term average?)

WHY LAG FEATURES?
    XGBoost looks at one row at a time. It does not know what happened in the
    previous candle unless we explicitly add that information as columns.
    Lag features give the model a "memory" of recent history.

INPUT:  data/processed/BTC_USD_processed.csv
OUTPUT: data/processed/BTC_USD_features.csv  (ready for labeler.py)

DEPENDENCIES:
    pip install pandas numpy ta
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
from pathlib import Path

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_pipeline.preprocess import load_processed_coin, PROCESSED_DIR
from src.features.indicators import calculate_all_indicators, FEATURE_COLUMNS

log = logging.getLogger(__name__)


def add_lag_features(df: pd.DataFrame, cols: list, lags: list = [1, 2, 3]) -> pd.DataFrame:
    """
    Add lagged versions of key indicator columns.

    For each column in `cols` and each lag in `lags`, adds a new column
    named `{col}_lag{n}` containing the value from n rows ago.

    Example: rsi_lag1 = RSI value from 1 hour ago
             rsi_lag2 = RSI value from 2 hours ago

    Args:
        df:   DataFrame with indicator columns
        cols: Which columns to lag
        lags: How many periods back to create lags for

    Returns:
        pd.DataFrame with additional lag columns
    """
    for col in cols:
        for lag in lags:
            df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df


def add_return_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add price return features over multiple timeframes.

    return_1h  = % change in close price over last 1 candle  (1 hour)
    return_4h  = % change in close price over last 4 candles (4 hours)
    return_24h = % change in close price over last 24 candles (1 day)

    WHY: The model learns that certain return patterns (e.g. -5% over 24h
    followed by RSI < 30) tend to predict a bounce (BUY signal).
    """
    df["return_1h"]  = df["close"].pct_change(1)   * 100
    df["return_4h"]  = df["close"].pct_change(4)   * 100
    df["return_24h"] = df["close"].pct_change(24)  * 100
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add time-of-day and day-of-week features.

    WHY: Markets behave very differently at different times.
    - Asian session (00:00-08:00 UTC): lower volume, smaller moves
    - London open (08:00 UTC): volume spike, trend begins
    - US open (13:30 UTC): highest volume, largest moves
    - Weekend: lower volume for crypto, markets closed for stocks

    These features help the model learn these patterns.
    """
    df["hour_of_day"]  = df["datetime"].dt.hour
    df["day_of_week"]  = df["datetime"].dt.dayofweek  # 0=Monday, 6=Sunday
    df["is_weekend"]   = (df["day_of_week"] >= 5).astype(int)

    # Market session flags (UTC hours)
    df["session_asia"]   = ((df["hour_of_day"] >= 0)  & (df["hour_of_day"] < 8)).astype(int)
    df["session_london"] = ((df["hour_of_day"] >= 8)  & (df["hour_of_day"] < 13)).astype(int)
    df["session_us"]     = ((df["hour_of_day"] >= 13) & (df["hour_of_day"] < 22)).astype(int)

    return df


def add_price_context_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add features that describe WHERE the current price is relative to
    recent history.

    close_vs_ema50:  is price above (+) or below (-) 50-period EMA?
                     Positive = uptrend, negative = downtrend
    high_low_range:  (high - low) / close — how volatile was this candle?
    price_momentum:  direction and strength of recent price moves
    """
    # Price relative to long-term average (normalised)
    df["close_vs_ema50"] = (df["close"] - df["ema_50"]) / df["ema_50"] * 100

    # Candle body size as % of close (small = indecision, large = conviction)
    df["candle_body"]  = abs(df["close"] - df["open"]) / df["close"] * 100
    df["high_low_range"] = (df["high"] - df["low"]) / df["close"] * 100

    # Candle direction: +1 if close > open (green), -1 if close < open (red)
    df["candle_direction"] = np.sign(df["close"] - df["open"])

    return df


# ── final feature list (everything the model will see during training) ─────────

ENGINEERED_FEATURE_COLUMNS = FEATURE_COLUMNS + [
    # Lag features
    "rsi_lag1", "rsi_lag2", "rsi_lag3",
    "macd_line_lag1", "macd_line_lag2",
    "macd_histogram_lag1", "macd_histogram_lag2",
    # Return features
    "return_1h", "return_4h", "return_24h",
    # Time features
    "hour_of_day", "day_of_week", "is_weekend",
    "session_asia", "session_london", "session_us",
    # Price context features
    "close_vs_ema50", "candle_body", "high_low_range", "candle_direction",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all feature engineering steps and return the final feature DataFrame.

    Args:
        df: Preprocessed DataFrame (output of preprocess_coin())

    Returns:
        pd.DataFrame: Full feature matrix — original columns + all engineered features.
        NaN rows dropped. Ready for labeler.py.

    Example:
        >>> from src.features.engineer import engineer_features
        >>> df_features = engineer_features(df_processed)
        >>> print(df_features[ENGINEERED_FEATURE_COLUMNS].shape)
    """
    log.info("Engineering features ...")

    df = df.copy()

    # Step 1: Calculate all technical indicators
    df = calculate_all_indicators(df)

    # Step 2: Add lag features for key indicators
    df = add_lag_features(
        df,
        cols=["rsi", "macd_line", "macd_histogram"],
        lags=[1, 2, 3]
    )

    # Step 3: Add price return features
    df = add_return_features(df)

    # Step 4: Add time features
    df = add_time_features(df)

    # Step 5: Add price context features
    df = add_price_context_features(df)

    # Drop NaN rows introduced by lag and return calculations
    rows_before = len(df)
    df = df.dropna(subset=ENGINEERED_FEATURE_COLUMNS).reset_index(drop=True)
    rows_dropped = rows_before - len(df)

    log.info(f"  Feature engineering complete.")
    log.info(f"  Dropped {rows_dropped} warmup rows.")
    log.info(f"  Final shape: {df.shape}")
    log.info(f"  Total features: {len(ENGINEERED_FEATURE_COLUMNS)}")

    return df


def build_and_save_features(coin_name: str) -> pd.DataFrame:
    """
    Full pipeline for one coin: load → engineer → save features CSV.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        pd.DataFrame: Complete feature DataFrame.
    """
    df_processed = load_processed_coin(coin_name)
    df_features  = engineer_features(df_processed)

    out_path = os.path.join(PROCESSED_DIR, f"{coin_name}_features.csv")
    df_features.to_csv(out_path, index=False)
    log.info(f"  Saved features → {out_path}")

    return df_features


def load_features(coin_name: str) -> pd.DataFrame:
    """
    Load pre-engineered features CSV for a coin.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        pd.DataFrame with all feature columns + datetime + OHLCV
    """
    path = os.path.join(PROCESSED_DIR, f"{coin_name}_features.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Features file not found: {path}\n"
            f"Run build_and_save_features('{coin_name}') first."
        )
    return pd.read_csv(path, parse_dates=["datetime"])


if __name__ == "__main__":
    from src.data_pipeline.fetch_huggingface import COINS

    for coin_name in COINS.values():
        try:
            df = build_and_save_features(coin_name)
            print(f"\n{coin_name}: {df.shape}")
            print(df[["datetime", "close", "rsi", "return_24h", "close_vs_ema50"]].tail(3).to_string(index=False))
        except Exception as e:
            print(f"Error for {coin_name}: {e}")