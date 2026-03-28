"""
main.py  (FINAL v3)
=====================
Starts everything together:
  - FastAPI server (port 8000)
  - Hourly signal scheduler
  - Telegram bot command handler (/start /status /help /signal)

HOW TO RUN:
    python main.py

    Then in a SEPARATE terminal:
    streamlit run app/main.py
"""

import os
import sys
import logging
import threading

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_TEST_CHAT_ID", "")


# ── Telegram bot command handler ──────────────────────────────────────────────

def run_telegram_bot():
    """
    Long-polling Telegram bot handler.
    Handles: /start  /help  /status  /signal BTC  /signal ETH etc.
    Runs in a background thread — does not block the scheduler.
    """
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_telegram_bot_token_here":
        log.warning("  Telegram token not set — bot commands disabled.")
        return

    try:
        import time
        import json
        import requests as req

        BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

        def send(chat_id, text):
            try:
                req.post(f"{BASE}/sendMessage",
                         data={"chat_id": chat_id, "text": text},
                         timeout=10)
            except Exception as e:
                log.error(f"  Telegram send error: {e}")

        def get_updates(offset=None):
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset
            try:
                r = req.get(f"{BASE}/getUpdates", params=params, timeout=35)
                return r.json().get("result", [])
            except Exception:
                return []

        log.info("  Telegram bot polling started — commands are live!")

        # Send startup message to owner
        if TELEGRAM_CHAT_ID and TELEGRAM_CHAT_ID != "your_chat_id_here":
            send(TELEGRAM_CHAT_ID,
                "AlgoBot Pro is now ONLINE!\n\n"
                "Commands:\n"
                "/start   - welcome\n"
                "/status  - latest signals\n"
                "/signal BTC - get BTC signal now\n"
                "/signal ETH - get ETH signal now\n"
                "/signal BNB - get BNB signal now\n"
                "/signal SOL - get SOL signal now\n"
                "/help    - all commands\n\n"
                "Signals fire automatically every hour."
            )

        offset = None
        while True:
            try:
                updates = get_updates(offset)
                for update in updates:
                    offset  = update["update_id"] + 1
                    msg     = update.get("message", {})
                    chat    = msg.get("chat", {})
                    chat_id = str(chat.get("id", ""))
                    text    = msg.get("text", "").strip()
                    name    = chat.get("first_name", "Trader")

                    if not text or not chat_id:
                        continue

                    cmd = text.lower().split()[0]
                    log.info(f"  Telegram cmd: '{text}' from {name} ({chat_id})")

                    # ── /start ────────────────────────────────────────────
                    if cmd == "/start":
                        send(chat_id,
                            f"Welcome to AlgoBot Pro, {name}!\n\n"
                            "I generate ML-powered trading signals for:\n"
                            "  BTC / ETH / BNB / SOL\n\n"
                            "Every signal includes:\n"
                            "  Entry price zone\n"
                            "  Target price (+6%)\n"
                            "  Stop loss (-3%)\n"
                            "  Position size in Rs\n"
                            "  Plain-English reasons\n\n"
                            "Signals fire every hour automatically.\n\n"
                            "Try: /signal BTC"
                        )

                    # ── /help ─────────────────────────────────────────────
                    elif cmd == "/help":
                        send(chat_id,
                            "AlgoBot Pro - All Commands:\n\n"
                            "/start       - welcome message\n"
                            "/status      - latest signal for all coins\n"
                            "/signal BTC  - instant BTC signal\n"
                            "/signal ETH  - instant ETH signal\n"
                            "/signal BNB  - instant BNB signal\n"
                            "/signal SOL  - instant SOL signal\n"
                            "/help        - this message\n\n"
                            "Signals also fire every hour automatically."
                        )

                    # ── /status ───────────────────────────────────────────
                    elif cmd == "/status":
                        try:
                            log_path = os.path.join("data", "signal_log.json")
                            if os.path.exists(log_path):
                                with open(log_path) as f:
                                    signals = json.load(f)

                                latest = {}
                                for s in signals:
                                    coin = s.get("coin", "")
                                    if coin:
                                        latest[coin] = s

                                if latest:
                                    reply = "Latest signals:\n\n"
                                    emj = {"BUY": "BUY", "SELL": "SELL", "HOLD": "HOLD"}
                                    for coin, s in latest.items():
                                        sig  = s.get("signal", "?")
                                        conf = s.get("confidence", 0)
                                        px   = s.get("price", 0)
                                        ts   = s.get("timestamp", "")[:16]
                                        reply += (
                                            f"{coin.replace('_','/')}: "
                                            f"{sig} ({conf:.0%}) "
                                            f"@ {px:,.2f}\n"
                                            f"  at {ts} UTC\n\n"
                                        )
                                    send(chat_id, reply)
                                else:
                                    send(chat_id, "No signals yet. Wait for next hourly run.")
                            else:
                                send(chat_id, "No signals logged yet. The bot runs every hour.")
                        except Exception as e:
                            send(chat_id, f"Error: {e}")

                    # ── /signal <COIN> ────────────────────────────────────
                    elif cmd == "/signal":
                        parts      = text.split()
                        coin_input = parts[1].upper() if len(parts) > 1 else "BTC"
                        coin_name  = f"{coin_input}_USD"
                        valid_coins = ["BTC_USD", "ETH_USD", "BNB_USD", "SOL_USD"]

                        if coin_name not in valid_coins:
                            send(chat_id,
                                f"Unknown coin: {coin_input}\n"
                                f"Available: BTC  ETH  BNB  SOL\n"
                                f"Example: /signal BTC"
                            )
                            continue

                        send(chat_id, f"Generating {coin_input}/USD signal... please wait")

                        try:
                            from src.signals.generator import generate_signal
                            from src.signals.formatter import format_signal
                            raw       = generate_signal(coin_name)
                            formatted = format_signal(raw, user_capital=50000.0)
                            send(chat_id, formatted["telegram_message"])
                        except Exception as e:
                            send(chat_id, f"Signal generation failed: {e}")

                    # ── unknown ───────────────────────────────────────────
                    elif text.startswith("/"):
                        send(chat_id,
                            f"Unknown command: {text}\n"
                            f"Send /help to see all commands."
                        )

            except Exception as e:
                log.error(f"  Telegram loop error: {e}")
                time.sleep(5)

    except ImportError:
        log.error("requests not installed. Run: pip install requests")
    except Exception as e:
        log.error(f"Telegram bot startup failed: {e}")


# ── FastAPI server ────────────────────────────────────────────────────────────

def run_api():
    try:
        import uvicorn
        from src.delivery.api import app
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    except Exception as e:
        log.error(f"API server error: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 55)
    log.info("  AlgoBot Pro — Starting up")
    log.info("=" * 55)

    # Check models exist
    models_dir = "models"
    model_files = [f for f in os.listdir(models_dir) if f.endswith(".pkl")] \
        if os.path.exists(models_dir) else []

    if not model_files:
        log.error(
            "\nNo trained models found in models/\n"
            "Run the full pipeline first:\n"
            "  python pipeline.py\n"
        )
        sys.exit(1)

    log.info(f"  Models       : {len(model_files)} files in models/")

    # Start FastAPI in background thread
    api_thread = threading.Thread(target=run_api, daemon=True, name="api-server")
    api_thread.start()
    log.info("  FastAPI      : http://localhost:8000")
    log.info("  API docs     : http://localhost:8000/docs")
    log.info("  Dashboard    : streamlit run app/main.py")

    # Start Telegram bot in background thread
    tg_thread = threading.Thread(
        target=run_telegram_bot, daemon=True, name="telegram-bot"
    )
    tg_thread.start()

    if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "your_telegram_bot_token_here":
        log.info("  Telegram bot : ACTIVE - /start /status /signal /help")
    else:
        log.info("  Telegram bot : NOT configured (add token to .env)")

    log.info("=" * 55 + "\n")

    # Start scheduler in main thread (blocking)
    from src.scheduler.runner import start_scheduler
    start_scheduler()