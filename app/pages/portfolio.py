"""
app/pages/portfolio.py
========================
Paper trading portfolio tracker.
Shows simulated P&L as if you had acted on every signal.
"""

import os
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime, timezone, timedelta

from config.settings import SIGNAL_LOG, COIN_DISPLAY, COINS


def _load_signals() -> pd.DataFrame:
    if not os.path.exists(SIGNAL_LOG):
        return pd.DataFrame()
    try:
        with open(SIGNAL_LOG) as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def _simulate_portfolio(df: pd.DataFrame, capital: float) -> pd.DataFrame:
    """
    Simulate paper trades from signal log.
    BUY → open LONG at signal price
    SELL → close LONG and open SHORT (or just close)
    HOLD → skip
    """
    if df.empty or "signal" not in df.columns:
        return pd.DataFrame()

    trades  = []
    equity  = capital
    pos     = None
    entry_p = 0.0
    entry_c = ""

    df_sorted = df.sort_values("timestamp") if "timestamp" in df.columns else df

    for _, row in df_sorted.iterrows():
        sig   = row.get("signal", "HOLD")
        coin  = row.get("coin", "")
        price = float(row.get("price", 0))
        conf  = float(row.get("confidence", 0))
        ts    = row.get("timestamp", "")

        if price <= 0:
            continue

        pos_size = equity * 0.10
        qty      = pos_size / price

        if pos is None:
            if sig == "BUY" and conf >= 0.65:
                pos     = {"dir": "LONG", "price": price, "qty": qty,
                           "coin": coin, "ts": ts}
                entry_p = price
                entry_c = coin
        elif pos["dir"] == "LONG":
            if sig == "SELL" or (coin == pos["coin"] and sig == "SELL"):
                pnl    = (price - pos["price"]) * pos["qty"]
                equity += pnl
                trades.append({
                    "entry_time": pos["ts"],
                    "exit_time":  ts,
                    "coin":       pos["coin"],
                    "direction":  "LONG",
                    "entry_price":pos["price"],
                    "exit_price": price,
                    "pnl":        round(pnl, 2),
                    "result":     "WIN" if pnl > 0 else "LOSS",
                    "equity":     round(equity, 2),
                })
                pos = None

    return pd.DataFrame(trades)


def render(capital: float):
    st.title("💼 Paper Trading Portfolio")
    st.caption(
        "Simulated portfolio — tracks performance as if you had acted on "
        "every signal above 65% confidence."
    )

    df = _load_signals()

    if df.empty:
        st.info(
            "No signals logged yet.\n\n"
            "Run `python main.py` and wait for the first hourly signal cycle."
        )
        return

    # ── Top-line metrics ──────────────────────────────────────────────────────
    total_signals  = len(df)
    buy_signals    = (df["signal"] == "BUY").sum()  if "signal" in df.columns else 0
    sell_signals   = (df["signal"] == "SELL").sum() if "signal" in df.columns else 0
    hold_signals   = (df["signal"] == "HOLD").sum() if "signal" in df.columns else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total signals",   total_signals)
    m2.metric("BUY signals",     buy_signals)
    m3.metric("SELL signals",    sell_signals)
    m4.metric("HOLD signals",    hold_signals)

    # ── Simulate paper trades ─────────────────────────────────────────────────
    trades_df = _simulate_portfolio(df, capital)

    st.markdown("---")

    if trades_df.empty:
        st.info(
            "No completed paper trades yet.\n\n"
            "Trades complete when a BUY signal is followed by a SELL signal "
            "for the same coin."
        )
    else:
        wins     = (trades_df["pnl"] > 0).sum()
        losses   = (trades_df["pnl"] <= 0).sum()
        total_pnl = trades_df["pnl"].sum()
        win_rate  = wins / len(trades_df) * 100 if len(trades_df) else 0
        final_cap = trades_df["equity"].iloc[-1] if not trades_df.empty else capital

        st.subheader("Paper trade performance")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Completed trades", len(trades_df))
        c2.metric("Win rate",         f"{win_rate:.1f}%")
        c3.metric("Total P&L",        f"₹{total_pnl:,.0f}",
                  delta=f"{total_pnl/capital*100:+.2f}%")
        c4.metric("Wins / Losses",    f"{wins} / {losses}")
        c5.metric("Final capital",    f"₹{final_cap:,.0f}")

        # Equity curve
        if "equity" in trades_df.columns:
            fig = go.Figure()
            x_vals = list(range(len(trades_df) + 1))
            y_vals = [capital] + trades_df["equity"].tolist()
            fig.add_trace(go.Scatter(
                x=x_vals, y=y_vals,
                mode="lines+markers",
                name="Portfolio value",
                line=dict(color="#2563EB", width=2),
                fill="tozeroy",
                fillcolor="rgba(37,99,235,0.08)",
            ))
            fig.add_hline(y=capital, line_dash="dash", line_color="gray",
                          annotation_text="Starting capital")
            fig.update_layout(
                title="Portfolio equity curve",
                xaxis_title="Trade #",
                yaxis_title="Portfolio value (₹)",
                height=320,
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Trade log table
        st.subheader("Trade log")
        show_cols = [c for c in [
            "entry_time", "coin", "direction", "entry_price",
            "exit_price", "pnl", "result",
        ] if c in trades_df.columns]
        if show_cols:
            st.dataframe(
                trades_df[show_cols].sort_values(
                    "entry_time", ascending=False
                ) if "entry_time" in trades_df.columns else trades_df[show_cols],
                use_container_width=True, hide_index=True,
            )

    # ── Signal distribution pie ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Signal distribution")

    if "signal" in df.columns:
        col_a, col_b = st.columns(2)
        with col_a:
            counts = df["signal"].value_counts()
            fig = px.pie(
                values=counts.values, names=counts.index,
                color=counts.index,
                color_discrete_map={
                    "BUY": "#16a34a", "SELL": "#dc2626", "HOLD": "#d97706"
                },
                hole=0.4, title="By signal type",
            )
            fig.update_layout(height=280, margin=dict(t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            if "coin" in df.columns:
                cc = df["coin"].value_counts()
                cc.index = [COIN_DISPLAY.get(c, c) for c in cc.index]
                fig2 = px.bar(
                    x=cc.index, y=cc.values,
                    title="By coin",
                    color=cc.index,
                    labels={"x": "Coin", "y": "Count"},
                )
                fig2.update_layout(height=280, margin=dict(t=40, b=0),
                                   showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)