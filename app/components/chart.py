"""
app/components/chart.py
=========================
Reusable chart components for the Streamlit dashboard.
All charts use Plotly for interactivity.

Import and call these from any page:
    from app.components.chart import candlestick_chart, rsi_chart, macd_chart
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def candlestick_chart(df: pd.DataFrame, coin_name: str = "", n_candles: int = 200):
    """
    Interactive candlestick chart with EMA overlays and Bollinger Bands.

    Args:
        df:         Feature DataFrame with datetime, open, high, low, close,
                    ema_9, ema_21, ema_50, bb_upper, bb_lower
        coin_name:  Display name (e.g. 'BTC/USD')
        n_candles:  How many candles to show
    """
    df = df.tail(n_candles)
    fig = go.Figure()

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df["datetime"],
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        name="Price",
        increasing_line_color="#16a34a",
        decreasing_line_color="#dc2626",
        increasing_fillcolor="#16a34a",
        decreasing_fillcolor="#dc2626",
    ))

    # EMA lines
    ema_styles = [
        ("ema_9",  "EMA 9",  "#3b82f6", 1),
        ("ema_21", "EMA 21", "#f59e0b", 1),
        ("ema_50", "EMA 50", "#8b5cf6", 1.5),
    ]
    for col, name, color, width in ema_styles:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["datetime"], y=df[col],
                name=name, line=dict(color=color, width=width),
                opacity=0.8,
            ))

    # Bollinger Bands
    if "bb_upper" in df.columns and "bb_lower" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["bb_upper"],
            name="BB Upper", line=dict(color="gray", width=1, dash="dot"),
            opacity=0.5,
        ))
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["bb_lower"],
            name="BB Lower", line=dict(color="gray", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(128,128,128,0.04)",
            opacity=0.5,
        ))

    fig.update_layout(
        title=f"{coin_name} — Price Chart",
        height=420,
        xaxis_rangeslider_visible=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", y=1.02, font=dict(size=11)),
        margin=dict(l=0, r=0, t=40, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def rsi_chart(df: pd.DataFrame, n_candles: int = 200):
    """
    RSI indicator chart with overbought/oversold lines.

    Args:
        df:        Feature DataFrame with datetime and rsi columns
        n_candles: How many candles to show
    """
    if "rsi" not in df.columns:
        st.warning("RSI column not found in data.")
        return

    df = df.tail(n_candles)
    fig = go.Figure()

    # RSI line with colour fill
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=df["rsi"],
        name="RSI", line=dict(color="#3b82f6", width=2),
        fill="tonexty", fillcolor="rgba(59,130,246,0.07)",
    ))

    # Overbought / oversold bands
    fig.add_hrect(y0=70, y1=100, fillcolor="#dc2626",
                  opacity=0.05, line_width=0)
    fig.add_hrect(y0=0,  y1=30,  fillcolor="#16a34a",
                  opacity=0.05, line_width=0)
    fig.add_hline(y=70, line_dash="dash", line_color="#dc2626", line_width=1,
                  annotation_text="Overbought", annotation_position="right")
    fig.add_hline(y=30, line_dash="dash", line_color="#16a34a", line_width=1,
                  annotation_text="Oversold", annotation_position="right")
    fig.add_hline(y=50, line_color="gray", line_width=0.5)

    fig.update_layout(
        title="RSI (14)",
        height=200, yaxis_range=[0, 100],
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=0, r=0, t=30, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def macd_chart(df: pd.DataFrame, n_candles: int = 200):
    """
    MACD chart with signal line and histogram.

    Args:
        df:        Feature DataFrame with macd_line, macd_signal, macd_histogram
        n_candles: How many candles to show
    """
    required = ["macd_line", "macd_signal", "macd_histogram"]
    if not all(c in df.columns for c in required):
        st.warning("MACD columns not found in data.")
        return

    df = df.tail(n_candles)
    fig = go.Figure()

    # Histogram bars (green positive, red negative)
    colors = ["#16a34a" if v >= 0 else "#dc2626"
              for v in df["macd_histogram"]]
    fig.add_trace(go.Bar(
        x=df["datetime"], y=df["macd_histogram"],
        name="Histogram", marker_color=colors, opacity=0.6,
    ))

    # MACD and signal lines
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=df["macd_line"],
        name="MACD", line=dict(color="#3b82f6", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=df["macd_signal"],
        name="Signal", line=dict(color="#f59e0b", width=1.5),
    ))
    fig.add_hline(y=0, line_color="gray", line_width=0.5)

    fig.update_layout(
        title="MACD",
        height=200,
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", y=1.1, font=dict(size=11)),
        margin=dict(l=0, r=0, t=30, b=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def volume_chart(df: pd.DataFrame, n_candles: int = 200):
    """
    Volume bar chart coloured by candle direction.

    Args:
        df:        Feature DataFrame with datetime, open, close, volume
        n_candles: How many candles to show
    """
    if "volume" not in df.columns:
        return

    df     = df.tail(n_candles)
    colors = [
        "#16a34a" if df["close"].iloc[i] >= df["open"].iloc[i] else "#dc2626"
        for i in range(len(df))
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["datetime"], y=df["volume"],
        marker_color=colors, name="Volume", opacity=0.7,
    ))
    fig.update_layout(
        title="Volume",
        height=150,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=0, r=0, t=30, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def stochastic_chart(df: pd.DataFrame, n_candles: int = 200):
    """
    Stochastic oscillator (%K and %D lines).
    """
    if "stoch_k" not in df.columns:
        return

    df = df.tail(n_candles)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=df["stoch_k"],
        name="%K", line=dict(color="#3b82f6", width=1.5),
    ))
    if "stoch_d" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df["stoch_d"],
            name="%D", line=dict(color="#f59e0b", width=1.5),
        ))
    fig.add_hline(y=80, line_dash="dash", line_color="#dc2626", line_width=1)
    fig.add_hline(y=20, line_dash="dash", line_color="#16a34a", line_width=1)

    fig.update_layout(
        title="Stochastic Oscillator",
        height=180, yaxis_range=[0, 100],
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", y=1.1, font=dict(size=11)),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)