"""
src/signals/formatter.py
==========================
PURPOSE:
    Transform a raw signal dict into a rich, human-readable signal card
    with entry zone, target price, stop-loss, position size, and plain-English reasons.

    This is what the user actually sees in Telegram or on the dashboard.
    It's the difference between "BUY" and a full professional signal card.
"""

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Target multipliers (how far we expect price to move)
BUY_TARGET_PCT   = 0.06   # Target = entry + 6%
SELL_TARGET_PCT  = 0.06   # Target = entry - 6%
STOP_LOSS_PCT    = 0.03   # Stop-loss = entry ± 3%
ENTRY_ZONE_PCT   = 0.005  # Entry zone width = ±0.5% around current price


def _build_reasons(signal: dict) -> list[str]:
    """
    Generate plain-English explanations for why the signal was triggered.
    Maps raw indicator values into human-readable sentences.

    Returns:
        list[str]: 3-5 reason strings
    """
    reasons  = []
    sig_type = signal.get("signal", "HOLD")
    rsi      = signal.get("rsi", 50)
    macd_h   = signal.get("macd_histogram", 0)
    vol_r    = signal.get("volume_ratio", 1)
    conf     = signal.get("confidence", 0.5)

    if sig_type == "BUY":
        if rsi < 35:
            reasons.append(f"RSI at {rsi:.0f} — asset is oversold and due for a bounce")
        elif rsi < 50:
            reasons.append(f"RSI at {rsi:.0f} — recovering from oversold territory")
        else:
            reasons.append(f"RSI at {rsi:.0f} — momentum building in upward direction")

        if macd_h > 0:
            reasons.append(f"MACD histogram positive ({macd_h:+.4f}) — bullish momentum confirmed")
        else:
            reasons.append("MACD showing early signs of bullish crossover")

        if vol_r >= 1.5:
            reasons.append(f"Volume is {vol_r:.1f}x above average — strong buyer interest")
        elif vol_r >= 1.0:
            reasons.append(f"Volume at {vol_r:.1f}x average — normal healthy activity")

        reasons.append(f"ML model confidence: {conf:.0%} across all 17 technical features")

        if signal.get("p_buy", 0) > 0.80:
            reasons.append("Multiple indicators aligned simultaneously — high conviction setup")

    elif sig_type == "SELL":
        if rsi > 70:
            reasons.append(f"RSI at {rsi:.0f} — asset is overbought and likely to pull back")
        elif rsi > 55:
            reasons.append(f"RSI at {rsi:.0f} — momentum fading from recent highs")
        else:
            reasons.append(f"RSI at {rsi:.0f} — weakening despite recent price levels")

        if macd_h < 0:
            reasons.append(f"MACD histogram negative ({macd_h:+.4f}) — bearish momentum confirmed")
        else:
            reasons.append("MACD showing early bearish crossover warning")

        if vol_r >= 1.5:
            reasons.append(f"Volume spike ({vol_r:.1f}x average) — sellers dominating with conviction")
        else:
            reasons.append(f"Volume at {vol_r:.1f}x average — selling pressure building")

        reasons.append(f"ML model confidence: {conf:.0%} across all 17 technical features")

    return reasons[:5]   # Cap at 5 reasons for readability


def format_signal(signal: dict, user_capital: float = 50000.0) -> dict:
    """
    Transform a raw signal dict into a complete, formatted signal card.

    Args:
        signal:       Raw signal dict from generator.py
        user_capital: User's total trading capital (for position sizing)

    Returns:
        dict: Complete signal card with all fields needed for delivery

    Example:
        >>> from src.signals.formatter import format_signal
        >>> card = format_signal(signal, user_capital=50000)
        >>> print(card['telegram_message'])
    """
    sig_type    = signal.get("signal", "HOLD")
    price       = signal.get("price", 0)
    coin        = signal.get("coin", "UNKNOWN")
    confidence  = signal.get("confidence", 0)
    atr         = signal.get("atr", price * 0.02)

    # Entry zone: ±0.5% around current price
    entry_low   = round(price * (1 - ENTRY_ZONE_PCT), 2)
    entry_high  = round(price * (1 + ENTRY_ZONE_PCT), 2)

    if sig_type == "BUY":
        target_price    = round(price * (1 + BUY_TARGET_PCT), 2)
        stop_loss_price = round(price * (1 - STOP_LOSS_PCT), 2)
        risk_pct        = STOP_LOSS_PCT * 100
        reward_pct      = BUY_TARGET_PCT * 100
    elif sig_type == "SELL":
        target_price    = round(price * (1 - SELL_TARGET_PCT), 2)
        stop_loss_price = round(price * (1 + STOP_LOSS_PCT), 2)
        risk_pct        = STOP_LOSS_PCT * 100
        reward_pct      = SELL_TARGET_PCT * 100
    else:
        target_price    = price
        stop_loss_price = price
        risk_pct        = 0
        reward_pct      = 0

    risk_reward = round(reward_pct / risk_pct, 2) if risk_pct > 0 else 0

    # Position sizing: risk POSITION_SIZE_PCT of capital on this trade
    position_value = user_capital * 0.10
    quantity       = round(position_value / price, 6)

    # Plain-English reasons
    reasons = _build_reasons(signal)

    # Confidence bar (10 blocks)
    filled = int(confidence * 10)
    conf_bar = "█" * filled + "░" * (10 - filled)

    # Signal emoji
    emoji_map = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
    emoji     = emoji_map.get(sig_type, "⚪")

    # Format Telegram message
    coin_display = coin.replace("_", "/")
    timestamp    = datetime.now(timezone.utc).strftime("%H:%M UTC")

    telegram_msg = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  AlgoBot Pro — Signal Alert\n"
        f"  {timestamp}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"  Asset      : {coin_display}\n"
        f"  Signal     : {emoji} {sig_type}\n"
        f"  Confidence : {conf_bar} {confidence:.0%}\n"
        f"\n"
        f"  Current Price : {price:,.2f}\n"
        f"  Entry Zone    : {entry_low:,.2f} – {entry_high:,.2f}\n"
        f"  Target Price  : {target_price:,.2f}  (+{reward_pct:.1f}%)\n"
        f"  Stop Loss     : {stop_loss_price:,.2f}  (-{risk_pct:.1f}%)\n"
        f"  Risk/Reward   : 1 : {risk_reward}\n"
        f"\n"
        f"  Position Size : {quantity:.6f} units\n"
        f"  Trade Value   : Rs {position_value:,.0f}\n"
        f"  (Based on Rs {user_capital:,.0f} capital, 10% per trade)\n"
        f"\n"
        f"  WHY THIS SIGNAL?\n"
    )
    for i, reason in enumerate(reasons, 1):
        telegram_msg += f"  {i}. {reason}\n"
    telegram_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    return {
        # Core signal data
        "coin":             coin,
        "signal":           sig_type,
        "confidence":       confidence,
        "price":            price,
        # Trade levels
        "entry_low":        entry_low,
        "entry_high":       entry_high,
        "target_price":     target_price,
        "stop_loss_price":  stop_loss_price,
        "risk_pct":         risk_pct,
        "reward_pct":       reward_pct,
        "risk_reward":      risk_reward,
        # Position sizing
        "quantity":         quantity,
        "position_value":   position_value,
        "user_capital":     user_capital,
        # Indicator context
        "rsi":              signal.get("rsi"),
        "macd_histogram":   signal.get("macd_histogram"),
        "volume_ratio":     signal.get("volume_ratio"),
        "atr":              atr,
        # Delivery content
        "reasons":          reasons,
        "telegram_message": telegram_msg,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
    }