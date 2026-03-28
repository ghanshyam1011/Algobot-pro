"""
app/pages/settings.py
=======================
Settings page — shows system status, pipeline health, and configuration.
"""

import os
import json
import streamlit as st
import requests
from datetime import datetime, timezone

from config.settings import (
    COINS, COIN_DISPLAY, MODELS_DIR, LABELS_DIR,
    RAW_DIR, PROCESSED_DIR, LIVE_DIR,
    API_PORT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    EMAIL_SENDER, MODEL_VERSION,
)

API_BASE = f"http://localhost:{API_PORT}"


def _fetch(endpoint):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=5)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def _file_age_str(path: str) -> str:
    if not os.path.exists(path):
        return "missing"
    mtime  = os.path.getmtime(path)
    dt     = datetime.fromtimestamp(mtime, tz=timezone.utc)
    age_h  = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    if age_h < 1:
        return f"{int(age_h*60)}m ago"
    elif age_h < 24:
        return f"{age_h:.1f}h ago"
    else:
        return f"{age_h/24:.1f}d ago"


def _tick(ok: bool) -> str:
    return "✅" if ok else "❌"


def render():
    st.title("⚙️ Settings & System Status")

    # ── API status ────────────────────────────────────────────────────────────
    st.subheader("API Status")
    api_data = _fetch("/")
    if api_data:
        st.success(f"✅ FastAPI running — {api_data.get('service', 'AlgoBot Pro')} v{api_data.get('version','?')}")
    else:
        st.error("❌ FastAPI not responding. Is `python main.py` running?")

    # ── Pipeline status ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Pipeline File Status")

    status_data = _fetch("/status").get("coins", {})

    rows = []
    for coin in COINS.values():
        raw_ok     = os.path.exists(os.path.join(RAW_DIR,       f"{coin}_raw.csv"))
        proc_ok    = os.path.exists(os.path.join(PROCESSED_DIR, f"{coin}_processed.csv"))
        feat_ok    = os.path.exists(os.path.join(PROCESSED_DIR, f"{coin}_features.csv"))
        label_ok   = os.path.exists(os.path.join(LABELS_DIR,    f"{coin}_labeled.csv"))
        model_ok   = os.path.exists(os.path.join(MODELS_DIR,    f"xgb_{coin}_v1.pkl"))
        live_age   = _file_age_str(os.path.join(LIVE_DIR,       f"{coin}_live.csv"))

        rows.append({
            "Coin":    COIN_DISPLAY.get(coin, coin),
            "Raw":     _tick(raw_ok),
            "Processed": _tick(proc_ok),
            "Features":  _tick(feat_ok),
            "Labeled":   _tick(label_ok),
            "Model":     _tick(model_ok),
            "Live data": live_age,
        })

    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not all(
        os.path.exists(os.path.join(MODELS_DIR, f"xgb_{c}_v1.pkl"))
        for c in COINS.values()
    ):
        st.warning(
            "Some models are missing. Run the full pipeline:\n```\npython pipeline.py\n```"
        )

    # ── Configuration ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Current Configuration")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Model settings**")
        st.json({
            "model_version":     MODEL_VERSION,
            "coins_tracked":     list(COINS.values()),
        })

    with col2:
        st.markdown("**Delivery settings**")
        st.json({
            "telegram_configured": bool(TELEGRAM_BOT_TOKEN and
                                        TELEGRAM_BOT_TOKEN != "your_telegram_bot_token_here"),
            "chat_id_configured":  bool(TELEGRAM_CHAT_ID and
                                        TELEGRAM_CHAT_ID != "your_chat_id_here"),
            "email_configured":    bool(EMAIL_SENDER),
        })

    # ── Model files ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Model Files")

    model_files = [
        f for f in os.listdir(MODELS_DIR)
        if f.endswith(".pkl") or f.endswith(".json")
    ] if os.path.exists(MODELS_DIR) else []

    if model_files:
        for mf in sorted(model_files):
            path = os.path.join(MODELS_DIR, mf)
            size = os.path.getsize(path) / 1024
            age  = _file_age_str(path)
            st.text(f"  {mf:<45} {size:>8.1f} KB   {age}")
    else:
        st.info("No model files found. Run `python pipeline.py` to train models.")

    # ── Quick actions ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Quick Actions")
    st.markdown("""
    ```bash
    # Retrain all models (run in terminal)
    python pipeline.py --from train

    # Run health check
    python src/scheduler/health.py

    # Generate a signal right now (without waiting for scheduler)
    python -c "from src.scheduler.runner import run_signal_pipeline; run_signal_pipeline()"

    # View model registry
    python src/models/registry.py

    # Run all tests
    pytest tests/ -v
    ```
    """)