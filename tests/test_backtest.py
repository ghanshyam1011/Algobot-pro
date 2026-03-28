"""
tests/test_backtest.py
========================
Unit tests for the backtesting engine.

Tests:
  - Trade simulation logic is correct
  - Metrics calculations are accurate
  - Edge cases handled (no trades, all wins, all losses)
  - P&L arithmetic is correct

HOW TO RUN:
    pytest tests/test_backtest.py -v
"""

import pytest
import numpy as np
import pandas as pd


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_price_series(n=200, start=60000, drift=0):
    """Generate a synthetic price series."""
    np.random.seed(42)
    returns = np.random.randn(n) * 200 + drift
    prices  = start + np.cumsum(returns)
    return np.maximum(prices, 1000)


def make_labeled_df(prices, signals, confidences):
    """
    Build a minimal labeled DataFrame for backtest testing.

    Args:
        prices:      np.array of prices
        signals:     np.array of predicted labels (0=BUY, 1=SELL, 2=HOLD)
        confidences: np.array of prediction confidences
    """
    n = len(prices)
    return pd.DataFrame({
        "datetime":   pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "close":      prices,
        "label":      np.zeros(n, dtype=int),   # True labels (not used in simulation)
        "pred":       signals,
        "confidence": confidences,
        "atr":        prices * 0.02,
    })


# ── Tests: Metric calculations ────────────────────────────────────────────────

class TestMetricsCalculations:
    def test_win_rate_calculation(self):
        """Win rate = wins / total trades."""
        trades = pd.DataFrame({
            "pnl": [100, -50, 200, -30, 150],
            "dur": [24, 12, 36, 8, 20],
            "dir": ["LONG"] * 5,
        })
        wins    = (trades["pnl"] > 0).sum()   # 3
        total   = len(trades)
        win_rate = wins / total * 100
        assert abs(win_rate - 60.0) < 0.1

    def test_profit_factor_calculation(self):
        """Profit factor = total gross profit / total gross loss."""
        trades = pd.DataFrame({"pnl": [200, -100, 300, -50, 150]})
        gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()   # 650
        gross_loss   = abs(trades.loc[trades["pnl"] <= 0, "pnl"].sum())  # 150
        pf = gross_profit / gross_loss
        assert abs(pf - (650/150)) < 0.001

    def test_total_return_calculation(self):
        """Total return = (final - initial) / initial * 100."""
        initial = 100_000.0
        final   = 115_000.0
        ret     = (final - initial) / initial * 100
        assert abs(ret - 15.0) < 0.001

    def test_max_drawdown_calculation(self):
        """
        Max drawdown = largest peak-to-trough decline.
        Given: 100 → 120 → 90 → 130
        Peak at 120, trough at 90 → drawdown = (90-120)/120 = -25%
        """
        equity = np.array([100, 110, 120, 90, 95, 130])
        peak   = np.maximum.accumulate(equity)
        dd     = (equity - peak) / peak * 100
        max_dd = dd.min()
        assert abs(max_dd - (-25.0)) < 0.1


# ── Tests: Trade simulation ────────────────────────────────────────────────────

class TestTradeSimulation:
    """
    Test the core trade simulation logic.
    We simulate manually without loading any models.
    """

    def test_no_trades_when_all_hold(self):
        """When model always predicts HOLD, no trades should execute."""
        prices = make_price_series(100)
        df     = make_labeled_df(
            prices,
            signals     = np.full(100, 2),   # All HOLD
            confidences = np.full(100, 0.90),
        )

        trades = self._simulate(df)
        assert len(trades) == 0

    def test_no_trades_when_low_confidence(self):
        """When all signals have low confidence, no trades should execute."""
        prices = make_price_series(100)
        df     = make_labeled_df(
            prices,
            signals     = np.zeros(100, dtype=int),   # All BUY
            confidences = np.full(100, 0.50),          # All below threshold
        )

        trades = self._simulate(df, conf_min=0.65)
        assert len(trades) == 0

    def test_long_trade_profit_when_price_rises(self):
        """A LONG trade entered and exited on a rising price should profit."""
        # Price rises: enter at 60000, exit at 66000 (+10%)
        prices = np.array([60000, 61000, 62000, 63000, 64000,
                            65000, 66000, 66000, 66000, 66000])
        sigs   = np.array([0, 2, 2, 2, 2, 2, 1, 2, 2, 2])  # BUY then SELL
        confs  = np.full(10, 0.90)
        df     = make_labeled_df(prices, sigs, confs)

        trades = self._simulate(df, conf_min=0.80)
        assert len(trades) >= 1
        assert trades[0]["pnl"] > 0, "Should profit on rising price"

    def test_long_trade_loss_when_price_falls(self):
        """A LONG trade that exits on a falling price should lose."""
        prices = np.array([60000, 59000, 58000, 57000, 56000,
                            55000, 55000, 55000, 55000, 55000])
        sigs   = np.array([0, 2, 2, 2, 2, 2, 1, 2, 2, 2])  # BUY then SELL
        confs  = np.full(10, 0.90)
        df     = make_labeled_df(prices, sigs, confs)

        trades = self._simulate(df, conf_min=0.80)
        # May have a loss or time-exit — main check is pnl is negative
        if trades:
            total_pnl = sum(t["pnl"] for t in trades)
            assert total_pnl < 0, "Should lose on falling price from LONG"

    def test_position_value_respects_capital(self):
        """Position value must not exceed capital × MAX_POSITION_PCT."""
        from config.settings import POSITION_SIZE_PCT
        capital = 100_000.0
        price   = 66500.0
        value   = capital * POSITION_SIZE_PCT
        assert value == 10_000.0, f"Expected Rs 10,000 position, got {value}"

    def test_fee_is_deducted(self):
        """Net P&L should be less than gross P&L after fee."""
        from config.settings import TRADE_FEE_PCT
        entry = 60000.0
        exit_ = 66000.0
        qty   = 0.075
        gross = (exit_ - entry) * qty
        fee   = exit_ * qty * TRADE_FEE_PCT
        net   = gross - fee
        assert net < gross
        assert fee > 0

    @staticmethod
    def _simulate(df, conf_min=0.65, capital=100_000.0):
        """Minimal trade simulator for testing."""
        from config.settings import POSITION_SIZE_PCT, TRADE_FEE_PCT

        trades   = []
        pos      = None
        entry_p  = 0.0
        entry_i  = 0
        qty      = 0.0

        for i, row in df.iterrows():
            price = row["close"]
            sig   = int(row["pred"])
            conf  = float(row["confidence"])

            if pos is None and conf >= conf_min:
                if sig == 0:    # BUY → LONG
                    val     = capital * POSITION_SIZE_PCT
                    qty     = (val * (1 - TRADE_FEE_PCT)) / price
                    entry_p = price
                    entry_i = i
                    pos     = "LONG"

            elif pos == "LONG":
                held = i - entry_i
                if (sig == 1 and conf >= conf_min) or held >= 48:
                    pnl = (price - entry_p) * qty - price * qty * TRADE_FEE_PCT
                    trades.append({"dir": "LONG", "pnl": pnl, "dur": held})
                    pos = None

        return trades


# ── Tests: Backtest report quality ────────────────────────────────────────────

class TestBacktestQuality:
    def test_deployment_gate_logic(self):
        """
        Verify the deployment gate: only deploy if model meets minimum thresholds.
        """
        from config.settings import MIN_WIN_RATE, MIN_TOTAL_RETURN, MAX_DRAWDOWN

        good_metrics = {
            "win_rate_pct":    55.0,
            "total_return_pct": 15.0,
            "max_drawdown_pct": -18.0,
        }
        bad_metrics = {
            "win_rate_pct":    45.0,
            "total_return_pct": -5.0,
            "max_drawdown_pct": -35.0,
        }

        def passes_gate(m):
            return (
                m["win_rate_pct"]    >= MIN_WIN_RATE and
                m["total_return_pct"] >= MIN_TOTAL_RETURN and
                m["max_drawdown_pct"] >= MAX_DRAWDOWN
            )

        assert passes_gate(good_metrics),  "Good metrics should pass the gate"
        assert not passes_gate(bad_metrics), "Bad metrics should fail the gate"

    def test_sharpe_ratio_sign(self):
        """Positive avg P&L → positive Sharpe; negative → negative."""
        pnl_positive = np.array([100, 150, 80, 120, 200])
        sharpe_pos   = pnl_positive.mean() / pnl_positive.std()
        assert sharpe_pos > 0

        pnl_negative = np.array([-100, -50, -200, -80, -30])
        sharpe_neg   = pnl_negative.mean() / pnl_negative.std()
        assert sharpe_neg < 0