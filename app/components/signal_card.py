"""
app/components/signal_card.py
===============================
Reusable signal card component for the Streamlit dashboard.
Renders a fully formatted signal card for any signal dict.

Usage:
    from app.components.signal_card import render_signal_card, render_mini_card
    render_signal_card(signal_dict)
    render_mini_card(signal_dict)
"""

import streamlit as st
from config.settings import COIN_DISPLAY

SIGNAL_COLORS = {"BUY": "#16a34a", "SELL": "#dc2626", "HOLD": "#d97706"}
SIGNAL_EMOJIS = {"BUY": "🟢",      "SELL": "🔴",       "HOLD": "🟡"}
SIGNAL_BG     = {"BUY": "#f0fdf4", "SELL": "#fef2f2",  "HOLD": "#fffbeb"}


def _conf_bar(confidence: float, width: int = 10) -> str:
    """Turn a 0-1 confidence float into a unicode progress bar."""
    filled = round(confidence * width)
    return "█" * filled + "░" * (width - filled)


def render_signal_card(signal: dict, show_reasons: bool = True) -> None:
    """
    Render a full-size signal card.

    Shows: coin name, signal type, confidence bar, price table
    (entry zone, target, stop-loss, risk/reward, position size),
    and optionally the list of reasons.

    Args:
        signal:       Formatted signal dict from formatter.format_signal()
        show_reasons: If True, show the "Why this signal?" expander

    Example:
        >>> from app.components.signal_card import render_signal_card
        >>> render_signal_card(signal_dict)
    """
    sig     = signal.get("signal", "HOLD")
    coin    = signal.get("coin", "UNKNOWN")
    conf    = float(signal.get("confidence", 0))
    price   = float(signal.get("price", 0))
    target  = float(signal.get("target_price", price))
    stop    = float(signal.get("stop_loss_price", price))
    rr      = signal.get("risk_reward", 0)
    el      = float(signal.get("entry_low", price))
    eh      = float(signal.get("entry_high", price))
    qty     = float(signal.get("quantity", 0))
    pv      = float(signal.get("position_value", 0))
    reasons = signal.get("reasons", [])
    ts      = signal.get("timestamp", signal.get("cached_at", ""))

    color   = SIGNAL_COLORS.get(sig, "#888")
    emoji   = SIGNAL_EMOJIS.get(sig, "⚪")
    bg      = SIGNAL_BG.get(sig, "#f9f9f9")
    display = COIN_DISPLAY.get(coin, coin.replace("_", "/"))

    # ── Percentage changes ────────────────────────────────────────────────────
    target_pct = ((target - price) / price * 100) if price else 0
    stop_pct   = ((stop   - price) / price * 100) if price else 0
    sign_t     = "+" if target_pct >= 0 else ""
    sign_s     = "+" if stop_pct   >= 0 else ""

    st.markdown(f"""
    <div style="
        border: 2px solid {color};
        border-radius: 14px;
        padding: 20px 22px;
        margin-bottom: 16px;
        background: {bg};
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    ">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
                <h3 style="margin:0;color:{color};font-size:20px;">
                    {emoji} {display} — {sig}
                </h3>
                <p style="font-size:13px;color:#777;margin:4px 0 0;">
                    {_conf_bar(conf)} {conf:.0%} confidence
                </p>
            </div>
            <div style="text-align:right;font-size:12px;color:#aaa;">
                {ts[:16].replace("T"," ") if ts else ""} UTC
            </div>
        </div>

        <hr style="border:none;border-top:1px solid {color}22;margin:14px 0 12px;"/>

        <table style="width:100%;font-size:14px;border-collapse:collapse;">
            <tr>
                <td style="padding:5px 0;color:#555;width:50%;">📌 Current price</td>
                <td style="text-align:right;font-weight:700;font-size:15px;">
                    ₹{price:,.2f}
                </td>
            </tr>
            <tr>
                <td style="padding:5px 0;color:#555;">🎯 Entry zone</td>
                <td style="text-align:right;">₹{el:,.2f} – ₹{eh:,.2f}</td>
            </tr>
            <tr>
                <td style="padding:5px 0;color:#16a34a;font-weight:500;">
                    ✅ Target price
                </td>
                <td style="text-align:right;color:#16a34a;font-weight:600;">
                    ₹{target:,.2f}
                    <span style="font-size:12px;color:#888;margin-left:6px;">
                        ({sign_t}{target_pct:.1f}%)
                    </span>
                </td>
            </tr>
            <tr>
                <td style="padding:5px 0;color:#dc2626;font-weight:500;">
                    🛑 Stop loss
                </td>
                <td style="text-align:right;color:#dc2626;font-weight:600;">
                    ₹{stop:,.2f}
                    <span style="font-size:12px;color:#888;margin-left:6px;">
                        ({sign_s}{stop_pct:.1f}%)
                    </span>
                </td>
            </tr>
            <tr>
                <td style="padding:5px 0;color:#555;">⚖️ Risk / Reward</td>
                <td style="text-align:right;">1 : {rr}</td>
            </tr>
            <tr>
                <td style="padding:5px 0;color:#555;">💰 Position size</td>
                <td style="text-align:right;">
                    {qty:.6f} units
                    <span style="font-size:12px;color:#888;">(₹{pv:,.0f})</span>
                </td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

    if show_reasons and reasons:
        with st.expander(f"💡 Why {sig}? ({len(reasons)} reasons)"):
            for i, reason in enumerate(reasons, 1):
                icon = "🟢" if sig == "BUY" else "🔴" if sig == "SELL" else "🟡"
                st.markdown(f"{icon} **{i}.** {reason}")


def render_mini_card(signal: dict) -> None:
    """
    Render a compact single-line signal card.
    Used in tight layouts like the sidebar or notification feed.

    Args:
        signal: Formatted signal dict

    Example:
        >>> from app.components.signal_card import render_mini_card
        >>> render_mini_card(signal_dict)
    """
    sig    = signal.get("signal", "HOLD")
    coin   = signal.get("coin", "?")
    conf   = float(signal.get("confidence", 0))
    price  = float(signal.get("price", 0))
    color  = SIGNAL_COLORS.get(sig, "#888")
    emoji  = SIGNAL_EMOJIS.get(sig, "⚪")
    display = COIN_DISPLAY.get(coin, coin.replace("_", "/"))

    st.markdown(f"""
    <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        border-radius: 8px;
        background: white;
        border: 1px solid {color}44;
        margin-bottom: 6px;
        font-size: 13px;
    ">
        <span style="font-weight:600;color:{color};">{emoji} {display}</span>
        <span style="color:{color};font-weight:500;">{sig}</span>
        <span style="color:#888;">{conf:.0%}</span>
        <span style="color:#555;">₹{price:,.0f}</span>
    </div>
    """, unsafe_allow_html=True)


def render_no_signal_card(coin: str) -> None:
    """
    Render a placeholder card when no signal is available for a coin.

    Args:
        coin: Coin name e.g. 'BTC_USD'
    """
    display = COIN_DISPLAY.get(coin, coin.replace("_", "/"))
    st.markdown(f"""
    <div style="
        border: 2px solid #e5e7eb;
        border-radius: 14px;
        padding: 20px 22px;
        margin-bottom: 16px;
        background: #f9fafb;
        text-align: center;
        color: #9ca3af;
    ">
        <h3 style="margin:0 0 8px;color:#d1d5db;">⏳ {display}</h3>
        <p style="margin:0;font-size:13px;">
            Waiting for first signal...<br/>
            Signals run every hour automatically.
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_signal_badge(signal: str, confidence: float) -> str:
    """
    Return an HTML badge string for a signal.
    Use with st.markdown(..., unsafe_allow_html=True).

    Args:
        signal:     'BUY' | 'SELL' | 'HOLD'
        confidence: 0.0 to 1.0

    Returns:
        str: HTML string with coloured badge

    Example:
        >>> badge = render_signal_badge("BUY", 0.84)
        >>> st.markdown(f"Latest: {badge}", unsafe_allow_html=True)
    """
    color = SIGNAL_COLORS.get(signal, "#888")
    emoji = SIGNAL_EMOJIS.get(signal, "⚪")
    return (
        f'<span style="background:{color};color:white;'
        f'padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">'
        f'{emoji} {signal} {confidence:.0%}</span>'
    )