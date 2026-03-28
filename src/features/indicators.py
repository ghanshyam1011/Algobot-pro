"""
src/features/indicators.py
============================
PURPOSE:
    Calculate all 12 technical indicators used as input features
    for the XGBoost model.

INDICATORS CALCULATED:
    Momentum  : RSI-14, Stochastic %K/%D
    Trend     : MACD line, MACD signal, MACD histogram, EMA-9, EMA-21, EMA-50
    Volatility: Bollinger Band upper/lower/width, ATR-14
    Volume    : OBV (On-Balance Volume), Volume SMA ratio

WHY THESE 12?
    Each indicator captures a DIFFERENT dimension of market behaviour.
    RSI tells you if it's overbought. MACD tells you if momentum is building.
    Bollinger Bands tell you if price is outside its normal range.
    Using all 12 together gives the model a complete picture.

INPUT:  pd.DataFrame with columns: datetime, open, high, low, close, volume
OUTPUT: Same DataFrame with 16 additional columns (the indicators + helpers)

DEPENDENCIES:
    pip install pandas numpy ta
"""

import logging
import numpy as np
import pandas as pd
import ta  # Technical Analysis library — wraps all indicator formulas

log = logging.getLogger(__name__)


# ── indicator calculation functions ──────────────────────────────────────────

def add_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    RSI — Relative Strength Index (0 to 100)

    WHAT IT MEANS:
        > 70 = overbought (price may fall soon)   → potential SELL signal
        < 30 = oversold  (price may rise soon)   → potential BUY signal
        40-60 = neutral zone

    Args:
        df:     DataFrame with 'close' column
        window: Lookback period (14 hours is the market standard)
    """
    df["rsi"] = ta.momentum.RSIIndicator(
        close=df["close"], window=window
    ).rsi()
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> pd.DataFrame:
    """
    MACD — Moving Average Convergence Divergence

    WHAT IT MEANS:
        macd_line > macd_signal  → bullish momentum building  (BUY bias)
        macd_line < macd_signal  → bearish momentum building  (SELL bias)
        macd_histogram crossing 0 = key signal crossover point

    Three output columns: macd_line, macd_signal, macd_histogram
    """
    macd_indicator = ta.trend.MACD(
        close=df["close"],
        window_fast=fast,
        window_slow=slow,
        window_sign=signal
    )
    df["macd_line"]      = macd_indicator.macd()
    df["macd_signal"]    = macd_indicator.macd_signal()
    df["macd_histogram"] = macd_indicator.macd_diff()
    return df


def add_bollinger_bands(df: pd.DataFrame, window: int = 20, std: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands — price envelope based on standard deviation

    WHAT IT MEANS:
        price > bb_upper  → price stretched too high, likely to snap back (SELL)
        price < bb_lower  → price stretched too low, likely to snap back (BUY)
        bb_width          → wider = more volatile market

    Three output columns: bb_upper, bb_lower, bb_width
    Also adds bb_pct (where is price within the band? 0=lower, 1=upper)
    """
    bb = ta.volatility.BollingerBands(
        close=df["close"], window=window, window_dev=std
    )
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = bb.bollinger_wband()   # (upper - lower) / middle  — normalised
    df["bb_pct"]   = bb.bollinger_pband()   # where price sits within band (0 to 1)
    return df


def add_ema(df: pd.DataFrame) -> pd.DataFrame:
    """
    EMA — Exponential Moving Averages (3 timeframes)

    WHAT IT MEANS:
        EMA-9   = short-term trend  (last ~9 hours)
        EMA-21  = medium-term trend (last ~21 hours)
        EMA-50  = long-term trend   (last ~50 hours)

        price > ema_50  → overall uptrend
        ema_9 > ema_21  → short-term momentum is bullish (BUY bias)
        ema_9 < ema_21  → short-term momentum is bearish (SELL bias)

    Also adds ema_cross: +1 if ema9 > ema21, -1 if ema9 < ema21
    """
    df["ema_9"]  = ta.trend.EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["ema_21"] = ta.trend.EMAIndicator(close=df["close"], window=21).ema_indicator()
    df["ema_50"] = ta.trend.EMAIndicator(close=df["close"], window=50).ema_indicator()

    # EMA crossover signal: +1 bullish, -1 bearish
    df["ema_cross"] = np.where(df["ema_9"] > df["ema_21"], 1, -1)
    return df


def add_atr(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    ATR — Average True Range

    WHAT IT MEANS:
        Measures how much price moves per candle on average.
        High ATR = volatile market (signals less reliable)
        Low ATR  = quiet market   (signals more reliable)

        We use ATR to set stop-loss distances in the signal formatter.
    """
    df["atr"] = ta.volatility.AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=window
    ).average_true_range()
    return df


def add_stochastic(df: pd.DataFrame, window: int = 14, smooth: int = 3) -> pd.DataFrame:
    """
    Stochastic Oscillator — %K and %D lines (0 to 100)

    WHAT IT MEANS:
        Similar to RSI but more sensitive to short-term moves.
        %K > 80 = overbought  (SELL bias)
        %K < 20 = oversold    (BUY bias)
        %K crossing above %D = bullish signal
    """
    stoch = ta.momentum.StochasticOscillator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=window,
        smooth_window=smooth
    )
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()
    return df


def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    """
    OBV — On-Balance Volume

    WHAT IT MEANS:
        Tracks whether volume is flowing INTO or OUT OF the asset.
        Rising OBV + rising price = strong uptrend (BUY confirmation)
        Falling OBV + rising price = weak uptrend  (price may reverse)

        We normalise OBV by dividing by its 20-period rolling mean
        so the value is comparable across different time periods.
    """
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(
        close=df["close"],
        volume=df["volume"]
    ).on_balance_volume()

    # Normalise: OBV relative to its own moving average
    df["obv_norm"] = df["obv"] / df["obv"].rolling(20).mean()
    return df


def add_volume_ratio(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    Volume Ratio — current volume vs. rolling average

    WHAT IT MEANS:
        volume_ratio = 2.0 means twice the normal volume.
        A signal with high volume behind it is more reliable.
        Spike in volume often precedes a big price move.
    """
    df["volume_sma"]   = df["volume"].rolling(window).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma"]
    return df


# ── master function ───────────────────────────────────────────────────────────

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all indicator functions to the DataFrame in the correct order.

    Args:
        df: Preprocessed DataFrame with columns:
            datetime, open, high, low, close, volume

    Returns:
        pd.DataFrame: Original columns PLUS all indicator columns.
        Rows at the start where indicators cannot be calculated
        (because there's not enough history) are DROPPED.

    Example:
        >>> from src.features.indicators import calculate_all_indicators
        >>> df_with_features = calculate_all_indicators(df)
        >>> print(df_with_features.columns.tolist())
    """
    log.info("Calculating technical indicators ...")

    df = df.copy()  # Never modify the original

    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)
    df = add_ema(df)
    df = add_atr(df)
    df = add_stochastic(df)
    df = add_obv(df)
    df = add_volume_ratio(df)

    # Drop the warmup rows where indicators are NaN
    # (EMA-50 needs 50 rows; MACD needs 26+9=35 rows → first ~50 rows will be NaN)
    rows_before = len(df)
    df = df.dropna().reset_index(drop=True)
    rows_dropped = rows_before - len(df)

    log.info(f"  Indicators calculated. Dropped {rows_dropped} warmup rows.")
    log.info(f"  Final shape: {df.shape}")
    log.info(f"  Columns: {[c for c in df.columns if c not in ['datetime','open','high','low','close','volume']]}")

    return df


# ── full feature column list (used by engineer.py and train.py) ───────────────

FEATURE_COLUMNS = [
    "rsi",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "bb_upper",
    "bb_lower",
    "bb_width",
    "bb_pct",
    "ema_9",
    "ema_21",
    "ema_50",
    "ema_cross",
    "atr",
    "stoch_k",
    "stoch_d",
    "obv_norm",
    "volume_ratio",
]


if __name__ == "__main__":
    # Quick test: load BTC processed data and calculate indicators
    from src.data_pipeline.preprocess import load_processed_coin

    df_raw = load_processed_coin("BTC_USD")
    df_ind = calculate_all_indicators(df_raw)

    print("\nSample output (last 5 rows):")
    print(df_ind[["datetime", "close", "rsi", "macd_line", "bb_pct", "ema_cross"]].tail(5).to_string(index=False))
    print(f"\nTotal features: {len(FEATURE_COLUMNS)}")