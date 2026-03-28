"""
app/pages/dashboard.py
========================
Live trading signals page — the main page users see first.
Shows real-time signal cards for all tracked coins.

Imported and rendered by app/main.py
"""

import json
import os
import requests
import streamlit as st
from datetime import datetime, timezone

from config.settings import COINS, COIN_DISPLAY, API_PORT

API_BASE = f"http://localhost:{API_PORT}"

SIGNAL_COLORS = {"BUY": "#16a34a", "SELL": "#dc2626", "HOLD": "#d97706"}
SIGNAL_EMOJIS = {"BUY": "🟢",      "SELL": "🔴",       "HOLD": "🟡"}


def _fetch(endpoint: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def _conf_bar(confidence: float) -> str:
    filled = int(confidence * 10)
    return "█" * filled + "░" * (10 - filled)


def _signal_card(coin: str, sig: dict) -> None:
    signal  = sig.get("signal", "HOLD")
    conf    = sig.get("confidence", 0)
    price   = sig.get("price", 0)
    target  = sig.get("target_price", price)
    stop    = sig.get("stop_loss_price", price)
    rr      = sig.get("risk_reward", 0)
    el      = sig.get("entry_low", price)
    eh      = sig.get("entry_high", price)
    qty     = sig.get("quantity", 0)
    pv      = sig.get("position_value", 0)
    reasons = sig.get("reasons", [])
    color   = SIGNAL_COLORS.get(signal, "#888")
    emoji   = SIGNAL_EMOJIS.get(signal, "⚪")

    bg = {"BUY": "#f0fdf4", "SELL": "#fef2f2", "HOLD": "#fffbeb"}.get(signal, "#f9f9f9")

    st.markdown(f"""
    <div style="border:2px solid {color};border-radius:12px;padding:20px;
                margin-bottom:16px;background:{bg};">
        <h3 style="margin:0;color:{color};">{emoji} {COIN_DISPLAY.get(coin, coin)} — {signal}</h3>
        <p style="font-size:13px;color:#666;margin:4px 0 14px;">
            {_conf_bar(conf)} {conf:.0%} confidence
        </p>
        <table style="width:100%;font-size:14px;border-collapse:collapse;">
            <tr><td style="padding:4px 0;color:#555;">Current price</td>
                <td style="text-align:right;font-weight:600;">₹{price:,.2f}</td></tr>
            <tr><td style="padding:4px 0;color:#555;">Entry zone</td>
                <td style="text-align:right;">₹{el:,.2f} – ₹{eh:,.2f}</td></tr>
            <tr><td style="padding:4px 0;color:#16a34a;">Target price</td>
                <td style="text-align:right;color:#16a34a;font-weight:600;">₹{target:,.2f}</td></tr>
            <tr><td style="padding:4px 0;color:#dc2626;">Stop loss</td>
                <td style="text-align:right;color:#dc2626;font-weight:600;">₹{stop:,.2f}</td></tr>
            <tr><td style="padding:4px 0;color:#555;">Risk / Reward</td>
                <td style="text-align:right;">1 : {rr}</td></tr>
            <tr><td style="padding:4px 0;color:#555;">Position size</td>
                <td style="text-align:right;">{qty:.6f} units (₹{pv:,.0f})</td></tr>
        </table>
    </div>""", unsafe_allow_html=True)

    if reasons:
        with st.expander("Why this signal?"):
            for i, r in enumerate(reasons, 1):
                st.markdown(f"**{i}.** {r}")


def render(selected_coins: list, capital: float):
    st.title("📊 Live Trading Signals")
    st.caption(
        "Signals generated every hour • Model reads 37 technical features "
        "to predict 24-hour price direction"
    )

    all_signals = _fetch("/signals/all").get("signals", {})

    if not all_signals:
        st.warning(
            "⏳ No cached signals yet. The scheduler runs every hour automatically.\n\n"
            "You can trigger a manual run by restarting `python main.py`."
        )
        for coin in selected_coins:
            st.info(f"{COIN_DISPLAY.get(coin, coin)} — waiting for first signal...")
        return

    col1, col2 = st.columns(2)
    for idx, coin in enumerate(selected_coins):
        sig = all_signals.get(coin)
        if not sig:
            continue
        with (col1 if idx % 2 == 0 else col2):
            _signal_card(coin, sig)

    # Last updated
    last_ts = None
    for sig in all_signals.values():
        ts = sig.get("cached_at", sig.get("timestamp", ""))
        if ts and (last_ts is None or ts > last_ts):
            last_ts = ts
    if last_ts:
        try:
            dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            st.caption(f"Last updated: {dt.strftime('%H:%M UTC, %d %b %Y')}")
        except Exception:
            pass