"""
src/features/validator.py
===========================
PURPOSE:
    Validate feature DataFrames before they are passed to the model.
    Acts as a quality gate — if the data is bad, the signal is blocked.

WHY THIS EXISTS:
    The model was trained on clean, complete data.
    If even one feature column is NaN or out of range, the model
    will produce garbage predictions without any error.

    This validator catches:
    - Missing feature columns
    - NaN values in any feature
    - Infinite values (division by zero in some indicators)
    - Values wildly outside expected ranges (data corruption)
    - Stale data (last candle is too old)

USED BY:
    src/signals/generator.py  before running model.predict_proba()

DEPENDENCIES:
    pip install pandas numpy
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from config.settings import FEATURE_COLUMNS

log = logging.getLogger(__name__)

# ── Expected value ranges for sanity checking ──────────────────────────────────
# If any value falls outside these ranges, it is flagged as suspicious.
# Ranges are intentionally wide to avoid false positives.
FEATURE_RANGES = {
    "rsi":              (0.0,    100.0),
    "macd_line":        (-1e6,   1e6),
    "macd_signal":      (-1e6,   1e6),
    "macd_histogram":   (-1e6,   1e6),
    "bb_pct":           (-1.0,   2.0),    # Can go outside 0-1 in extreme moves
    "bb_width":         (0.0,    100.0),
    "ema_cross":        (-1.0,   1.0),
    "stoch_k":          (0.0,    100.0),
    "stoch_d":          (0.0,    100.0),
    "obv_norm":         (-10.0,  10.0),
    "volume_ratio":     (0.0,    50.0),
    "return_1h":        (-50.0,  50.0),   # % return
    "return_4h":        (-80.0,  80.0),
    "return_24h":       (-99.0,  500.0),
    "hour_of_day":      (0.0,    23.0),
    "day_of_week":      (0.0,    6.0),
    "is_weekend":       (0.0,    1.0),
    "session_asia":     (0.0,    1.0),
    "session_london":   (0.0,    1.0),
    "session_us":       (0.0,    1.0),
    "close_vs_ema50":   (-50.0,  50.0),
    "candle_body":      (0.0,    20.0),
    "high_low_range":   (0.0,    30.0),
    "candle_direction": (-1.0,   1.0),
}

# How old the latest candle can be before we consider data stale (hours)
MAX_DATA_AGE_HOURS = 3.0


class ValidationError(Exception):
    """Raised when feature validation fails and signal should be blocked."""
    pass


class ValidationWarning(Exception):
    """Raised for non-critical issues that don't block signal generation."""
    pass


def validate_features(
    df: pd.DataFrame,
    coin_name: str = "UNKNOWN",
    strict: bool = False,
) -> dict:
    """
    Validate a feature DataFrame before passing it to the model.

    Checks performed:
        1. All required feature columns are present
        2. No NaN values in feature columns
        3. No infinite values
        4. Latest candle is not stale (< MAX_DATA_AGE_HOURS old)
        5. Values within expected ranges (sanity check)

    Args:
        df:        Feature DataFrame (output of engineer_features())
        coin_name: Used for logging only
        strict:    If True, range violations raise ValidationError.
                   If False (default), they only log warnings.

    Returns:
        dict: Validation report with keys:
              'passed': bool
              'errors': list of error strings
              'warnings': list of warning strings
              'feature_count': int
              'row_count': int

    Raises:
        ValidationError: If critical validation fails
                         (missing columns, NaN values, stale data)

    Example:
        >>> from src.features.validator import validate_features
        >>> report = validate_features(df_features, coin_name='BTC_USD')
        >>> if report['passed']:
        ...     signal = model.predict(df)
    """
    errors   = []
    warnings = []

    # ── Check 1: DataFrame is not empty ──────────────────────────────────────
    if df is None or df.empty:
        raise ValidationError(
            f"{coin_name}: Feature DataFrame is empty. "
            f"Check that fetch_live.py and engineer.py ran successfully."
        )

    # ── Check 2: All required feature columns are present ────────────────────
    missing_cols = [col for col in FEATURE_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValidationError(
            f"{coin_name}: Missing {len(missing_cols)} feature columns: "
            f"{missing_cols}\n"
            f"This usually means engineer.py was not run, or the feature "
            f"list in config/settings.py does not match what engineer.py produces."
        )

    log.debug(f"  {coin_name}: All {len(FEATURE_COLUMNS)} feature columns present.")

    # ── Check 3: No NaN values in feature columns ─────────────────────────────
    feature_df = df[FEATURE_COLUMNS]
    nan_counts  = feature_df.isna().sum()
    nan_cols    = nan_counts[nan_counts > 0]

    if len(nan_cols) > 0:
        nan_details = ", ".join(
            [f"{col}={count}" for col, count in nan_cols.items()]
        )
        raise ValidationError(
            f"{coin_name}: NaN values found in {len(nan_cols)} feature columns: "
            f"{nan_details}\n"
            f"This usually means insufficient historical data for warmup. "
            f"Fetch more candles (current LOOKBACK_CANDLES in settings.py)."
        )

    log.debug(f"  {coin_name}: No NaN values found.")

    # ── Check 4: No infinite values ───────────────────────────────────────────
    inf_mask = np.isinf(feature_df.values)
    if inf_mask.any():
        inf_cols = feature_df.columns[inf_mask.any(axis=0)].tolist()
        raise ValidationError(
            f"{coin_name}: Infinite values found in columns: {inf_cols}\n"
            f"This usually means division by zero in indicator calculation "
            f"(e.g. volume = 0, or price = 0)."
        )

    log.debug(f"  {coin_name}: No infinite values found.")

    # ── Check 5: Data freshness ───────────────────────────────────────────────
    if "datetime" in df.columns:
        latest_dt = pd.to_datetime(df["datetime"].iloc[-1], utc=True)
        now       = datetime.now(timezone.utc)
        age_h     = (now - latest_dt).total_seconds() / 3600

        if age_h > MAX_DATA_AGE_HOURS:
            raise ValidationError(
                f"{coin_name}: Latest candle is {age_h:.1f}h old "
                f"(max allowed: {MAX_DATA_AGE_HOURS}h).\n"
                f"Yahoo Finance may be experiencing issues. "
                f"The signal will be skipped to avoid trading on stale data."
            )

        if age_h > 1.5:
            warnings.append(
                f"Latest candle is {age_h:.1f}h old — "
                f"data may be slightly delayed."
            )

        log.debug(f"  {coin_name}: Data freshness OK ({age_h:.2f}h old).")

    # ── Check 6: Value range sanity check (last row only — the live row) ──────
    last_row = feature_df.iloc[-1]
    range_violations = []

    for col, (low, high) in FEATURE_RANGES.items():
        if col not in last_row.index:
            continue
        val = last_row[col]
        if not (low <= val <= high):
            range_violations.append(
                f"{col}={val:.4f} (expected {low} to {high})"
            )

    if range_violations:
        msg = (
            f"{coin_name}: {len(range_violations)} feature values outside "
            f"expected ranges: {range_violations}"
        )
        if strict:
            raise ValidationError(msg)
        else:
            warnings.append(msg)
            log.warning(f"  {msg}")

    # ── Build report ──────────────────────────────────────────────────────────
    passed = len(errors) == 0

    report = {
        "passed":        passed,
        "coin":          coin_name,
        "errors":        errors,
        "warnings":      warnings,
        "feature_count": len(FEATURE_COLUMNS),
        "row_count":     len(df),
        "validated_at":  datetime.now(timezone.utc).isoformat(),
    }

    if warnings:
        for w in warnings:
            log.warning(f"  Validation warning [{coin_name}]: {w}")

    if passed:
        log.info(
            f"  Validation passed: {coin_name} | "
            f"{len(FEATURE_COLUMNS)} features | "
            f"{len(df)} rows | "
            f"{len(warnings)} warning(s)"
        )

    return report


def validate_single_row(row: pd.Series, coin_name: str = "UNKNOWN") -> bool:
    """
    Validate a single feature row (the latest live row) before prediction.
    Lighter-weight version of validate_features() for the live engine.

    Args:
        row:       pd.Series with feature values (one row from feature DataFrame)
        coin_name: Used for logging

    Returns:
        bool: True if row is valid, False if it should be skipped

    Example:
        >>> latest_row = df_features.iloc[-1]
        >>> if validate_single_row(latest_row, 'BTC_USD'):
        ...     signal = model.predict(latest_row)
    """
    # Check all features present
    missing = [col for col in FEATURE_COLUMNS if col not in row.index]
    if missing:
        log.error(f"  {coin_name}: Missing features in row: {missing}")
        return False

    # Check no NaN or inf
    values = row[FEATURE_COLUMNS].values.astype(float)
    if np.isnan(values).any():
        nan_features = [FEATURE_COLUMNS[i] for i, v in enumerate(values) if np.isnan(v)]
        log.error(f"  {coin_name}: NaN in row features: {nan_features}")
        return False

    if np.isinf(values).any():
        inf_features = [FEATURE_COLUMNS[i] for i, v in enumerate(values) if np.isinf(v)]
        log.error(f"  {coin_name}: Inf in row features: {inf_features}")
        return False

    return True


def check_label_distribution(df: pd.DataFrame, coin_name: str) -> dict:
    """
    Check that labeled data has a reasonable class distribution.
    Warns if any class is severely underrepresented (< 10%).

    Args:
        df:        Labeled DataFrame with 'label' column
        coin_name: Used for logging

    Returns:
        dict: { 'buy_pct': float, 'sell_pct': float, 'hold_pct': float,
                'is_balanced': bool }
    """
    if "label" not in df.columns:
        log.warning(f"  {coin_name}: No 'label' column found")
        return {}

    total  = len(df)
    counts = df["label"].value_counts()

    buy_pct  = counts.get(0, 0) / total * 100
    sell_pct = counts.get(1, 0) / total * 100
    hold_pct = counts.get(2, 0) / total * 100

    is_balanced = all(pct >= 10.0 for pct in [buy_pct, sell_pct, hold_pct])

    if not is_balanced:
        log.warning(
            f"  {coin_name}: Imbalanced labels — "
            f"BUY={buy_pct:.1f}% SELL={sell_pct:.1f}% HOLD={hold_pct:.1f}%\n"
            f"  Consider adjusting THRESHOLD_PCT in config/settings.py"
        )

    return {
        "buy_pct":     round(buy_pct, 2),
        "sell_pct":    round(sell_pct, 2),
        "hold_pct":    round(hold_pct, 2),
        "is_balanced": is_balanced,
        "total_rows":  total,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )

    # Quick test: validate features for BTC
    try:
        from src.data_pipeline.data_store import load_features
        df = load_features("BTC_USD")
        report = validate_features(df, coin_name="BTC_USD")

        print("\n── Validation Report ──────────────────────────────")
        print(f"  Passed         : {report['passed']}")
        print(f"  Feature count  : {report['feature_count']}")
        print(f"  Row count      : {report['row_count']}")
        print(f"  Warnings       : {len(report['warnings'])}")
        for w in report["warnings"]:
            print(f"    - {w}")

    except FileNotFoundError as e:
        print(f"No features found: {e}")
        print("Run pipeline.py first to generate features.")