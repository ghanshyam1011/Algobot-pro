"""
tests/test_indicators.py
==========================
Unit tests for src/features/indicators.py

Tests that every technical indicator:
  - Produces output of the correct shape
  - Contains no NaN after the warmup period
  - Produces values within expected ranges
  - Handles edge cases (tiny datasets, zero volume)

HOW TO RUN:
    pytest tests/test_indicators.py -v
    pytest tests/test_indicators.py -v --tb=short

DEPENDENCIES:
    pip install pytest pandas numpy ta
"""

import pytest
import numpy as np
import pandas as pd


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_ohlcv():
    """
    Generate 200 rows of synthetic OHLCV data.
    Uses realistic BTC-like price behaviour.
    """
    np.random.seed(42)
    n      = 200
    dates  = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    close  = 60000 + np.cumsum(np.random.randn(n) * 200)
    close  = np.maximum(close, 1000)   # Never go below 0
    spread = np.abs(np.random.randn(n) * 100) + 50

    df = pd.DataFrame({
        "datetime": dates,
        "open":     close - np.random.uniform(0, 100, n),
        "high":     close + spread,
        "low":      close - spread,
        "close":    close,
        "volume":   np.random.uniform(1e6, 5e6, n),
    })

    # Fix OHLC violations
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"]  = df[["low",  "open", "close"]].min(axis=1)
    return df


@pytest.fixture
def tiny_ohlcv():
    """Very small dataset — only 30 rows. Tests edge cases."""
    np.random.seed(0)
    n     = 30
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    close = 1000 + np.cumsum(np.random.randn(n) * 10)
    return pd.DataFrame({
        "datetime": dates,
        "open":  close * 0.999,
        "high":  close * 1.002,
        "low":   close * 0.998,
        "close": close,
        "volume": np.ones(n) * 1e5,
    })


# ── Tests: Individual indicators ──────────────────────────────────────────────

class TestRSI:
    def test_rsi_column_created(self, sample_ohlcv):
        from src.features.indicators import add_rsi
        df = add_rsi(sample_ohlcv.copy())
        assert "rsi" in df.columns

    def test_rsi_range(self, sample_ohlcv):
        """RSI must always be between 0 and 100."""
        from src.features.indicators import add_rsi
        df   = add_rsi(sample_ohlcv.copy()).dropna(subset=["rsi"])
        rsi  = df["rsi"]
        assert (rsi >= 0).all(), "RSI below 0 found"
        assert (rsi <= 100).all(), "RSI above 100 found"

    def test_rsi_no_nan_after_warmup(self, sample_ohlcv):
        from src.features.indicators import add_rsi
        df  = add_rsi(sample_ohlcv.copy())
        df  = df.iloc[15:]   # Skip first 15 warmup rows
        assert df["rsi"].isna().sum() == 0

    def test_rsi_custom_window(self, sample_ohlcv):
        from src.features.indicators import add_rsi
        df = add_rsi(sample_ohlcv.copy(), window=7)
        assert "rsi" in df.columns
        df_valid = df.dropna(subset=["rsi"])
        assert len(df_valid) > 0


class TestMACD:
    def test_macd_columns_created(self, sample_ohlcv):
        from src.features.indicators import add_macd
        df = add_macd(sample_ohlcv.copy())
        for col in ["macd_line", "macd_signal", "macd_histogram"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_macd_histogram_is_difference(self, sample_ohlcv):
        """Histogram should equal macd_line minus macd_signal."""
        from src.features.indicators import add_macd
        df     = add_macd(sample_ohlcv.copy()).dropna()
        diff   = df["macd_line"] - df["macd_signal"]
        np.testing.assert_array_almost_equal(
            df["macd_histogram"].values, diff.values, decimal=4
        )

    def test_macd_no_nan_after_warmup(self, sample_ohlcv):
        from src.features.indicators import add_macd
        df = add_macd(sample_ohlcv.copy()).iloc[35:]
        for col in ["macd_line", "macd_signal", "macd_histogram"]:
            assert df[col].isna().sum() == 0


class TestBollingerBands:
    def test_bb_columns_created(self, sample_ohlcv):
        from src.features.indicators import add_bollinger_bands
        df = add_bollinger_bands(sample_ohlcv.copy())
        for col in ["bb_upper", "bb_lower", "bb_width", "bb_pct"]:
            assert col in df.columns

    def test_upper_above_lower(self, sample_ohlcv):
        """Upper band must always be >= lower band."""
        from src.features.indicators import add_bollinger_bands
        df = add_bollinger_bands(sample_ohlcv.copy()).dropna()
        assert (df["bb_upper"] >= df["bb_lower"]).all()

    def test_bb_width_non_negative(self, sample_ohlcv):
        from src.features.indicators import add_bollinger_bands
        df = add_bollinger_bands(sample_ohlcv.copy()).dropna()
        assert (df["bb_width"] >= 0).all()


class TestEMA:
    def test_ema_columns_created(self, sample_ohlcv):
        from src.features.indicators import add_ema
        df = add_ema(sample_ohlcv.copy())
        for col in ["ema_9", "ema_21", "ema_50", "ema_cross"]:
            assert col in df.columns

    def test_ema_cross_values(self, sample_ohlcv):
        """ema_cross must be either +1 or -1."""
        from src.features.indicators import add_ema
        df      = add_ema(sample_ohlcv.copy()).dropna()
        crosses = df["ema_cross"].unique()
        for v in crosses:
            assert v in [1, -1], f"Unexpected ema_cross value: {v}"

    def test_ema_50_lags_ema_9(self, sample_ohlcv):
        """EMA-50 reacts more slowly than EMA-9 (smoother)."""
        from src.features.indicators import add_ema
        df       = add_ema(sample_ohlcv.copy()).dropna()
        std_ema9 = df["ema_9"].std()
        std_ema50 = df["ema_50"].std()
        assert std_ema9 > std_ema50, "EMA-9 should be more volatile than EMA-50"


class TestATR:
    def test_atr_column_created(self, sample_ohlcv):
        from src.features.indicators import add_atr
        df = add_atr(sample_ohlcv.copy())
        assert "atr" in df.columns

    def test_atr_non_negative(self, sample_ohlcv):
        from src.features.indicators import add_atr
        df = add_atr(sample_ohlcv.copy()).dropna()
        assert (df["atr"] >= 0).all()


class TestOBV:
    def test_obv_columns_created(self, sample_ohlcv):
        from src.features.indicators import add_obv
        df = add_obv(sample_ohlcv.copy())
        assert "obv" in df.columns
        assert "obv_norm" in df.columns

    def test_obv_is_cumulative(self, sample_ohlcv):
        """OBV should change with every candle."""
        from src.features.indicators import add_obv
        df = add_obv(sample_ohlcv.copy()).dropna()
        assert df["obv"].nunique() > 10


# ── Tests: Full indicator pipeline ────────────────────────────────────────────

class TestCalculateAllIndicators:
    def test_all_columns_present(self, sample_ohlcv):
        from src.features.indicators import calculate_all_indicators, FEATURE_COLUMNS
        df = calculate_all_indicators(sample_ohlcv.copy())
        for col in FEATURE_COLUMNS:
            assert col in df.columns, f"Missing indicator column: {col}"

    def test_no_nan_after_calculation(self, sample_ohlcv):
        from src.features.indicators import calculate_all_indicators, FEATURE_COLUMNS
        df = calculate_all_indicators(sample_ohlcv.copy())
        nan_counts = df[FEATURE_COLUMNS].isna().sum()
        assert nan_counts.sum() == 0, f"NaN values found: {nan_counts[nan_counts>0].to_dict()}"

    def test_no_infinite_values(self, sample_ohlcv):
        from src.features.indicators import calculate_all_indicators, FEATURE_COLUMNS
        df  = calculate_all_indicators(sample_ohlcv.copy())
        inf = np.isinf(df[FEATURE_COLUMNS].values).any()
        assert not inf, "Infinite values found in indicators"

    def test_output_has_fewer_rows_than_input(self, sample_ohlcv):
        """Warmup rows should be dropped."""
        from src.features.indicators import calculate_all_indicators
        df_out = calculate_all_indicators(sample_ohlcv.copy())
        assert len(df_out) < len(sample_ohlcv)

    def test_original_df_not_modified(self, sample_ohlcv):
        """Input DataFrame must not be modified in place."""
        from src.features.indicators import calculate_all_indicators
        original_len = len(sample_ohlcv)
        original_cols = set(sample_ohlcv.columns)
        calculate_all_indicators(sample_ohlcv)
        assert len(sample_ohlcv) == original_len
        assert set(sample_ohlcv.columns) == original_cols

    def test_tiny_dataset_handled(self, tiny_ohlcv):
        """Should either succeed or raise a clear error — not crash silently."""
        from src.features.indicators import calculate_all_indicators
        try:
            df = calculate_all_indicators(tiny_ohlcv.copy())
            # If it succeeds, it should return a valid DataFrame
            assert isinstance(df, pd.DataFrame)
        except Exception as e:
            # Any exception is acceptable — but it must be explicit, not silent
            assert str(e) != ""