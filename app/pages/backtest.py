"""
app/pages/backtest.py
=======================
Backtest performance page — shows model performance on historical test data.
"""

import os
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import COINS, COIN_DISPLAY, MODELS_DIR, LABELS_DIR


def _load_backtest(coin: str) -> dict:
    path = os.path.join(MODELS_DIR, f"backtest_{coin}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _load_trade_log(coin: str) -> pd.DataFrame:
    path = os.path.join(MODELS_DIR, f"trade_log_{coin}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def _metric_card(label: str, value: str, good: bool = True, delta: str = None):
    color = "#16a34a" if good else "#dc2626"
    st.markdown(
        f"""<div style="background:#f8f9fa;border-radius:8px;padding:12px 16px;
                        border-left:4px solid {color};margin-bottom:8px;">
            <div style="font-size:12px;color:#666;">{label}</div>
            <div style="font-size:22px;font-weight:600;color:{color};">{value}</div>
            {f'<div style="font-size:11px;color:#999;">{delta}</div>' if delta else ''}
        </div>""",
        unsafe_allow_html=True,
    )


def render():
    st.title("🔬 Backtest Performance")
    st.caption(
        "Walk-forward simulation on the 20% test set the model never saw during training. "
        "Results show how the model would have performed on real historical data."
    )

    # Deployment thresholds explanation
    with st.expander("What do these metrics mean?"):
        st.markdown("""
        | Metric | Target | Meaning |
        |---|---|---|
        | **Total Return** | > 10% | Did the bot make money on the test period? |
        | **Win Rate** | > 52% | What % of trades were profitable? (50% = coin flip) |
        | **Max Drawdown** | > -25% | Worst peak-to-trough loss (lower is worse) |
        | **Sharpe Ratio** | > 0.8 | Risk-adjusted return (higher is better) |
        | **Profit Factor** | > 1.2 | Total profit ÷ total loss |
        """)

    # ── Per-coin metrics ──────────────────────────────────────────────────────
    cols = st.columns(len(COINS))

    for i, coin in enumerate(COINS.values()):
        data = _load_backtest(coin)
        with cols[i]:
            st.subheader(COIN_DISPLAY.get(coin, coin))

            if not data:
                st.warning("No backtest data.\nRun pipeline.py first.")
                continue

            ret    = data.get("total_return_pct", 0)
            win    = data.get("win_rate_pct", 0)
            dd     = data.get("max_drawdown_pct", 0)
            sharpe = data.get("sharpe_ratio", 0)
            pf     = data.get("profit_factor", 0)
            trades = data.get("total_trades", 0)
            final  = data.get("final_capital", 0)

            _metric_card("Total return",  f"{ret:+.2f}%",  good=(ret > 0))
            _metric_card("Win rate",      f"{win:.1f}%",   good=(win >= 52))
            _metric_card("Max drawdown",  f"{dd:.2f}%",    good=(dd > -25))
            _metric_card("Sharpe ratio",  f"{sharpe:.3f}", good=(sharpe >= 0.8))
            _metric_card("Profit factor", f"{pf:.2f}",     good=(pf >= 1.2))
            _metric_card("Total trades",  str(trades),     good=True)

            if final:
                st.caption(f"₹1,00,000 → ₹{final:,.0f}")

    # ── Trade log chart ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Trade-by-trade P&L")

    coin_choice = st.selectbox(
        "Select coin",
        list(COINS.values()),
        format_func=lambda c: COIN_DISPLAY.get(c, c),
    )

    trade_log = _load_trade_log(coin_choice)

    if trade_log.empty:
        st.info("No trade log available. Run backtest.py to generate it.")
        return

    if "net_pnl" in trade_log.columns:
        trade_log["cumulative_pnl"] = trade_log["net_pnl"].cumsum()
        trade_log["trade_num"]      = range(1, len(trade_log) + 1)

        # Cumulative P&L chart
        colors = ["#16a34a" if p > 0 else "#dc2626"
                  for p in trade_log["net_pnl"]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=trade_log["trade_num"],
            y=trade_log["net_pnl"],
            name="Trade P&L",
            marker_color=colors,
            opacity=0.7,
        ))
        fig.add_trace(go.Scatter(
            x=trade_log["trade_num"],
            y=trade_log["cumulative_pnl"],
            name="Cumulative P&L",
            line=dict(color="#2563EB", width=2),
            yaxis="y2",
        ))
        fig.update_layout(
            title=f"{COIN_DISPLAY.get(coin_choice, coin_choice)} — Trade P&L",
            xaxis_title="Trade #",
            yaxis_title="Trade P&L (Rs)",
            yaxis2=dict(title="Cumulative P&L (Rs)", overlaying="y", side="right"),
            height=380,
            plot_bgcolor="white",
            paper_bgcolor="white",
            hovermode="x unified",
            legend=dict(orientation="h", y=1.02),
            margin=dict(l=0, r=0, t=40, b=0),
        )
        fig.add_hline(y=0, line_color="gray", line_width=0.8, line_dash="dash")
        st.plotly_chart(fig, use_container_width=True)

        # Summary stats
        wins   = (trade_log["net_pnl"] > 0).sum()
        losses = (trade_log["net_pnl"] <= 0).sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Winning trades",  str(wins))
        c2.metric("Losing trades",   str(losses))
        c3.metric("Avg win  (Rs)",   f"₹{trade_log.loc[trade_log['net_pnl']>0,'net_pnl'].mean():,.0f}" if wins else "N/A")
        c4.metric("Avg loss (Rs)",   f"₹{trade_log.loc[trade_log['net_pnl']<=0,'net_pnl'].mean():,.0f}" if losses else "N/A")