"""
tests/test_labeler.py
=======================
Unit tests for src/features/labeler.py

Tests label creation logic:
  - Correct BUY / SELL / HOLD assignment
  - No future data leakage
  - Correct row count after dropping last N rows
  - Label distribution is reasonable

HOW TO RUN:
    pytest tests/test_labeler.py -v
"""

import pytest
import numpy as np
import pandas as pd

from src.features.labeler import (
    create_labels,
    LABEL_BUY,
    LABEL_SELL,
    LABEL_HOLD,
    FORWARD_HOURS,
    THRESHOLD_PCT,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def flat_df():
    """DataFrame where price never changes — should produce all HOLD labels."""
    n  = 100
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "close":    np.ones(n) * 50000.0,
        "open":     np.ones(n) * 50000.0,
        "high":     np.ones(n) * 50000.0,
        "low":      np.ones(n) * 50000.0,
        "volume":   np.ones(n) * 1e6,
    })
    return df


@pytest.fixture
def rising_df():
    """
    DataFrame with strongly rising prices.
    Should produce mostly BUY labels.
    """
    n     = 150
    close = 50000 + np.arange(n) * 200   # Rises 200 per candle
    df    = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "close":    close,
        "open":     close * 0.999,
        "high":     close * 1.002,
        "low":      close * 0.997,
        "volume":   np.ones(n) * 1e6,
    })
    return df


@pytest.fixture
def falling_df():
    """DataFrame with strongly falling prices — should produce mostly SELL labels."""
    n     = 150
    close = 80000 - np.arange(n) * 200
    close = np.maximum(close, 1000)
    df    = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "close":    close,
        "open":     close * 1.001,
        "high":     close * 1.003,
        "low":      close * 0.997,
        "volume":   np.ones(n) * 1e6,
    })
    return df


@pytest.fixture
def mixed_df():
    """Realistic mixed DataFrame — prices go up, down, and sideways."""
    np.random.seed(99)
    n     = 300
    close = 60000 + np.cumsum(np.random.randn(n) * 300)
    close = np.maximum(close, 1000)
    df    = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "close":    close,
        "open":     close * (1 + np.random.uniform(-0.001, 0.001, n)),
        "high":     close * (1 + np.random.uniform(0.001, 0.005, n)),
        "low":      close * (1 - np.random.uniform(0.001, 0.005, n)),
        "volume":   np.random.uniform(1e5, 5e6, n),
    })
    return df


# ── Tests: Label assignment logic ─────────────────────────────────────────────

class TestLabelValues:
    def test_flat_prices_produce_hold(self, flat_df):
        """When price doesn't move, every row should be HOLD."""
        df = create_labels(flat_df, forward_hours=24, threshold_pct=2.0)
        assert (df["label"] == LABEL_HOLD).all(), \
            "Flat prices should produce all HOLD labels"

    def test_rising_prices_produce_buy(self, rising_df):
        """Strongly rising prices should produce mostly BUY labels."""
        df     = create_labels(rising_df, forward_hours=10, threshold_pct=2.0)
        buy_pct = (df["label"] == LABEL_BUY).mean()
        assert buy_pct > 0.7, \
            f"Expected >70% BUY labels for rising prices, got {buy_pct:.1%}"

    def test_falling_prices_produce_sell(self, falling_df):
        """Strongly falling prices should produce mostly SELL labels."""
        df      = create_labels(falling_df, forward_hours=10, threshold_pct=2.0)
        sell_pct = (df["label"] == LABEL_SELL).mean()
        assert sell_pct > 0.7, \
            f"Expected >70% SELL labels for falling prices, got {sell_pct:.1%}"

    def test_label_values_are_valid_integers(self, mixed_df):
        """Labels must only be 0 (BUY), 1 (SELL), or 2 (HOLD)."""
        df     = create_labels(mixed_df)
        unique = set(df["label"].unique())
        valid  = {LABEL_BUY, LABEL_SELL, LABEL_HOLD}
        assert unique.issubset(valid), \
            f"Invalid label values found: {unique - valid}"

    def test_label_dtype_is_int(self, mixed_df):
        """Label column must be integer type."""
        df = create_labels(mixed_df)
        assert df["label"].dtype in [np.int32, np.int64, int], \
            f"Label dtype should be int, got {df['label'].dtype}"


class TestRowCounts:
    def test_last_n_rows_dropped(self, mixed_df):
        """
        The last FORWARD_HOURS rows can't have a label
        (no future data available). They must be dropped.
        """
        df_labeled = create_labels(mixed_df, forward_hours=24)
        expected_max = len(mixed_df) - 24
        assert len(df_labeled) <= expected_max, \
            "Last FORWARD_HOURS rows were not dropped"

    def test_output_shorter_than_input(self, mixed_df):
        df = create_labels(mixed_df)
        assert len(df) < len(mixed_df)

    def test_custom_forward_hours(self, mixed_df):
        df12 = create_labels(mixed_df.copy(), forward_hours=12)
        df48 = create_labels(mixed_df.copy(), forward_hours=48)
        assert len(df12) > len(df48), \
            "Larger forward_hours should produce fewer labeled rows"


class TestFutureReturn:
    def test_future_return_column_exists(self, mixed_df):
        df = create_labels(mixed_df)
        assert "future_return" in df.columns

    def test_future_return_no_nan(self, mixed_df):
        df = create_labels(mixed_df)
        assert df["future_return"].isna().sum() == 0

    def test_future_return_matches_label(self, mixed_df):
        """
        Verify that future_return and label are consistent.
        Where future_return > threshold → label should be BUY.
        """
        df = create_labels(mixed_df, threshold_pct=2.0)
        buy_rows = df[df["label"] == LABEL_BUY]
        assert (buy_rows["future_return"] > 2.0).all(), \
            "BUY rows must all have future_return > threshold"

        sell_rows = df[df["label"] == LABEL_SELL]
        assert (sell_rows["future_return"] < -2.0).all(), \
            "SELL rows must all have future_return < -threshold"

    def test_threshold_pct_affects_distribution(self, mixed_df):
        """
        Higher threshold → fewer BUY/SELL, more HOLD.
        """
        df_tight = create_labels(mixed_df.copy(), threshold_pct=0.5)
        df_wide  = create_labels(mixed_df.copy(), threshold_pct=5.0)

        tight_hold = (df_tight["label"] == LABEL_HOLD).mean()
        wide_hold  = (df_wide["label"] == LABEL_HOLD).mean()

        assert wide_hold > tight_hold, \
            "Higher threshold should produce more HOLD labels"


class TestEdgeCases:
    def test_empty_dataframe_raises(self):
        """Empty input should raise a clear error."""
        with pytest.raises(Exception):
            create_labels(pd.DataFrame())

    def test_missing_close_column_raises(self):
        """DataFrame without 'close' column should raise."""
        df = pd.DataFrame({"price": [100, 200, 300]})
        with pytest.raises((KeyError, Exception)):
            create_labels(df)

    def test_original_df_not_modified(self, mixed_df):
        """Input DataFrame must not be modified in place."""
        original_len  = len(mixed_df)
        original_cols = set(mixed_df.columns)
        create_labels(mixed_df)
        assert len(mixed_df) == original_len
        assert set(mixed_df.columns) == original_cols