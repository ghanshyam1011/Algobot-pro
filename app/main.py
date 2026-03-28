"""
app/main.py
============
AlgoBot Pro — Streamlit Dashboard

A complete web UI showing:
- Live signal cards for all 4 coins
- Price + RSI charts
- Signal history table
- Backtest performance metrics
- Portfolio paper tracker
- Settings panel

HOW TO RUN:
    streamlit run app/main.py

DEPENDENCIES:
    pip install streamlit plotly requests pandas
"""

import os
import json
import time
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime, timezone

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AlgoBot Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE  = "http://localhost:8000"
COINS     = ["BTC_USD", "ETH_USD", "BNB_USD", "SOL_USD"]
COIN_DISPLAY = {
    "BTC_USD": "BTC/USD",
    "ETH_USD": "ETH/USD",
    "BNB_USD": "BNB/USD",
    "SOL_USD": "SOL/USD",
}

SIGNAL_COLORS = {
    "BUY":  "#16a34a",   # green
    "SELL": "#dc2626",   # red
    "HOLD": "#d97706",   # amber
}

SIGNAL_EMOJIS = {
    "BUY":  "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def fetch_api(endpoint: str) -> dict:
    """Call the FastAPI backend. Returns empty dict if API is down."""
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def load_local_features(coin: str) -> pd.DataFrame:
    """Load the feature CSV directly — fallback when API is down."""
    path = os.path.join("data", "processed", f"{coin}_features.csv")
    if os.path.exists(path):
        return pd.read_csv(path, parse_dates=["datetime"])
    return pd.DataFrame()


def load_signal_history_local() -> pd.DataFrame:
    """Load signal log from disk."""
    path = os.path.join("data", "signal_log.json")
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        with open(path) as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def confidence_bar(confidence: float) -> str:
    """Turn a 0-1 confidence into a progress bar string."""
    filled = int(confidence * 10)
    return "█" * filled + "░" * (10 - filled)


# ── sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.title("⚙️ AlgoBot Pro")
        st.markdown("---")

        st.subheader("Your settings")
        capital = st.number_input(
            "Capital (₹)", min_value=1000, max_value=10_000_000,
            value=50000, step=1000
        )
        risk_level = st.selectbox(
            "Risk level",
            ["Low (85%+ confidence)", "Medium (75%+)", "High (65%+)"],
            index=1,
        )
        selected_coins = st.multiselect(
            "Track coins",
            options=COINS,
            default=COINS,
            format_func=lambda c: COIN_DISPLAY[c],
        )

        st.markdown("---")
        st.subheader("Navigation")
        page = st.radio(
            "Go to",
            ["📊 Live Signals", "📈 Charts", "📋 History",
             "🔬 Backtest", "💼 Portfolio"],
            label_visibility="collapsed",
        )

        st.markdown("---")
        api_ok = bool(fetch_api("/"))
        if api_ok:
            st.success("🟢 API connected")
        else:
            st.error("🔴 API offline — showing cached data")

        if st.button("🔄 Refresh signals"):
            st.rerun()

        st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

    return page, capital, risk_level, selected_coins


# ── page: live signals ────────────────────────────────────────────────────────

def page_live_signals(capital: float, selected_coins: list):
    st.title("📊 Live Trading Signals")
    st.caption(
        "Signals generated every hour. Model reads 37 technical features "
        "to predict 24-hour price direction."
    )

    # Fetch all signals
    all_signals = fetch_api("/signals/all").get("signals", {})

    if not all_signals:
        st.warning(
            "⚠️ No cached signals yet. The scheduler runs every hour automatically. "
            "You can also trigger manually by restarting `python main.py`."
        )
        # Show placeholder cards
        for coin in selected_coins:
            with st.expander(f"{COIN_DISPLAY[coin]} — waiting for first signal..."):
                st.info("Signal will appear after the scheduler runs.")
        return

    cols = st.columns(min(len(selected_coins), 2))
    col_idx = 0

    for coin in selected_coins:
        sig = all_signals.get(coin, {})
        if not sig:
            continue

        signal    = sig.get("signal", "HOLD")
        conf      = sig.get("confidence", 0)
        price     = sig.get("price", 0)
        target    = sig.get("target_price", 0)
        stop      = sig.get("stop_loss_price", 0)
        rr        = sig.get("risk_reward", 0)
        entry_low = sig.get("entry_low", 0)
        entry_hi  = sig.get("entry_high", 0)
        qty       = sig.get("quantity", 0)
        pos_val   = sig.get("position_value", capital * 0.10)
        reasons   = sig.get("reasons", [])
        color     = SIGNAL_COLORS.get(signal, "#888")
        emoji     = SIGNAL_EMOJIS.get(signal, "⚪")

        with cols[col_idx % 2]:
            st.markdown(
                f"""
                <div style="
                    border: 2px solid {color};
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 16px;
                    background: {'#f0fdf4' if signal=='BUY' else '#fef2f2' if signal=='SELL' else '#fffbeb'};
                ">
                    <h3 style="margin:0; color:{color};">
                        {emoji} {COIN_DISPLAY[coin]} — {signal}
                    </h3>
                    <p style="font-size:13px; color:#666; margin:4px 0 16px;">
                        {confidence_bar(conf)} {conf:.0%} confidence
                    </p>
                    <table style="width:100%; font-size:14px; border-collapse:collapse;">
                        <tr>
                            <td style="padding:4px 0; color:#666;">Current price</td>
                            <td style="text-align:right; font-weight:600;">₹{price:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0; color:#666;">Entry zone</td>
                            <td style="text-align:right;">₹{entry_low:,.2f} – ₹{entry_hi:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0; color:#16a34a;">Target price</td>
                            <td style="text-align:right; color:#16a34a; font-weight:600;">
                                ₹{target:,.2f}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0; color:#dc2626;">Stop loss</td>
                            <td style="text-align:right; color:#dc2626; font-weight:600;">
                                ₹{stop:,.2f}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0; color:#666;">Risk / Reward</td>
                            <td style="text-align:right;">1 : {rr}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0; color:#666;">Position size</td>
                            <td style="text-align:right;">{qty:.6f} units (₹{pos_val:,.0f})</td>
                        </tr>
                    </table>
                """,
                unsafe_allow_html=True,
            )

            if reasons:
                st.markdown("**Why this signal?**")
                for i, reason in enumerate(reasons, 1):
                    st.markdown(f"&nbsp;&nbsp;{i}. {reason}")

            st.markdown("</div>", unsafe_allow_html=True)

        col_idx += 1


# ── page: charts ─────────────────────────────────────────────────────────────

def page_charts(selected_coins: list):
    st.title("📈 Price & Indicator Charts")

    coin = st.selectbox(
        "Select coin",
        selected_coins,
        format_func=lambda c: COIN_DISPLAY[c],
    )

    df = load_local_features(coin)
    if df.empty:
        st.error(f"No feature data found for {coin}. Run the pipeline first.")
        return

    # Show last N candles
    n = st.slider("Candles to show", min_value=50, max_value=500, value=200, step=50)
    df = df.tail(n).reset_index(drop=True)

    # ── Candlestick chart ─────────────────────────────────────────────────────
    st.subheader(f"{COIN_DISPLAY[coin]} — Price")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["datetime"],
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        name="Price",
        increasing_line_color="#16a34a",
        decreasing_line_color="#dc2626",
    ))

    if "ema_9" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["ema_9"],
            name="EMA 9", line=dict(color="#3b82f6", width=1),
        ))
    if "ema_21" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["ema_21"],
            name="EMA 21", line=dict(color="#f59e0b", width=1),
        ))
    if "ema_50" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["ema_50"],
            name="EMA 50", line=dict(color="#8b5cf6", width=1.5),
        ))
    if "bb_upper" in df.columns and "bb_lower" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["bb_upper"],
            name="BB Upper", line=dict(color="gray", width=1, dash="dot"),
        ))
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["bb_lower"],
            name="BB Lower", line=dict(color="gray", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(128,128,128,0.05)",
        ))

    fig.update_layout(
        height=400, xaxis_rangeslider_visible=False,
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", y=1.02),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── RSI chart ─────────────────────────────────────────────────────────────
    if "rsi" in df.columns:
        st.subheader("RSI (14)")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df["datetime"], y=df["rsi"],
            name="RSI", line=dict(color="#3b82f6", width=2),
            fill="tonexty", fillcolor="rgba(59,130,246,0.08)",
        ))
        fig2.add_hline(y=70, line_dash="dash", line_color="#dc2626",
                       annotation_text="Overbought (70)")
        fig2.add_hline(y=30, line_dash="dash", line_color="#16a34a",
                       annotation_text="Oversold (30)")
        fig2.update_layout(
            height=200, yaxis_range=[0, 100],
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=0, t=10, b=0),
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── MACD chart ────────────────────────────────────────────────────────────
    if "macd_line" in df.columns:
        st.subheader("MACD")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=df["datetime"], y=df["macd_line"],
            name="MACD", line=dict(color="#3b82f6", width=2),
        ))
        fig3.add_trace(go.Scatter(
            x=df["datetime"], y=df["macd_signal"],
            name="Signal", line=dict(color="#f59e0b", width=1.5),
        ))
        colors = ["#16a34a" if v >= 0 else "#dc2626"
                  for v in df["macd_histogram"]]
        fig3.add_trace(go.Bar(
            x=df["datetime"], y=df["macd_histogram"],
            name="Histogram", marker_color=colors, opacity=0.6,
        ))
        fig3.add_hline(y=0, line_color="gray", line_width=0.5)
        fig3.update_layout(
            height=200, plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ── Volume chart ──────────────────────────────────────────────────────────
    st.subheader("Volume")
    fig4 = go.Figure()
    vol_colors = [
        "#16a34a" if df["close"].iloc[i] >= df["open"].iloc[i] else "#dc2626"
        for i in range(len(df))
    ]
    fig4.add_trace(go.Bar(
        x=df["datetime"], y=df["volume"],
        marker_color=vol_colors, name="Volume", opacity=0.7,
    ))
    fig4.update_layout(
        height=150, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
    )
    st.plotly_chart(fig4, use_container_width=True)


# ── page: history ─────────────────────────────────────────────────────────────

def page_history():
    st.title("📋 Signal History")

    df = load_signal_history_local()

    if df.empty:
        st.info(
            "No signal history yet. Signals are logged automatically "
            "every time the scheduler runs."
        )
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        coin_filter = st.multiselect(
            "Filter by coin", COINS,
            format_func=lambda c: COIN_DISPLAY[c],
        )
    with col2:
        sig_filter = st.multiselect(
            "Filter by signal", ["BUY", "SELL", "HOLD"],
        )
    with col3:
        min_conf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)

    filtered = df.copy()
    if coin_filter:
        filtered = filtered[filtered["coin"].isin(coin_filter)]
    if sig_filter:
        filtered = filtered[filtered["signal"].isin(sig_filter)]
    if "confidence" in filtered.columns:
        filtered = filtered[filtered["confidence"] >= min_conf]

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total signals", len(filtered))
    if "signal" in filtered.columns:
        buy_pct  = (filtered["signal"] == "BUY").mean() * 100
        sell_pct = (filtered["signal"] == "SELL").mean() * 100
        c2.metric("BUY signals",  f"{buy_pct:.1f}%")
        c3.metric("SELL signals", f"{sell_pct:.1f}%")
    if "confidence" in filtered.columns:
        c4.metric("Avg confidence", f"{filtered['confidence'].mean():.1%}")

    st.markdown("---")

    # Signal table
    display_cols = [c for c in [
        "timestamp", "coin", "signal", "confidence",
        "price", "target_price", "stop_loss_price", "risk_reward"
    ] if c in filtered.columns]

    if display_cols:
        st.dataframe(
            filtered[display_cols].sort_values(
                "timestamp", ascending=False
            ).head(100),
            use_container_width=True,
            hide_index=True,
        )


# ── page: backtest ────────────────────────────────────────────────────────────

def page_backtest():
    st.title("🔬 Backtest Performance")
    st.caption(
        "Walk-forward simulation on the 20% test data the model never saw during training."
    )

    cols = st.columns(len(COINS))
    for i, coin in enumerate(COINS):
        data = fetch_api(f"/backtest/{coin}")
        with cols[i]:
            st.subheader(COIN_DISPLAY[coin])
            if not data:
                st.warning("No backtest data yet")
                continue

            total_ret = data.get("total_return_pct", 0)
            win_rate  = data.get("win_rate_pct", 0)
            max_dd    = data.get("max_drawdown_pct", 0)
            sharpe    = data.get("sharpe_ratio", 0)
            trades    = data.get("total_trades", 0)
            pf        = data.get("profit_factor", 0)

            ret_color = "normal" if total_ret >= 0 else "inverse"
            st.metric("Total return",   f"{total_ret:+.2f}%",    delta_color=ret_color)
            st.metric("Win rate",       f"{win_rate:.1f}%")
            st.metric("Max drawdown",   f"{max_dd:.2f}%",         delta_color="inverse")
            st.metric("Sharpe ratio",   f"{sharpe:.3f}")
            st.metric("Total trades",   str(trades))
            st.metric("Profit factor",  f"{pf:.2f}")

    st.markdown("---")
    st.subheader("What these metrics mean")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Total Return** — Did the bot make or lose money on the test period?
        Target: > 10%

        **Win Rate** — What % of trades were profitable?
        Target: > 52% (anything above 50% beats a coin flip)

        **Max Drawdown** — Worst peak-to-trough loss during the test period.
        Target: < 25%
        """)
    with col2:
        st.markdown("""
        **Sharpe Ratio** — Risk-adjusted return. Higher is better.
        Target: > 0.8

        **Profit Factor** — Total profit ÷ total loss.
        Target: > 1.2 (meaning every Rs 1 lost, we made Rs 1.20+)

        **Total Trades** — How many trades were executed.
        Too few = model is too conservative.
        """)


# ── page: portfolio ───────────────────────────────────────────────────────────

def page_portfolio(capital: float):
    st.title("💼 Paper Trading Portfolio")
    st.caption("Simulated portfolio — tracks performance as if you had acted on every signal.")

    history = load_signal_history_local()

    if history.empty:
        st.info("No signals logged yet. Portfolio tracker activates after first signals.")
        return

    # Simulate paper trades from history
    buy_signals  = history[history["signal"] == "BUY"]
    sell_signals = history[history["signal"] == "SELL"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Starting capital", f"₹{capital:,.0f}")
    c2.metric("BUY signals received", len(buy_signals))
    c3.metric("SELL signals received", len(sell_signals))
    c4.metric("Total signals", len(history))

    st.markdown("---")
    st.subheader("Signal log")

    if "signal" in history.columns:
        # Show signal breakdown pie
        sig_counts = history["signal"].value_counts()
        fig = px.pie(
            values=sig_counts.values,
            names=sig_counts.index,
            color=sig_counts.index,
            color_discrete_map={
                "BUY": "#16a34a",
                "SELL": "#dc2626",
                "HOLD": "#d97706",
            },
            hole=0.4,
            title="Signal distribution",
        )
        fig.update_layout(height=300, margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("All logged signals")
    st.dataframe(history.tail(50), use_container_width=True, hide_index=True)


# ── main app ──────────────────────────────────────────────────────────────────

def main():
    page, capital, risk_level, selected_coins = render_sidebar()

    if page == "📊 Live Signals":
        page_live_signals(capital, selected_coins)

    elif page == "📈 Charts":
        page_charts(selected_coins)

    elif page == "📋 History":
        page_history()

    elif page == "🔬 Backtest":
        page_backtest()

    elif page == "💼 Portfolio":
        page_portfolio(capital)

    # Auto-refresh every 60 seconds on the signals page
    if page == "📊 Live Signals":
        time.sleep(0.5)
        st.caption("⏱️ Dashboard auto-refreshes every 60 seconds on next run.")


if __name__ == "__main__":
    main()