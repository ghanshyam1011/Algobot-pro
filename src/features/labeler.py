"""
src/features/labeler.py
=========================
PURPOSE:
    Create trading labels (BUY/SELL/HOLD) from engineered features.
    Uses a simple rules-based labeling strategy:
    
    - BUY: If close price rises > 2% in the next 24 hours
    - SELL: If close price falls > 2% in the next 24 hours  
    - HOLD: Otherwise (neutral movement or conflicting signals)

INPUT:  data/labels/BTC_USD_labeled.csv  (features + target label)
OUTPUT: Used by train.py, backtest.py, tune.py for model training

LABEL DEFINITIONS:
    LABEL_BUY   = 1  (price expected to go up)
    LABEL_SELL  = 2  (price expected to go down)
    LABEL_HOLD  = 0  (neutral / no clear direction)

DEPENDENCIES:
    pip install pandas numpy
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

log = logging.getLogger(__name__)

# Label constants (must match test expectations and libel definitions)
LABEL_BUY   = 0
LABEL_SELL  = 1
LABEL_HOLD  = 2

LABEL_NAMES = {
    LABEL_BUY:   "BUY",
    LABEL_SELL:  "SELL",
    LABEL_HOLD:  "HOLD",
}

LABELS_DIR = os.path.join("data", "labels")

# Labeling thresholds
FORWARD_HOURS = 24              # Look ahead N hours for label
THRESHOLD_PCT = 0.02            # 2% price change threshold
RETURN_THRESHOLD = THRESHOLD_PCT  # Alias for backward compatibility


def create_labels(
    df: pd.DataFrame,
    coin_name: str = "UNKNOWN",
    forward_hours: int = None,
    threshold_pct: float = None,
    return_threshold: float = None
) -> pd.DataFrame:
    """
    Create BUY/SELL/HOLD labels based on future price movements.
    
    Logic:
        - Calculate what price will be N hours from now
        - If return > +threshold → BUY label (1)
        - If return < -threshold → SELL label (2)
        - Else → HOLD label (0)
    
    Args:
        df: DataFrame with 'close' and 'datetime' columns
        coin_name: Name of coin (for logging, default: "UNKNOWN")
        forward_hours: How many hours to look ahead (default: FORWARD_HOURS global)
        threshold_pct: Return threshold as percentage (default: THRESHOLD_PCT global)
        return_threshold: Return threshold (alias, use threshold_pct instead)
    
    Returns:
        DataFrame with columns: datetime, label, return
    """
    # Handle parameter defaults
    if forward_hours is None:
        forward_hours = FORWARD_HOURS
    
    if threshold_pct is not None:
        threshold = threshold_pct / 100.0  # Convert percentage to decimal
    elif return_threshold is not None:
        threshold = return_threshold
    else:
        threshold = THRESHOLD_PCT
    
    df = df.copy()
    df = df.reset_index(drop=True)
    
    # Calculate forward return over forward_hours
    df[f"close_{forward_hours}h_future"] = df["close"].shift(-forward_hours)  # N candles ahead
    df[f"return_{forward_hours}h"] = (df[f"close_{forward_hours}h_future"] - df["close"]) / df["close"]
    
    # Drop the last N rows (they don't have a full forward-looking period)
    df = df.iloc[:-forward_hours].copy()
    
    # Create labels
    df["label"] = LABEL_HOLD
    return_col = f"return_{forward_hours}h"
    df.loc[df[return_col] > threshold, "label"] = LABEL_BUY
    df.loc[df[return_col] < -threshold, "label"] = LABEL_SELL
    
    # Count labels
    buy_count = (df["label"] == LABEL_BUY).sum()
    sell_count = (df["label"] == LABEL_SELL).sum()
    hold_count = (df["label"] == LABEL_HOLD).sum()
    
    if coin_name != "UNKNOWN":
        log.info(f"  {coin_name}: Created labels")
        log.info(f"    BUY:  {buy_count:6d} ({buy_count/len(df):6.1%})")
        log.info(f"    SELL: {sell_count:6d} ({sell_count/len(df):6.1%})")
        log.info(f"    HOLD: {hold_count:6d} ({hold_count/len(df):6.1%})")
    
    # Return only necessary columns, convert return to percentage
    result = df[["datetime", "label"]].copy()
    result["future_return"] = df[return_col] * 100  # Convert to percentage format
    return result


def load_labeled(coin_name: str) -> pd.DataFrame:
    """
    Load a pre-labeled CSV file for a coin.
    
    Args:
        coin_name: e.g. 'BTC_USD'
    
    Returns:
        pd.DataFrame with columns: datetime, open, high, low, close, volume, 
                                   (all indicators), label
    
    Raises:
        FileNotFoundError: If labeled file doesn't exist
    """
    os.makedirs(LABELS_DIR, exist_ok=True)
    
    path = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Labeled data not found: {path}\n"
            f"Run the full pipeline: preprocess → engineer → label_all"
        )
    
    df = pd.read_csv(path, parse_dates=["datetime"])
    return df


def label_all() -> dict:
    """
    Create labels for all coins and save as CSV.
    
    This is called after engineer.py to add the target label column.
    """
    from src.features.engineer import build_and_save_features
    from src.data_pipeline.preprocess import COINS
    
    results = {}
    
    for coin_name in COINS.values():
        try:
            log.info(f"Labeling {coin_name} ...")
            
            # Load engineered features
            df_features = build_and_save_features(coin_name)
            
            # Create labels
            labels_subset = create_labels(df_features, coin_name)
            
            # Merge labels into features
            df_labeled = df_features.merge(
                labels_subset[["datetime", "label"]],
                on="datetime",
                how="inner"
            )
            
            # Save
            os.makedirs(LABELS_DIR, exist_ok=True)
            out_path = os.path.join(LABELS_DIR, f"{coin_name}_labeled.csv")
            df_labeled.to_csv(out_path, index=False)
            
            log.info(f"  Saved → {out_path}  ({len(df_labeled):,} rows)")
            results[coin_name] = df_labeled
            
        except Exception as e:
            log.error(f"Failed to label {coin_name}: {e}")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    label_all()
