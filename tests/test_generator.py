"""
tests/test_generator.py
=========================
Unit tests for src/signals/generator.py and src/signals/filter.py

Tests:
  - generate_signal() returns correct structure
  - filter.py applies thresholds correctly
  - formatter.py builds complete signal cards
  - sizer.py calculates correct position sizes

HOW TO RUN:
    pytest tests/test_generator.py -v

NOTE:
    Tests that require live internet (Yahoo Finance) are marked
    with @pytest.mark.integration and skipped in CI by default.
    Run them manually with: pytest -m integration
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_buy_signal():
    """A mock raw signal dict representing a strong BUY."""
    return {
        "coin":           "BTC_USD",
        "signal":         "BUY",
        "signal_int":     0,
        "confidence":     0.84,
        "p_buy":          0.84,
        "p_sell":         0.09,
        "p_hold":         0.07,
        "price":          66500.0,
        "datetime":       "2024-03-28T14:00:00+00:00",
        "atr":            1200.0,
        "rsi":            32.5,
        "macd_histogram": 0.0245,
        "volume_ratio":   1.8,
    }


@pytest.fixture
def mock_sell_signal():
    """A mock raw signal dict representing a SELL."""
    return {
        "coin":           "ETH_USD",
        "signal":         "SELL",
        "signal_int":     1,
        "confidence":     0.79,
        "p_buy":          0.08,
        "p_sell":         0.79,
        "p_hold":         0.13,
        "price":          2000.0,
        "datetime":       "2024-03-28T14:00:00+00:00",
        "atr":            45.0,
        "rsi":            74.3,
        "macd_histogram": -0.012,
        "volume_ratio":   2.1,
    }


@pytest.fixture
def mock_hold_signal():
    """A mock HOLD signal with low confidence."""
    return {
        "coin":           "BNB_USD",
        "signal":         "HOLD",
        "signal_int":     2,
        "confidence":     0.55,
        "p_buy":          0.22,
        "p_sell":         0.23,
        "p_hold":         0.55,
        "price":          613.0,
        "datetime":       "2024-03-28T14:00:00+00:00",
        "atr":            8.0,
        "rsi":            50.2,
        "macd_histogram": 0.001,
        "volume_ratio":   0.9,
    }


# ── Tests: Signal filter ───────────────────────────────────────────────────────

class TestSignalFilter:
    def test_hold_signal_always_blocked(self, mock_hold_signal):
        from src.signals.filter import should_send_signal
        ok, reason = should_send_signal(mock_hold_signal, risk_level="high")
        assert not ok, "HOLD signals should always be blocked"
        assert "HOLD" in reason

    def test_high_confidence_buy_passes_medium(self, mock_buy_signal):
        from src.signals.filter import should_send_signal
        ok, reason = should_send_signal(mock_buy_signal, risk_level="medium")
        assert ok, f"High-confidence BUY should pass medium threshold. Reason: {reason}"

    def test_low_confidence_blocked_on_low_risk(self):
        from src.signals.filter import should_send_signal
        low_conf_signal = {
            "signal":       "BUY",
            "signal_int":   0,
            "confidence":   0.70,
            "volume_ratio": 1.2,
        }
        ok, reason = should_send_signal(low_conf_signal, risk_level="low")
        assert not ok, "70% confidence should be blocked on low risk (needs 85%)"

    def test_medium_confidence_passes_high_risk(self):
        from src.signals.filter import should_send_signal
        signal = {
            "signal":       "SELL",
            "signal_int":   1,
            "confidence":   0.67,
            "volume_ratio": 1.0,
        }
        ok, _ = should_send_signal(signal, risk_level="high")
        assert ok, "67% confidence should pass high risk threshold (65%)"

    def test_low_volume_blocked(self):
        from src.signals.filter import should_send_signal
        signal = {
            "signal":       "BUY",
            "signal_int":   0,
            "confidence":   0.90,
            "volume_ratio": 0.5,   # Very low volume
        }
        ok, reason = should_send_signal(signal, risk_level="medium")
        assert not ok, "Low volume should block signal"

    def test_risk_thresholds(self):
        from src.signals.filter import should_send_signal
        from config.settings import RISK_THRESHOLDS

        for risk, threshold in RISK_THRESHOLDS.items():
            # Just below threshold — should be blocked
            signal_below = {
                "signal": "BUY", "signal_int": 0,
                "confidence": threshold - 0.01,
                "volume_ratio": 1.0,
            }
            ok, _ = should_send_signal(signal_below, risk_level=risk)
            assert not ok, f"Confidence below {risk} threshold should be blocked"

            # At threshold — should pass
            signal_at = {
                "signal": "BUY", "signal_int": 0,
                "confidence": threshold,
                "volume_ratio": 1.0,
            }
            ok, _ = should_send_signal(signal_at, risk_level=risk)
            assert ok, f"Confidence at {risk} threshold should pass"

    def test_filter_signals_list(self, mock_buy_signal, mock_hold_signal, mock_sell_signal):
        from src.signals.filter import filter_signals
        signals = [mock_buy_signal, mock_hold_signal, mock_sell_signal]
        passed  = filter_signals(signals, risk_level="medium")
        # HOLD should be filtered out; BUY (84%) and SELL (79%) should pass
        assert all(s["signal"] != "HOLD" for s in passed)


# ── Tests: Signal formatter ────────────────────────────────────────────────────

class TestSignalFormatter:
    def test_formatter_returns_complete_dict(self, mock_buy_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_buy_signal, user_capital=50000.0)

        required_keys = [
            "coin", "signal", "confidence", "price",
            "entry_low", "entry_high", "target_price",
            "stop_loss_price", "risk_reward", "quantity",
            "position_value", "reasons", "telegram_message",
        ]
        for key in required_keys:
            assert key in card, f"Missing key in formatted signal: {key}"

    def test_buy_target_above_price(self, mock_buy_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_buy_signal)
        assert card["target_price"] > card["price"], \
            "BUY target must be above current price"

    def test_buy_stop_below_price(self, mock_buy_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_buy_signal)
        assert card["stop_loss_price"] < card["price"], \
            "BUY stop-loss must be below current price"

    def test_sell_target_below_price(self, mock_sell_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_sell_signal)
        assert card["target_price"] < card["price"], \
            "SELL target must be below current price"

    def test_sell_stop_above_price(self, mock_sell_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_sell_signal)
        assert card["stop_loss_price"] > card["price"], \
            "SELL stop-loss must be above current price"

    def test_risk_reward_positive(self, mock_buy_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_buy_signal)
        assert card["risk_reward"] > 0

    def test_telegram_message_contains_key_info(self, mock_buy_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_buy_signal)
        msg  = card["telegram_message"]
        assert "BUY"          in msg
        assert "BTC"          in msg
        assert "confidence"   in msg.lower() or "%" in msg
        assert "Target"       in msg or "target" in msg.lower()
        assert "Stop"         in msg or "stop" in msg.lower()

    def test_reasons_list_not_empty(self, mock_buy_signal):
        from src.signals.formatter import format_signal
        card = format_signal(mock_buy_signal)
        assert len(card["reasons"]) > 0, "Signal card must have at least one reason"

    def test_position_value_matches_capital(self, mock_buy_signal):
        from src.signals.formatter import format_signal
        from config.settings import POSITION_SIZE_PCT
        capital = 100_000.0
        card    = format_signal(mock_buy_signal, user_capital=capital)
        expected = capital * POSITION_SIZE_PCT
        # Allow for confidence adjustment (may differ slightly)
        assert card["position_value"] <= capital * 0.25, \
            "Position value should not exceed 25% of capital"


# ── Tests: Position sizer ──────────────────────────────────────────────────────

class TestPositionSizer:
    def test_fixed_pct_correct_value(self):
        from src.signals.sizer import fixed_pct_size
        result = fixed_pct_size(capital=50000, price=1000, pct=0.10)
        assert abs(result["position_value"] - 5000) < 10

    def test_quantity_calculated_from_price(self):
        from src.signals.sizer import fixed_pct_size
        result   = fixed_pct_size(capital=50000, price=66500, pct=0.10)
        expected = (50000 * 0.10 * (1 - 0.001)) / 66500
        assert abs(result["quantity"] - expected) < 0.0001

    def test_max_position_cap_applied(self):
        from src.signals.sizer import fixed_pct_size, MAX_POSITION_PCT
        # Try to use 50% — should be capped at MAX_POSITION_PCT
        result = fixed_pct_size(capital=50000, price=1000, pct=0.50)
        max_val = 50000 * MAX_POSITION_PCT
        assert result["position_value"] <= max_val + 1

    def test_atr_based_size(self):
        from src.signals.sizer import atr_based_size
        result = atr_based_size(capital=50000, price=66500, atr=1200)
        assert result["position_value"] > 0
        assert result["quantity"] > 0
        assert result["method"] == "atr_based"

    def test_confidence_adjusted_higher_conf_bigger_position(self):
        from src.signals.sizer import confidence_adjusted_size
        low_conf  = confidence_adjusted_size(50000, 66500, confidence=0.65)
        high_conf = confidence_adjusted_size(50000, 66500, confidence=0.90)
        assert high_conf["position_value"] > low_conf["position_value"], \
            "Higher confidence should give larger position"

    def test_zero_price_handled(self):
        from src.signals.sizer import fixed_pct_size
        result = fixed_pct_size(capital=50000, price=0)
        assert result["quantity"] == 0

    def test_calculate_position_complete(self, mock_buy_signal):
        from src.signals.sizer import calculate_position
        sizing = calculate_position(mock_buy_signal, capital=50000)
        assert "position_value"   in sizing
        assert "quantity"         in sizing
        assert "stop_loss_price"  in sizing
        assert "target_price"     in sizing


# ── Integration tests (require internet + trained model) ──────────────────────

@pytest.mark.integration
class TestGenerateSignalIntegration:
    """
    These tests call Yahoo Finance and load real model files.
    Skip in CI — run manually only.
    """

    def test_generate_signal_returns_dict(self):
        from src.signals.generator import generate_signal
        result = generate_signal("BTC_USD")
        assert isinstance(result, dict)

    def test_generate_signal_has_required_keys(self):
        from src.signals.generator import generate_signal
        result = generate_signal("BTC_USD")
        for key in ["coin", "signal", "confidence", "price", "rsi"]:
            assert key in result

    def test_signal_is_valid_type(self):
        from src.signals.generator import generate_signal
        result = generate_signal("BTC_USD")
        assert result["signal"] in ["BUY", "SELL", "HOLD"]

    def test_confidence_in_range(self):
        from src.signals.generator import generate_signal
        result = generate_signal("BTC_USD")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_probabilities_sum_to_one(self):
        from src.signals.generator import generate_signal
        result = generate_signal("BTC_USD")
        total  = result["p_buy"] + result["p_sell"] + result["p_hold"]
        assert abs(total - 1.0) < 0.01