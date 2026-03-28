"""
src/signals/filter.py
=======================
PURPOSE:
    Filter raw model signals based on user risk level and confidence threshold.
    Only signals that pass the filter are sent to the formatter and delivered.

WHY FILTER?
    The model generates a prediction every hour for every coin.
    Most of these predictions have low confidence (55-70%).
    Sending ALL of them would overwhelm users and reduce quality.
    We only send signals we are sufficiently confident about.

RISK LEVEL → CONFIDENCE THRESHOLD:
    Low    → 85%+ confidence (very selective, fewer but higher quality signals)
    Medium → 75%+ confidence (balanced)
    High   → 65%+ confidence (more signals, more risk)
"""

import logging
import sys
from pathlib import Path

# Add repo root to path so absolute imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.features.labeler import LABEL_HOLD

log = logging.getLogger(__name__)

RISK_THRESHOLDS = {
    "low":    0.85,
    "medium": 0.75,
    "high":   0.65,
}


def should_send_signal(signal: dict, risk_level: str = "medium") -> tuple[bool, str]:
    """
    Decide whether a raw signal should be delivered to the user.

    Args:
        signal:     Raw signal dict from generator.py
        risk_level: User's risk preference ('low', 'medium', 'high')

    Returns:
        tuple: (should_send: bool, reason: str)

    Example:
        >>> from src.signals.filter import should_send_signal
        >>> ok, reason = should_send_signal(signal, risk_level='medium')
    """
    threshold = RISK_THRESHOLDS.get(risk_level.lower(), 0.75)

    # Rule 1: Never send HOLD signals — they carry no actionable information
    if signal.get("signal") == "HOLD" or signal.get("signal_int") == LABEL_HOLD:
        return False, "Signal is HOLD — no action needed"

    # Rule 2: Confidence must meet the risk threshold
    confidence = signal.get("confidence", 0)
    if confidence < threshold:
        return False, (
            f"Confidence {confidence:.1%} is below {risk_level} threshold ({threshold:.0%})"
        )

    # Rule 3: Volume must be at least 80% of normal (avoid low-liquidity signals)
    volume_ratio = signal.get("volume_ratio", 1.0)
    if volume_ratio < 0.8:
        return False, f"Volume ratio {volume_ratio:.2f} too low — market is illiquid"

    return True, "Signal passes all filters"


def filter_signals(signals: list[dict], risk_level: str = "medium") -> list[dict]:
    """
    Filter a list of signals and return only the ones that should be sent.

    Args:
        signals:    List of raw signal dicts
        risk_level: User's risk preference

    Returns:
        list: Filtered signals with a 'filter_reason' key added
    """
    passed  = []
    blocked = 0

    for sig in signals:
        ok, reason = should_send_signal(sig, risk_level)
        if ok:
            sig["filter_reason"] = reason
            passed.append(sig)
        else:
            blocked += 1
            log.debug(f"  Filtered out {sig.get('coin')} {sig.get('signal')}: {reason}")

    log.info(f"  Signal filter: {len(passed)} passed, {blocked} blocked "
             f"(risk_level={risk_level})")
    return passed