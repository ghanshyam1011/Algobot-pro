"""
src/scheduler/runner.py  (FINAL v2)
=====================================
Master orchestrator — runs every hour automatically.

CHANGES in v2:
    - Signals are now stored via api.store_signal() for dashboard display
    - Signal log is persisted to data/signal_log.json
    - Telegram delivery properly wired with .env token
    - Better error handling and summary logging

HOW TO START:
    python main.py          (starts API + scheduler together)
    OR
    python src/scheduler/runner.py   (scheduler only, no API)

DEPENDENCIES:
    pip install apscheduler python-dotenv yfinance
"""

import os
import json
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()
log = logging.getLogger(__name__)

ACTIVE_COINS   = ["BTC_USD", "ETH_USD", "BNB_USD", "SOL_USD"]
SIGNAL_LOG     = os.path.join("data", "signal_log.json")
MODEL_VERSION  = os.getenv("MODEL_VERSION", "v1")

# ── Risk level → minimum confidence to send ───────────────────────────────────
RISK_THRESHOLDS = {
    "low":    0.85,
    "medium": 0.75,
    "high":   0.65,
}

# ── Subscriber list — edit this or load from database ─────────────────────────
# Replace YOUR_CHAT_ID_HERE with your actual Telegram chat ID
# Get your chat ID by messaging @userinfobot on Telegram
SUBSCRIBERS = [
    {
        "chat_id":    os.getenv("TELEGRAM_TEST_CHAT_ID", "YOUR_CHAT_ID_HERE"),
        "coins":      ["BTC_USD", "ETH_USD", "BNB_USD", "SOL_USD"],
        "risk_level": "medium",
        "capital":    50000.0,
    },
]


def _save_signal(signal: dict) -> None:
    """Persist signal to JSON log file and to API cache."""
    os.makedirs(os.path.dirname(SIGNAL_LOG), exist_ok=True)

    # Load existing log
    log_data = []
    if os.path.exists(SIGNAL_LOG):
        try:
            with open(SIGNAL_LOG) as f:
                log_data = json.load(f)
        except Exception:
            log_data = []

    log_data.append(signal)
    log_data = log_data[-1000:]   # Keep last 1000

    with open(SIGNAL_LOG, "w") as f:
        json.dump(log_data, f, indent=2, default=str)

    # Push to API cache if available
    try:
        from src.delivery.api import store_signal
        store_signal(signal)
    except Exception:
        pass   # API may not be running in standalone mode


def _send_telegram(chat_id: str, message: str) -> bool:
    """Send a message to Telegram. Returns True if successful."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or token == "your_telegram_bot_token_here":
        log.warning("  Telegram not configured. Add TELEGRAM_BOT_TOKEN to .env")
        return False

    try:
        import requests
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.error(f"  Telegram send failed: {e}")
        return False


def _should_send(signal: str, confidence: float, risk_level: str) -> bool:
    """Return True if this signal passes the risk threshold."""
    if signal == "HOLD":
        return False
    threshold = RISK_THRESHOLDS.get(risk_level.lower(), 0.75)
    return confidence >= threshold


def run_signal_pipeline() -> None:
    """
    The main hourly job.
    Fetch → engineer → predict → filter → format → deliver → log.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log.info(f"\n{'='*55}")
    log.info(f"AlgoBot Pro — Hourly Signal Run — {now}")
    log.info(f"{'='*55}")

    results = []

    for coin_name in ACTIVE_COINS:
        try:
            log.info(f"\nProcessing {coin_name} ...")

            # ── 1. Generate raw signal ────────────────────────────────────
            from src.signals.generator import generate_signal
            raw_signal = generate_signal(coin_name, model_version=MODEL_VERSION)

            signal     = raw_signal["signal"]
            confidence = raw_signal["confidence"]
            price      = raw_signal["price"]

            # ── 2. Format signal card ─────────────────────────────────────
            from src.signals.formatter import format_signal
            formatted = format_signal(raw_signal, user_capital=50000.0)

            # ── 3. Save to log (regardless of whether we send) ────────────
            _save_signal({
                **formatted,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "coin":      coin_name,
            })

            # ── 4. Filter and deliver per subscriber ─────────────────────
            sent_count = 0

            for user in SUBSCRIBERS:
                if coin_name not in user.get("coins", []):
                    continue

                risk_level = user.get("risk_level", "medium")

                if not _should_send(signal, confidence, risk_level):
                    log.info(
                        f"  {coin_name}: Skipped — "
                        f"{'HOLD signal' if signal=='HOLD' else f'Confidence {confidence:.1%} below {risk_level} threshold ({RISK_THRESHOLDS[risk_level]:.0%})'}"
                    )
                    continue

                # Reformat with user's capital
                user_formatted = format_signal(
                    raw_signal, user_capital=user.get("capital", 50000.0)
                )

                ok = _send_telegram(
                    user["chat_id"],
                    user_formatted["telegram_message"]
                )
                if ok:
                    sent_count += 1
                    log.info(
                        f"  {coin_name}: {signal} ({confidence:.0%}) "
                        f"sent to {user['chat_id']}"
                    )

            results.append({
                "coin":       coin_name,
                "signal":     signal,
                "confidence": confidence,
                "price":      price,
                "sent":       sent_count,
            })

        except Exception as e:
            log.error(f"  {coin_name}: FAILED — {e}", exc_info=False)
            results.append({"coin": coin_name, "error": str(e)})

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info(f"\n{'─'*45}")
    log.info("  Run summary:")
    for r in results:
        if "error" in r:
            log.error(f"  {r['coin']}: ERROR — {r['error']}")
        else:
            log.info(
                f"  {r['coin']}: {r['signal']} "
                f"({r['confidence']:.0%}) @ {r['price']:,.2f} "
                f"— sent to {r['sent']} subscriber(s)"
            )
    log.info(f"  Next run: in ~1 hour")
    log.info("=" * 55)


def start_scheduler() -> None:
    """Start APScheduler — fires run_signal_pipeline() every hour at :00."""
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        func=run_signal_pipeline,
        trigger=CronTrigger(minute=0),
        id="hourly_signal_run",
        name="AlgoBot Pro Hourly Signal Run",
        replace_existing=True,
    )

    log.info("AlgoBot Pro Scheduler started.")
    log.info("Signals generated every hour at :00 UTC.")
    log.info("Press Ctrl+C to stop.\n")

    # Run immediately on startup — don't wait for next hour
    log.info("Running initial signal check now ...")
    run_signal_pipeline()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    start_scheduler()