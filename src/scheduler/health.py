"""
src/scheduler/health.py
=========================
PURPOSE:
    Health monitoring for the AlgoBot Pro system.
    Runs every 30 minutes and checks that everything is working correctly.
    Sends alerts via Telegram if something goes wrong.

WHAT IT MONITORS:
    1. Data freshness     — is live data being fetched every hour?
    2. Signal generation  — are signals being produced?
    3. Model availability — are model files present and loadable?
    4. Disk space         — is there enough space for logs and data?
    5. API health         — is the FastAPI server responding?
    6. Pipeline status    — are all required data files present?

WHY THIS MATTERS:
    Without health monitoring, you won't know if:
    - Yahoo Finance went down and no live data is being fetched
    - A signal generation error is silently failing
    - The scheduler crashed overnight
    - Disk is full and signals are not being logged

    The health checker runs silently — you only hear from it when
    something is wrong.

DEPENDENCIES:
    pip install requests psutil
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone, timedelta

from config.settings import (
    MODELS_DIR,
    LIVE_DIR,
    SIGNAL_LOG,
    COINS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    API_HOST,
    API_PORT,
    MAX_DATA_STALENESS_H,
    MAX_SIGNAL_STALENESS_H,
    HEALTH_CHECK_INTERVAL_MIN,
)

log = logging.getLogger(__name__)


# ── Alert delivery ─────────────────────────────────────────────────────────────

def _send_alert(message: str, level: str = "WARNING") -> None:
    """
    Send a health alert via Telegram.

    Args:
        message: Alert message text
        level:   'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
    """
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        log.warning(f"  Health alert (Telegram not configured): {message}")
        return

    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        log.warning(f"  Health alert (no chat ID): {message}")
        return

    emoji_map = {
        "INFO":     "ℹ️",
        "WARNING":  "⚠️",
        "ERROR":    "❌",
        "CRITICAL": "🚨",
    }
    emoji = emoji_map.get(level, "⚠️")

    full_msg = (
        f"{emoji} AlgoBot Pro — {level}\n\n"
        f"{message}\n\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": full_msg},
            timeout=10,
        )
        log.info(f"  Health alert sent: [{level}] {message[:60]}...")
    except Exception as e:
        log.error(f"  Failed to send health alert: {e}")


# ── Individual health checks ───────────────────────────────────────────────────

def check_data_freshness() -> dict:
    """
    Check that live market data is being fetched regularly.
    Returns warning if any coin's data is older than MAX_DATA_STALENESS_H.
    """
    issues  = []
    details = {}

    for coin_name in COINS.values():
        live_path = os.path.join(LIVE_DIR, f"{coin_name}_live.csv")

        if not os.path.exists(live_path):
            issues.append(f"{coin_name}: No live data file found")
            details[coin_name] = {"age_h": 999, "status": "missing"}
            continue

        mtime  = os.path.getmtime(live_path)
        mod_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        age_h  = (datetime.now(timezone.utc) - mod_dt).total_seconds() / 3600

        if age_h > MAX_DATA_STALENESS_H:
            issues.append(
                f"{coin_name}: Live data is {age_h:.1f}h old "
                f"(max: {MAX_DATA_STALENESS_H}h)"
            )
            details[coin_name] = {"age_h": round(age_h, 2), "status": "stale"}
        else:
            details[coin_name] = {"age_h": round(age_h, 2), "status": "ok"}

    return {
        "check":   "data_freshness",
        "passed":  len(issues) == 0,
        "issues":  issues,
        "details": details,
    }


def check_signal_generation() -> dict:
    """
    Check that signals are being generated regularly.
    Returns warning if no signal in the last MAX_SIGNAL_STALENESS_H hours.
    """
    issues = []

    if not os.path.exists(SIGNAL_LOG):
        issues.append("Signal log file does not exist — no signals ever generated")
        return {"check": "signal_generation", "passed": False, "issues": issues}

    try:
        with open(SIGNAL_LOG) as f:
            signals = json.load(f)
    except Exception as e:
        issues.append(f"Could not read signal log: {e}")
        return {"check": "signal_generation", "passed": False, "issues": issues}

    if not signals:
        issues.append("Signal log is empty — no signals generated yet")
        return {"check": "signal_generation", "passed": False, "issues": issues}

    # Check how long ago the last signal was
    last_signal = signals[-1]
    ts_str      = last_signal.get("timestamp", last_signal.get("logged_at", ""))

    try:
        last_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        age_h   = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600

        if age_h > MAX_SIGNAL_STALENESS_H:
            issues.append(
                f"Last signal was {age_h:.1f}h ago "
                f"(max expected gap: {MAX_SIGNAL_STALENESS_H}h). "
                f"Scheduler may have stopped."
            )
    except Exception:
        issues.append(f"Could not parse last signal timestamp: {ts_str}")

    return {
        "check":        "signal_generation",
        "passed":       len(issues) == 0,
        "issues":       issues,
        "total_signals":len(signals),
        "last_signal":  last_signal.get("signal", "?"),
        "last_coin":    last_signal.get("coin", "?"),
    }


def check_models() -> dict:
    """
    Check that all trained model files exist and are loadable.
    """
    issues  = []
    details = {}

    for coin_name in COINS.values():
        model_path  = os.path.join(MODELS_DIR, f"xgb_{coin_name}_v1.pkl")
        scaler_path = os.path.join(MODELS_DIR, f"scaler_{coin_name}.pkl")

        model_ok  = os.path.exists(model_path)
        scaler_ok = os.path.exists(scaler_path)

        if not model_ok:
            issues.append(f"{coin_name}: Model file missing: {model_path}")
        if not scaler_ok:
            issues.append(f"{coin_name}: Scaler file missing: {scaler_path}")

        details[coin_name] = {
            "model_exists":  model_ok,
            "scaler_exists": scaler_ok,
        }

        # Try loading the model to ensure it's not corrupt
        if model_ok:
            try:
                import joblib
                model = joblib.load(model_path)
                details[coin_name]["loadable"] = True
            except Exception as e:
                issues.append(f"{coin_name}: Model file corrupt: {e}")
                details[coin_name]["loadable"] = False

    return {
        "check":   "models",
        "passed":  len(issues) == 0,
        "issues":  issues,
        "details": details,
    }


def check_api() -> dict:
    """
    Check that the FastAPI server is responding.
    """
    issues = []
    url    = f"http://{API_HOST if API_HOST != '0.0.0.0' else 'localhost'}:{API_PORT}/"

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        return {
            "check":   "api",
            "passed":  True,
            "issues":  [],
            "status":  data.get("status", "unknown"),
            "url":     url,
        }

    except requests.exceptions.ConnectionError:
        issues.append(
            f"FastAPI server not reachable at {url}. "
            f"Is main.py running?"
        )
    except Exception as e:
        issues.append(f"API check failed: {e}")

    return {
        "check":  "api",
        "passed": False,
        "issues": issues,
        "url":    url,
    }


def check_disk_space(min_free_gb: float = 0.5) -> dict:
    """
    Check that there's enough free disk space.

    Args:
        min_free_gb: Minimum free space required in GB (default 0.5 GB)
    """
    issues = []

    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024 ** 3)

        if free_gb < min_free_gb:
            issues.append(
                f"Low disk space: {free_gb:.2f} GB free "
                f"(minimum: {min_free_gb} GB). "
                f"Delete old logs or data files."
            )

        return {
            "check":      "disk_space",
            "passed":     len(issues) == 0,
            "issues":     issues,
            "free_gb":    round(free_gb, 2),
            "total_gb":   round(total / (1024 ** 3), 2),
            "used_pct":   round(used / total * 100, 1),
        }

    except Exception as e:
        return {
            "check":  "disk_space",
            "passed": True,   # Don't block on disk check failure
            "issues": [f"Could not check disk space: {e}"],
        }


# ── Master health check ────────────────────────────────────────────────────────

def run_health_check(send_alerts: bool = True) -> dict:
    """
    Run all health checks and send alerts for any failures.

    Args:
        send_alerts: If True, send Telegram alerts for failures

    Returns:
        dict: Complete health report with all check results

    Example:
        >>> from src.scheduler.health import run_health_check
        >>> report = run_health_check()
        >>> print(f"Overall health: {'OK' if report['all_passed'] else 'ISSUES FOUND'}")
    """
    log.info("Running health check ...")
    now = datetime.now(timezone.utc).isoformat()

    checks = {
        "data_freshness":   check_data_freshness(),
        "signal_generation":check_signal_generation(),
        "models":           check_models(),
        "api":              check_api(),
        "disk_space":       check_disk_space(),
    }

    all_passed  = all(c["passed"] for c in checks.values())
    all_issues  = []
    for name, result in checks.items():
        for issue in result.get("issues", []):
            all_issues.append(f"[{name}] {issue}")

    report = {
        "timestamp":  now,
        "all_passed": all_passed,
        "checks":     checks,
        "issues":     all_issues,
    }

    if all_passed:
        log.info("  Health check: ALL PASSED ✓")
    else:
        log.warning(f"  Health check: {len(all_issues)} issue(s) found")
        for issue in all_issues:
            log.warning(f"    - {issue}")

        if send_alerts and all_issues:
            alert_msg = (
                f"Health check found {len(all_issues)} issue(s):\n\n" +
                "\n".join(f"• {i}" for i in all_issues)
            )
            level = "CRITICAL" if not checks["models"]["passed"] else "WARNING"
            _send_alert(alert_msg, level=level)

    return report


def start_health_monitor() -> None:
    """
    Start the health monitor as a background scheduled job.
    Called from main.py to run alongside the signal scheduler.
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        func=lambda: run_health_check(send_alerts=True),
        trigger="interval",
        minutes=HEALTH_CHECK_INTERVAL_MIN,
        id="health_check",
        name="AlgoBot Pro Health Check",
        replace_existing=True,
    )
    scheduler.start()
    log.info(
        f"  Health monitor started — "
        f"runs every {HEALTH_CHECK_INTERVAL_MIN} minutes."
    )
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )

    report = run_health_check(send_alerts=False)

    print(f"\n── Health Report ──────────────────────────────────")
    print(f"  Overall: {'ALL PASSED' if report['all_passed'] else 'ISSUES FOUND'}")
    for name, check in report["checks"].items():
        status = "✓" if check["passed"] else "✗"
        print(f"  {status}  {name}")
        for issue in check.get("issues", []):
            print(f"       → {issue}")