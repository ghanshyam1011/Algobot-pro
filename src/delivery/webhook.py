"""
src/delivery/webhook.py
=========================
PURPOSE:
    Send signals to external services via HTTP webhooks.
    Allows AlgoBot Pro to integrate with any third-party system
    that accepts JSON payloads via HTTP POST.

USE CASES:
    - Send signals to your own custom app or website
    - Integrate with Zapier, Make (Integromat), or n8n
    - Post signals to Discord via Discord webhooks
    - Send to Slack channels
    - Trigger Zerodha/Upstox auto-trades via their webhook APIs
    - Log signals to external analytics tools (Mixpanel, Amplitude)

HOW WEBHOOKS WORK:
    1. You configure a URL in .env (WEBHOOK_URL)
    2. Every time a signal is generated, we POST a JSON payload to that URL
    3. The receiving server does whatever it wants with the data
    4. We log success or failure

DISCORD INTEGRATION (popular use case):
    1. Open Discord → Server Settings → Integrations → Webhooks
    2. Create New Webhook → Copy Webhook URL
    3. Add to .env:  WEBHOOK_URL=https://discord.com/api/webhooks/...
    4. That's it — signals will post to your Discord channel

DEPENDENCIES:
    pip install requests
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Webhook URLs from environment variables
WEBHOOK_URL          = os.getenv("WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL  = os.getenv("DISCORD_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL    = os.getenv("SLACK_WEBHOOK_URL", "")

WEBHOOK_TIMEOUT = 10   # seconds


def send_webhook(
    url: str,
    payload: dict,
    headers: dict = None,
) -> bool:
    """
    Send a JSON payload to any webhook URL via HTTP POST.

    Args:
        url:     Webhook endpoint URL
        payload: JSON-serialisable dict to send
        headers: Optional HTTP headers

    Returns:
        bool: True if HTTP 2xx response received

    Example:
        >>> from src.delivery.webhook import send_webhook
        >>> ok = send_webhook("https://hooks.example.com/signal", signal_dict)
    """
    if not url:
        log.debug("Webhook URL not configured — skipping.")
        return False

    default_headers = {"Content-Type": "application/json"}
    if headers:
        default_headers.update(headers)

    try:
        resp = requests.post(
            url,
            json=payload,
            headers=default_headers,
            timeout=WEBHOOK_TIMEOUT,
        )
        resp.raise_for_status()
        log.info(f"  Webhook sent to {url[:50]}... → {resp.status_code}")
        return True

    except requests.exceptions.Timeout:
        log.error(f"  Webhook timed out after {WEBHOOK_TIMEOUT}s: {url[:50]}...")
        return False
    except requests.exceptions.HTTPError as e:
        log.error(f"  Webhook HTTP error {e.response.status_code}: {url[:50]}...")
        return False
    except requests.exceptions.RequestException as e:
        log.error(f"  Webhook request failed: {e}")
        return False


def send_signal_webhook(formatted_signal: dict) -> bool:
    """
    Send a formatted signal to the configured generic webhook URL.

    Sends the complete signal dict as JSON.
    The receiving server can parse and use any fields it needs.

    Args:
        formatted_signal: Output of formatter.format_signal()

    Returns:
        bool: True if sent successfully

    Example:
        >>> from src.delivery.webhook import send_signal_webhook
        >>> ok = send_signal_webhook(formatted_signal)
    """
    if not WEBHOOK_URL:
        return False

    payload = {
        "source":    "AlgoBot Pro",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "coin":      formatted_signal.get("coin"),
        "signal":    formatted_signal.get("signal"),
        "confidence":formatted_signal.get("confidence"),
        "price":     formatted_signal.get("price"),
        "target":    formatted_signal.get("target_price"),
        "stop_loss": formatted_signal.get("stop_loss_price"),
        "reasons":   formatted_signal.get("reasons", []),
        "rsi":       formatted_signal.get("rsi"),
        "full":      formatted_signal,   # Send everything
    }

    return send_webhook(WEBHOOK_URL, payload)


def send_discord_signal(formatted_signal: dict) -> bool:
    """
    Send a signal to a Discord channel via Discord Webhook.

    Creates a rich Discord embed with colour-coded signal type.

    Args:
        formatted_signal: Output of formatter.format_signal()

    Returns:
        bool: True if sent successfully

    HOW TO SET UP:
        1. Discord → Server Settings → Integrations → Webhooks
        2. New Webhook → Copy URL
        3. Add to .env:  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

    Example:
        >>> from src.delivery.webhook import send_discord_signal
        >>> ok = send_discord_signal(formatted_signal)
    """
    if not DISCORD_WEBHOOK_URL:
        return False

    signal = formatted_signal.get("signal", "HOLD")
    coin   = formatted_signal.get("coin", "?").replace("_", "/")
    conf   = formatted_signal.get("confidence", 0)
    price  = formatted_signal.get("price", 0)
    target = formatted_signal.get("target_price", 0)
    stop   = formatted_signal.get("stop_loss_price", 0)
    rr     = formatted_signal.get("risk_reward", 0)

    # Discord embed colours
    colour_map = {"BUY": 0x16a34a, "SELL": 0xdc2626, "HOLD": 0xd97706}
    colour     = colour_map.get(signal, 0x888888)

    emoji_map  = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
    emoji      = emoji_map.get(signal, "⚪")

    reasons    = formatted_signal.get("reasons", [])
    reason_str = "\n".join(f"• {r}" for r in reasons[:3])

    payload = {
        "embeds": [{
            "title":       f"{emoji} {coin} — {signal}",
            "color":       colour,
            "description": f"**Confidence:** {conf:.0%}\n\n{reason_str}",
            "fields": [
                {"name": "Current Price", "value": f"₹{price:,.2f}",  "inline": True},
                {"name": "Target",        "value": f"₹{target:,.2f}", "inline": True},
                {"name": "Stop Loss",     "value": f"₹{stop:,.2f}",   "inline": True},
                {"name": "Risk/Reward",   "value": f"1 : {rr}",       "inline": True},
            ],
            "footer": {
                "text": f"AlgoBot Pro • {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }

    return send_webhook(DISCORD_WEBHOOK_URL, payload)


def send_slack_signal(formatted_signal: dict) -> bool:
    """
    Send a signal to a Slack channel via Slack Incoming Webhook.

    HOW TO SET UP:
        1. Slack → Apps → Incoming Webhooks → Add to Slack
        2. Choose channel → Copy Webhook URL
        3. Add to .env:  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

    Args:
        formatted_signal: Output of formatter.format_signal()

    Returns:
        bool: True if sent successfully
    """
    if not SLACK_WEBHOOK_URL:
        return False

    signal = formatted_signal.get("signal", "HOLD")
    coin   = formatted_signal.get("coin", "?").replace("_", "/")
    conf   = formatted_signal.get("confidence", 0)
    price  = formatted_signal.get("price", 0)
    target = formatted_signal.get("target_price", 0)
    stop   = formatted_signal.get("stop_loss_price", 0)

    emoji  = {"BUY": ":large_green_circle:", "SELL": ":red_circle:", "HOLD": ":large_yellow_circle:"}.get(signal, ":white_circle:")

    payload = {
        "text": f"{emoji} *{coin} — {signal}* | Confidence: {conf:.0%}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *{coin} — {signal}*\n"
                        f"Confidence: `{conf:.0%}` | "
                        f"Price: `₹{price:,.2f}` | "
                        f"Target: `₹{target:,.2f}` | "
                        f"Stop: `₹{stop:,.2f}`"
                    ),
                }
            }
        ]
    }

    return send_webhook(SLACK_WEBHOOK_URL, payload)


def broadcast_signal(formatted_signal: dict) -> dict:
    """
    Send a signal to ALL configured webhook destinations simultaneously.

    Args:
        formatted_signal: Output of formatter.format_signal()

    Returns:
        dict: { 'generic': bool, 'discord': bool, 'slack': bool }
    """
    results = {
        "generic": send_signal_webhook(formatted_signal) if WEBHOOK_URL else None,
        "discord": send_discord_signal(formatted_signal) if DISCORD_WEBHOOK_URL else None,
        "slack":   send_slack_signal(formatted_signal)   if SLACK_WEBHOOK_URL else None,
    }

    sent = sum(1 for v in results.values() if v is True)
    log.info(f"  Webhooks: {sent} sent | {results}")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if not any([WEBHOOK_URL, DISCORD_WEBHOOK_URL, SLACK_WEBHOOK_URL]):
        print("No webhook URLs configured.")
        print("Add to .env:")
        print("  WEBHOOK_URL=https://your-webhook-url.com/signal")
        print("  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
        print("  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...")
    else:
        print(f"Webhook URLs configured:")
        if WEBHOOK_URL:         print(f"  Generic : {WEBHOOK_URL[:40]}...")
        if DISCORD_WEBHOOK_URL: print(f"  Discord : {DISCORD_WEBHOOK_URL[:40]}...")
        if SLACK_WEBHOOK_URL:   print(f"  Slack   : {SLACK_WEBHOOK_URL[:40]}...")