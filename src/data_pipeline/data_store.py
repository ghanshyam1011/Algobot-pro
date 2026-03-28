"""
src/data_pipeline/data_store.py
=================================
PURPOSE:
    Central data access layer for reading and writing all project data files.
    All other modules use data_store to read/write data — never access
    file paths directly.

    Think of this as the "database" interface for the project.
    Even though we use CSV files (not a real database), all file paths
    and I/O logic are centralised here.

WHAT IT MANAGES:
    - Raw OHLCV CSVs          (data/raw/)
    - Processed feature CSVs  (data/processed/)
    - Live candle CSVs        (data/live/)
    - Labeled CSVs            (data/labels/)
    - Signal log JSON         (data/signal_log.json)
    - Model metadata JSON     (models/)

DEPENDENCIES:
    pip install pandas
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime, timezone
from typing import Optional

from config.settings import (
    RAW_DIR,
    PROCESSED_DIR,
    LIVE_DIR,
    LABELS_DIR,
    MODELS_DIR,
    SIGNAL_LOG,
    MAX_SIGNAL_LOG_ENTRIES,
    COINS,
)

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# DIRECTORY SETUP
# ══════════════════════════════════════════════════════════════

def ensure_all_dirs() -> None:
    """Create all required data directories if they don't exist."""
    for d in [RAW_DIR, PROCESSED_DIR, LIVE_DIR, LABELS_DIR, MODELS_DIR]:
        os.makedirs(d, exist_ok=True)
    log.debug("All data directories verified.")


# ══════════════════════════════════════════════════════════════
# RAW DATA
# ══════════════════════════════════════════════════════════════

def save_raw(df: pd.DataFrame, coin_name: str) -> str:
    """
    Save raw OHLCV DataFrame to data/raw/{coin}_raw.csv

    Args:
        df:        DataFrame with columns: datetime, open, high, low, close, volume
        coin_name: e.g. 'BTC_USD'

    Returns:
        str: Full path of saved file
    """
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, f"{coin_name}_raw.csv")
    df.to_csv(path, index=False)
    log.info(f"Saved raw data: {path} ({len(df):,} rows)")
    return path


def load_raw(coin_name: str) -> pd.DataFrame:
    """
    Load raw CSV for a coin.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        pd.DataFrame

    Raises:
        FileNotFoundError: If raw data hasn't been fetched yet
    """
    path = os.path.join(RAW_DIR, f"{coin_name}_raw.csv")
    _assert_exists(path, f"Run fetch_huggingface.py first to download {coin_name} data.")
    df = pd.read_csv(path, parse_dates=["datetime"])
    log.debug(f"Loaded raw {coin_name}: {len(df):,} rows")
    return df


def raw_exists(coin_name: str) -> bool:
    """Return True if raw data file exists for a coin."""
    return os.path.exists(os.path.join(RAW_DIR, f"{coin_name}_raw.csv"))


# ══════════════════════════════════════════════════════════════
# PROCESSED DATA
# ══════════════════════════════════════════════════════════════

def save_processed(df: pd.DataFrame, coin_name: str) -> str:
    """Save processed (cleaned + indicator-enriched) DataFrame."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    path = os.path.join(PROCESSED_DIR, f"{coin_name}_processed.csv")
    df.to_csv(path, index=False)
    log.info(f"Saved processed: {path} ({len(df):,} rows)")
    return path


def load_processed(coin_name: str) -> pd.DataFrame:
    """Load processed CSV for a coin."""
    path = os.path.join(PROCESSED_DIR, f"{coin_name}_processed.csv")
    _assert_exists(path, f"Run preprocess.py first for {coin_name}.")
    return pd.read_csv(path, parse_dates=["datetime"])


def save_features(df: pd.DataFrame, coin_name: str) -> str:
    """Save feature-engineered DataFrame."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    path = os.path.join(PROCESSED_DIR, f"{coin_name}_features.csv")
    df.to_csv(path, index=False)
    log.info(f"Saved features: {path} ({len(df):,} rows, {len(df.columns)} cols)")
    return path


def load_features(coin_name: str) -> pd.DataFrame:
    """Load feature CSV for a coin."""
    path = os.path.join(PROCESSED_DIR, f"{coin_name}_features.csv")
    _assert_exists(path, f"Run engineer.py first for {coin_name}.")
    return pd.read_csv(path, parse_dates=["datetime"])


def features_exist(coin_name: str) -> bool:
    """Return True if features file exists for a coin."""
    return os.path.exists(
        os.path.join(PROCESSED_DIR, f"{coin_name}_features.csv")
    )


# ══════════════════════════════════════════════════════════════
# LIVE DATA
# ══════════════════════════════════════════════════════════════

def save_live(df: pd.DataFrame, coin_name: str) -> str:
    """Save live candle data (fetched every hour)."""
    os.makedirs(LIVE_DIR, exist_ok=True)
    path = os.path.join(LIVE_DIR, f"{coin_name}_live.csv")
    df.to_csv(path, index=False)
    return path


def load_live(coin_name: str) -> pd.DataFrame:
    """
    Load cached live candles.

    Returns:
        pd.DataFrame, or empty DataFrame if no cache exists
    """
    path = os.path.join(LIVE_DIR, f"{coin_name}_live.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["datetime"])


def live_cache_age_hours(coin_name: str) -> float:
    """
    Return how many hours ago the live cache was last updated.
    Returns 999 if no cache exists.
    """
    path = os.path.join(LIVE_DIR, f"{coin_name}_live.csv")
    if not os.path.exists(path):
        return 999.0

    mtime    = os.path.getmtime(path)
    mod_dt   = datetime.fromtimestamp(mtime, tz=timezone.utc)
    now      = datetime.now(timezone.utc)
    age_h    = (now - mod_dt).total_seconds() / 3600
    return round(age_h, 2)


# ══════════════════════════════════════════════════════════════
# LABELED DATA
# ══════════════════════════════════════════════════════════════

def save_labeled(df: pd.DataFrame, coin_name: str) -> str:
    """Save labeled DataFrame (features + BUY/SELL/HOLD labels)."""
    os.makedirs(LABELS_DIR, exist_ok=True)
    path = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
    df.to_csv(path, index=False)
    log.info(f"Saved labeled: {path} ({len(df):,} rows)")
    return path


def load_labeled(coin_name: str) -> pd.DataFrame:
    """Load labeled CSV for a coin."""
    path = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
    _assert_exists(path, f"Run labeler.py first for {coin_name}.")
    return pd.read_csv(path, parse_dates=["datetime"])


def labeled_exists(coin_name: str) -> bool:
    """Return True if labeled file exists for a coin."""
    return os.path.exists(
        os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
    )


# ══════════════════════════════════════════════════════════════
# SIGNAL LOG
# ══════════════════════════════════════════════════════════════

def append_signal(signal: dict) -> None:
    """
    Append a new signal to the signal log JSON file.
    Keeps only the last MAX_SIGNAL_LOG_ENTRIES signals.

    Args:
        signal: Signal dict from formatter.py
    """
    signals = load_signal_log()
    signal["logged_at"] = datetime.now(timezone.utc).isoformat()
    signals.append(signal)
    signals = signals[-MAX_SIGNAL_LOG_ENTRIES:]

    os.makedirs(os.path.dirname(SIGNAL_LOG), exist_ok=True)
    with open(SIGNAL_LOG, "w") as f:
        json.dump(signals, f, indent=2, default=str)


def load_signal_log() -> list:
    """
    Load all signals from the signal log file.

    Returns:
        list: List of signal dicts, oldest first.
              Returns empty list if log doesn't exist.
    """
    if not os.path.exists(SIGNAL_LOG):
        return []
    try:
        with open(SIGNAL_LOG) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        log.warning("Signal log file is corrupted — starting fresh.")
        return []


def get_latest_signal(coin_name: str) -> Optional[dict]:
    """
    Get the most recent signal for one coin from the log.

    Args:
        coin_name: e.g. 'BTC_USD'

    Returns:
        dict or None if no signal found for this coin
    """
    signals = load_signal_log()
    # Walk backwards to find the latest for this coin
    for signal in reversed(signals):
        if signal.get("coin") == coin_name:
            return signal
    return None


def get_latest_signals_all() -> dict:
    """
    Get the most recent signal for every coin.

    Returns:
        dict: { 'BTC_USD': signal_dict, 'ETH_USD': signal_dict, ... }
    """
    signals = load_signal_log()
    latest  = {}
    for signal in reversed(signals):
        coin = signal.get("coin", "")
        if coin and coin not in latest:
            latest[coin] = signal
        if len(latest) == len(COINS):
            break
    return latest


def clear_signal_log() -> None:
    """Clear the signal log. Use with caution — irreversible."""
    if os.path.exists(SIGNAL_LOG):
        os.remove(SIGNAL_LOG)
        log.warning("Signal log cleared.")


# ══════════════════════════════════════════════════════════════
# PIPELINE STATUS
# ══════════════════════════════════════════════════════════════

def get_pipeline_status() -> dict:
    """
    Return the status of all data files for every coin.
    Used by the health checker and dashboard status page.

    Returns:
        dict: {
            'BTC_USD': {
                'raw':      True,
                'processed': True,
                'features': True,
                'labeled':  True,
                'model':    True,
                'live_age_h': 0.5,
            },
            ...
        }
    """
    status = {}
    for coin_name in COINS.values():
        model_path = os.path.join(MODELS_DIR, f"xgb_{coin_name}_v1.pkl")
        status[coin_name] = {
            "raw":        raw_exists(coin_name),
            "processed":  os.path.exists(
                              os.path.join(PROCESSED_DIR, f"{coin_name}_processed.csv")),
            "features":   features_exist(coin_name),
            "labeled":    labeled_exists(coin_name),
            "model":      os.path.exists(model_path),
            "live_age_h": live_cache_age_hours(coin_name),
        }
    return status


# ══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════

def _assert_exists(path: str, hint: str) -> None:
    """Raise FileNotFoundError with a helpful message if path doesn't exist."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"File not found: {path}\n"
            f"Hint: {hint}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    ensure_all_dirs()
    status = get_pipeline_status()

    print("\n── Pipeline Status ────────────────────────────────")
    print(f"  {'Coin':<12} {'Raw':>5} {'Proc':>5} {'Feat':>5} "
          f"{'Label':>6} {'Model':>6} {'Live age':>10}")
    print("  " + "─" * 55)

    for coin, s in status.items():
        def tick(v): return "✓" if v else "✗"
        print(
            f"  {coin:<12} {tick(s['raw']):>5} {tick(s['processed']):>5} "
            f"{tick(s['features']):>5} {tick(s['labeled']):>6} "
            f"{tick(s['model']):>6} {s['live_age_h']:>8.1f}h"
        )

    print("\n── Signal Log ─────────────────────────────────────")
    latest = get_latest_signals_all()
    if latest:
        for coin, sig in latest.items():
            print(f"  {coin}: {sig.get('signal','?')} "
                  f"({sig.get('confidence',0):.0%}) "
                  f"@ {sig.get('price',0):,.2f}")
    else:
        print("  No signals logged yet.")