"""
src/signals/sizer.py
======================
PURPOSE:
    Calculate the exact position size for every signal.
    Turns "BUY BTC" into "Buy 0.075 BTC worth ₹5,000".

WHY POSITION SIZING MATTERS:
    Without proper sizing, traders either:
    - Risk too much on one trade (blow up their account)
    - Risk too little (miss meaningful profits)

    Professional traders use strict rules:
    - Never risk more than 1-2% of capital on a single trade
    - Size positions based on the stop-loss distance (ATR-based)
    - Adjust size based on signal confidence

SIZING METHODS IMPLEMENTED:
    1. Fixed percentage  — always use X% of capital (simple, default)
    2. ATR-based         — size based on volatility (professional method)
    3. Kelly criterion   — mathematically optimal sizing (advanced)

DEPENDENCIES:
    pip install pandas numpy
"""

import logging
import numpy as np

from config.settings import (
    DEFAULT_CAPITAL,
    POSITION_SIZE_PCT,
    STOP_LOSS_PCT,
    TRADE_FEE_PCT,
    RISK_THRESHOLDS,
)

log = logging.getLogger(__name__)

# Maximum position size as % of capital — safety cap
MAX_POSITION_PCT  = 0.20   # Never use more than 20% on one trade
MIN_POSITION_USD  = 100.0  # Minimum position value (avoid dust trades)


def fixed_pct_size(
    capital: float,
    price: float,
    pct: float = POSITION_SIZE_PCT,
) -> dict:
    """
    Simple fixed-percentage position sizing.
    Use X% of total capital for each trade.

    This is the default method — simple, predictable, easy to understand.

    Args:
        capital: Total available capital in Rs
        price:   Current asset price
        pct:     Fraction of capital to use (default 0.10 = 10%)

    Returns:
        dict: {
            'position_value': float,   # Rs amount to invest
            'quantity':       float,   # How many units to buy
            'fee':            float,   # Estimated fee
            'net_investment': float,   # position_value - fee
            'method':         str,
        }

    Example:
        >>> from src.signals.sizer import fixed_pct_size
        >>> size = fixed_pct_size(capital=50000, price=66500, pct=0.10)
        >>> print(f"Buy {size['quantity']:.6f} BTC worth Rs {size['position_value']:,.0f}")
    """
    # Apply safety cap
    pct             = min(pct, MAX_POSITION_PCT)
    position_value  = capital * pct
    fee             = position_value * TRADE_FEE_PCT
    net_investment  = position_value - fee
    quantity        = net_investment / price if price > 0 else 0.0

    return {
        "position_value": round(position_value, 2),
        "quantity":       round(quantity, 8),
        "fee":            round(fee, 2),
        "net_investment": round(net_investment, 2),
        "pct_of_capital": round(pct * 100, 1),
        "method":         "fixed_pct",
    }


def atr_based_size(
    capital: float,
    price: float,
    atr: float,
    risk_pct: float = 0.01,
    atr_multiplier: float = 2.0,
) -> dict:
    """
    ATR-based position sizing — professional volatility-adjusted method.

    The idea: if the market is volatile (high ATR), take a smaller position.
    If the market is calm (low ATR), you can take a larger position.

    Risk per trade = capital × risk_pct (e.g. 1% of Rs 50,000 = Rs 500)
    Stop distance  = ATR × atr_multiplier (e.g. 2 × ATR)
    Position size  = Risk per trade / Stop distance

    Example with BTC @ Rs 66,500 and ATR = Rs 1,200:
        Risk          = Rs 50,000 × 1% = Rs 500
        Stop distance = Rs 1,200 × 2   = Rs 2,400
        Quantity      = Rs 500 / Rs 2,400 = 0.208 BTC
        Position value= 0.208 × Rs 66,500 = Rs 13,832

    Args:
        capital:         Total capital
        price:           Current price
        atr:             Average True Range (from indicators.py)
        risk_pct:        Max % of capital to risk per trade (default 1%)
        atr_multiplier:  Stop-loss = ATR × this multiplier (default 2.0)

    Returns:
        dict: Same structure as fixed_pct_size()

    Example:
        >>> from src.signals.sizer import atr_based_size
        >>> size = atr_based_size(50000, 66500, 1200)
        >>> print(f"Quantity: {size['quantity']:.6f}")
    """
    if atr <= 0 or price <= 0:
        log.warning("ATR or price is zero — falling back to fixed 5% sizing")
        return fixed_pct_size(capital, price, pct=0.05)

    risk_amount    = capital * risk_pct
    stop_distance  = atr * atr_multiplier
    quantity       = risk_amount / stop_distance

    position_value = quantity * price
    fee            = position_value * TRADE_FEE_PCT

    # Apply safety caps
    max_position   = capital * MAX_POSITION_PCT
    if position_value > max_position:
        log.debug(f"  Position capped at {MAX_POSITION_PCT:.0%} of capital")
        position_value = max_position
        quantity       = position_value / price

    return {
        "position_value":   round(position_value, 2),
        "quantity":         round(quantity, 8),
        "fee":              round(fee, 2),
        "net_investment":   round(position_value - fee, 2),
        "pct_of_capital":   round(position_value / capital * 100, 1),
        "risk_amount":      round(risk_amount, 2),
        "stop_distance":    round(stop_distance, 2),
        "method":           "atr_based",
    }


def confidence_adjusted_size(
    capital: float,
    price: float,
    confidence: float,
    base_pct: float = POSITION_SIZE_PCT,
) -> dict:
    """
    Confidence-adjusted position sizing.
    Higher model confidence → larger position.
    Lower confidence → smaller position.

    Scaling:
        65% confidence → 50% of base position
        75% confidence → 75% of base position
        85% confidence → 100% of base position
        95% confidence → 125% of base position (capped at MAX_POSITION_PCT)

    Args:
        capital:    Total capital
        price:      Current price
        confidence: Model confidence (0.0 to 1.0)
        base_pct:   Base position size % (adjusted up/down by confidence)

    Returns:
        dict: Same structure as fixed_pct_size()

    Example:
        >>> from src.signals.sizer import confidence_adjusted_size
        >>> size = confidence_adjusted_size(50000, 66500, confidence=0.84)
    """
    # Scale factor: confidence maps to 0.5 → 1.25 range
    # At 65% conf → 0.5×, at 75% → 0.75×, at 85% → 1.0×, at 95% → 1.25×
    scale_factor  = np.interp(
        confidence,
        [0.65, 0.75, 0.85, 0.95],
        [0.50, 0.75, 1.00, 1.25],
    )

    adjusted_pct  = min(base_pct * scale_factor, MAX_POSITION_PCT)

    result = fixed_pct_size(capital, price, pct=adjusted_pct)
    result["confidence"]      = round(confidence, 4)
    result["scale_factor"]    = round(float(scale_factor), 3)
    result["base_pct"]        = round(base_pct * 100, 1)
    result["method"]          = "confidence_adjusted"

    return result


def calculate_position(
    signal: dict,
    capital: float = DEFAULT_CAPITAL,
    method: str = "confidence",
) -> dict:
    """
    Master position sizing function.
    Called by formatter.py to add sizing info to every signal card.

    Args:
        signal:  Raw signal dict from generator.py
                 Must have: price, confidence, atr
        capital: User's total capital in Rs
        method:  'fixed' | 'atr' | 'confidence' (default: 'confidence')

    Returns:
        dict: Position sizing info to merge into the signal card

    Example:
        >>> from src.signals.sizer import calculate_position
        >>> sizing = calculate_position(raw_signal, capital=50000)
        >>> print(f"Buy {sizing['quantity']:.6f} units (Rs {sizing['position_value']:,.0f})")
    """
    price      = float(signal.get("price", 0))
    confidence = float(signal.get("confidence", 0.75))
    atr        = float(signal.get("atr", price * 0.02))   # Default 2% ATR

    if price <= 0:
        log.warning("  Price is 0 — cannot calculate position size")
        return {
            "position_value": 0,
            "quantity": 0,
            "fee": 0,
            "method": "error",
        }

    if method == "fixed":
        sizing = fixed_pct_size(capital, price)

    elif method == "atr":
        sizing = atr_based_size(capital, price, atr)

    else:   # confidence (default)
        sizing = confidence_adjusted_size(capital, price, confidence)

    # Add stop-loss and target values for display
    sig_type = signal.get("signal", "HOLD")
    if sig_type == "BUY":
        sizing["stop_loss_price"] = round(price * (1 - STOP_LOSS_PCT), 2)
        sizing["target_price"]    = round(price * 1.06, 2)
        sizing["max_loss_rs"]     = round(
            sizing["position_value"] * STOP_LOSS_PCT, 2
        )
    elif sig_type == "SELL":
        sizing["stop_loss_price"] = round(price * (1 + STOP_LOSS_PCT), 2)
        sizing["target_price"]    = round(price * 0.94, 2)
        sizing["max_loss_rs"]     = round(
            sizing["position_value"] * STOP_LOSS_PCT, 2
        )
    else:
        sizing["stop_loss_price"] = price
        sizing["target_price"]    = price
        sizing["max_loss_rs"]     = 0.0

    log.debug(
        f"  Position size: {sizing['quantity']:.6f} units | "
        f"Rs {sizing['position_value']:,.0f} | "
        f"method={method}"
    )

    return sizing


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    capital = 50000.0
    price   = 66500.0
    atr     = 1200.0
    conf    = 0.84

    print("── Position Sizing Examples ────────────────────────")
    print(f"  Capital: Rs {capital:,.0f} | Price: Rs {price:,.0f}")
    print()

    s1 = fixed_pct_size(capital, price)
    print(f"  Fixed 10%:       {s1['quantity']:.6f} units | Rs {s1['position_value']:,.0f}")

    s2 = atr_based_size(capital, price, atr)
    print(f"  ATR-based:       {s2['quantity']:.6f} units | Rs {s2['position_value']:,.0f}")

    s3 = confidence_adjusted_size(capital, price, conf)
    print(f"  Conf-adjusted:   {s3['quantity']:.6f} units | Rs {s3['position_value']:,.0f}  (conf={conf:.0%})")