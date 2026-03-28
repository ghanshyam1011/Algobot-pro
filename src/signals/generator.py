"""
src/signals/generator.py
==========================
PURPOSE:
    The live signal engine. Runs every hour, fetches the latest market data,
    calculates indicators, runs the trained model, and produces a raw signal.
    This is the brain of the live system.

INPUT:  Latest OHLCV data from Yahoo Finance API
OUTPUT: dict with keys: coin, signal, confidence, price, probabilities

DEPENDENCIES:
    pip install yfinance pandas numpy joblib xgboost ta
"""

import logging
import sys
from pathlib import Path
import pandas as pd
import yfinance as yf

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.features.engineer import engineer_features, ENGINEERED_FEATURE_COLUMNS
from src.models.train import load_model
from src.features.labeler import LABEL_NAMES

log = logging.getLogger(__name__)

# How many historical candles to fetch for indicator calculation
# Must be > 50 (EMA-50 warmup) + lags (3) + returns (24) = at least 100
LOOKBACK_CANDLES = 200

# Yahoo Finance ticker map
YAHOO_TICKERS = {
    "BTC_USD": "BTC-USD",
    "ETH_USD": "ETH-USD",
    "BNB_USD": "BNB-USD",
    "SOL_USD": "SOL-USD",
}


def fetch_live_ohlcv(coin_name: str, candles: int = LOOKBACK_CANDLES) -> pd.DataFrame:
    """
    Fetch the latest N hourly candles from Yahoo Finance.

    Args:
        coin_name: e.g. 'BTC_USD'
        candles:   How many historical candles to fetch

    Returns:
        pd.DataFrame: columns datetime, open, high, low, close, volume
    """
    ticker = YAHOO_TICKERS.get(coin_name)
    if ticker is None:
        raise ValueError(f"Unknown coin: {coin_name}. Available: {list(YAHOO_TICKERS.keys())}")

    log.info(f"  Fetching live data for {coin_name} ({ticker}) ...")

    # yfinance: interval='1h', period covers enough days for our candles
    days_needed = max(10, candles // 20)
    raw = yf.download(
        ticker,
        period=f"{days_needed}d",
        interval="1h",
        progress=False,
        auto_adjust=True,
    )

    if raw.empty or len(raw) < 60:
        raise ValueError(f"Insufficient live data for {coin_name}: got {len(raw)} rows")

    df = raw.reset_index()
    
    # Handle both simple and MultiIndex columns from yfinance
    def flatten_column_name(col):
        if isinstance(col, tuple):
            # MultiIndex: take first element and lowercase
            return col[0].lower() if col[0] else col[1].lower()
        else:
            # Simple string column
            return str(col).lower()
    
    df.columns = [flatten_column_name(c) for c in df.columns]

    # Rename to standard columns
    rename = {"datetime": "datetime", "date": "datetime", "index": "datetime"}
    for old, new in rename.items():
        if old in df.columns:
            df = df.rename(columns={old: new})

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df[["datetime", "open", "high", "low", "close", "volume"]].dropna()
    df = df.sort_values("datetime").tail(candles).reset_index(drop=True)

    log.info(f"  Fetched {len(df)} candles for {coin_name} | "
             f"latest: {df['datetime'].iloc[-1]} @ {df['close'].iloc[-1]:.2f}")

    return df


def generate_signal(coin_name: str, model_version: str = "v1") -> dict:
    """
    Generate a live trading signal for one coin.

    Steps:
        1. Fetch latest 200 hourly candles
        2. Engineer all features (same as training)
        3. Take the LAST row (the most recent candle)
        4. Scale and run through the trained model
        5. Return prediction with probabilities

    Args:
        coin_name:     e.g. 'BTC_USD'
        model_version: 'v1' or 'tuned'

    Returns:
        dict: {
            coin, signal, confidence, price,
            p_buy, p_sell, p_hold,
            datetime, atr, rsi, macd_histogram
        }

    Example:
        >>> from src.signals.generator import generate_signal
        >>> sig = generate_signal('BTC_USD')
        >>> print(sig['signal'], sig['confidence'])
    """
    log.info(f"Generating signal for {coin_name} ...")

    # 1. Fetch live data
    df_live = fetch_live_ohlcv(coin_name)

    # 2. Engineer features
    df_features = engineer_features(df_live)

    if len(df_features) == 0:
        raise ValueError(f"Feature engineering returned empty DataFrame for {coin_name}")

    # 3. Take only the LAST (most recent) row
    latest = df_features.iloc[[-1]].copy()

    # 4. Load model and predict
    model, scaler, features = load_model(coin_name, model_version)
    X = scaler.transform(latest[features].values)

    proba      = model.predict_proba(X)[0]   # [P(BUY), P(SELL), P(HOLD)]
    label_int  = int(proba.argmax())
    confidence = float(proba.max())

    signal_dict = {
        "coin":           coin_name,
        "signal":         LABEL_NAMES[label_int],
        "signal_int":     label_int,
        "confidence":     round(confidence, 4),
        "p_buy":          round(float(proba[0]), 4),
        "p_sell":         round(float(proba[1]), 4),
        "p_hold":         round(float(proba[2]), 4),
        "price":          round(float(latest["close"].iloc[0]), 2),
        "datetime":       str(latest["datetime"].iloc[0]),
        "atr":            round(float(latest["atr"].iloc[0]), 2),
        "rsi":            round(float(latest["rsi"].iloc[0]), 2),
        "macd_histogram": round(float(latest["macd_histogram"].iloc[0]), 4),
        "volume_ratio":   round(float(latest["volume_ratio"].iloc[0]), 2),
    }

    log.info(
        f"  Signal: {signal_dict['signal']} | "
        f"Confidence: {signal_dict['confidence']:.1%} | "
        f"Price: {signal_dict['price']:.2f} | "
        f"RSI: {signal_dict['rsi']:.1f}"
    )

    return signal_dict


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = generate_signal("BTC_USD")
    import json
    print(json.dumps(result, indent=2))