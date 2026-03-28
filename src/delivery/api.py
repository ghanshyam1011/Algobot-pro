"""
src/delivery/api.py
====================
FastAPI REST API — serves signal data to the Angular dashboard.

ENDPOINTS:
    GET  /              → health check
    GET  /signal/{coin} → latest signal for one coin
    GET  /signals/all   → latest signals for all coins
    GET  /history/{coin}→ last N signals from log
    GET  /backtest/{coin}→ backtest metrics
    GET  /status        → system status
"""

import os
import json
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger(__name__)

app = FastAPI(
    title="AlgoBot Pro API",
    description="Algorithmic Trading Signal Engine",
    version="1.0.0",
)

# ── CORS — allow Angular dev server + any local origin ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",   # Angular dev server
        "http://localhost:4201",   # Angular alt port
        "http://localhost:3000",   # Any React/Next fallback
        "http://127.0.0.1:4200",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODELS_DIR = "models"
LABELS_DIR = os.path.join("data", "labels")
SIGNAL_LOG = os.path.join("data", "signal_log.json")

COINS = ["BTC_USD", "ETH_USD", "BNB_USD", "SOL_USD"]


def _load_signal_log() -> list:
    if not os.path.exists(SIGNAL_LOG):
        return []
    try:
        with open(SIGNAL_LOG) as f:
            return json.load(f)
    except Exception:
        return []


def _save_signal_to_log(signal: dict) -> None:
    log_data = _load_signal_log()
    log_data.append(signal)
    log_data = log_data[-1000:]
    os.makedirs(os.path.dirname(SIGNAL_LOG), exist_ok=True)
    with open(SIGNAL_LOG, "w") as f:
        json.dump(log_data, f, indent=2, default=str)


_latest_signals: dict = {}


def store_signal(signal: dict) -> None:
    coin = signal.get("coin", "UNKNOWN")
    signal["cached_at"] = datetime.now(timezone.utc).isoformat()
    _latest_signals[coin] = signal
    _save_signal_to_log(signal)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status":    "running",
        "service":   "AlgoBot Pro",
        "version":   "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "coins":     COINS,
    }


@app.get("/signal/{coin}")
def get_latest_signal(coin: str):
    coin = coin.upper()
    if coin not in COINS:
        raise HTTPException(status_code=404, detail=f"Coin '{coin}' not found. Available: {COINS}")

    signal = _latest_signals.get(coin)
    if not signal:
        try:
            from src.signals.generator import generate_signal
            from src.signals.formatter import format_signal
            raw    = generate_signal(coin)
            signal = format_signal(raw, user_capital=50000.0)
            store_signal(signal)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Signal generation failed: {str(e)}")

    return signal


@app.get("/signals/all")
def get_all_signals():
    return {
        "signals":   _latest_signals,
        "count":     len(_latest_signals),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/history/{coin}")
def get_signal_history(coin: str, limit: int = 100):
    coin = coin.upper()
    if coin not in COINS:
        raise HTTPException(status_code=404, detail=f"Coin '{coin}' not found.")
    all_logs  = _load_signal_log()
    coin_logs = [s for s in all_logs if s.get("coin") == coin]
    return {
        "coin":    coin,
        "count":   len(coin_logs),
        "signals": coin_logs[-limit:],
    }


@app.get("/backtest/{coin}")
def get_backtest(coin: str):
    coin = coin.upper()
    path = os.path.join(MODELS_DIR, f"backtest_{coin}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"No backtest found for {coin}.")
    with open(path) as f:
        return json.load(f)


@app.get("/status")
def get_status():
    status = {}
    for coin in COINS:
        model_path = os.path.join(MODELS_DIR, f"xgb_{coin}_v1.pkl")
        label_path = os.path.join(LABELS_DIR, f"{coin}_labeled.csv")
        latest_sig = _latest_signals.get(coin, {})
        status[coin] = {
            "model_trained":   os.path.exists(model_path),
            "data_labeled":    os.path.exists(label_path),
            "last_signal":     latest_sig.get("signal", "none"),
            "last_confidence": latest_sig.get("confidence", 0),
            "last_price":      latest_sig.get("price", 0),
            "cached_at":       latest_sig.get("cached_at", "never"),
        }
    return {"system": "AlgoBot Pro", "coins": status}