"""
src/delivery/telegram_bot.py
=============================
PURPOSE:
    Send trading signals to Telegram subscribers.
    Handles:
    - Formatting signal messages
    - Managing subscriber lists
    - Sending messages to individual users or broadcast

HOW TO SET UP:
    1. Create a Telegram bot via @BotFather (get TOKEN)
    2. Store TOKEN in environment variable: TELEGRAM_BOT_TOKEN
    3. Find your chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates
    4. Add subscribers to database or env file

DEPENDENCIES:
    pip install python-telegram-bot
"""

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

# Get bot token from environment (or use None for development)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None)


def send_message(chat_id: str, message: str, notify: bool = True) -> bool:
    """
    Send a Telegram message to a user.
    
    Args:
        chat_id: Telegram chat ID
        message: Message text (supports Markdown)
        notify: Whether to notify the user
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN:
        log.warning(f"Telegram token not configured. Message not sent to {chat_id}")
        return False
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        params = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_notification": not notify,
        }
        response = requests.post(url, json=params, timeout=10)
        
        if response.status_code == 200:
            log.info(f"Message sent to {chat_id}")
            return True
        else:
            log.error(f"Failed to send message to {chat_id}: {response.text}")
            return False
            
    except Exception as e:
        log.error(f"Error sending Telegram message: {e}")
        return False


def send_to_all_subscribers(message: str, subscribers: Optional[list] = None) -> dict:
    """
    Send a message to all registered subscribers.
    
    Args:
        message: Message text to send
        subscribers: List of subscriber dicts with 'chat_id' key
                    If None, will try to load from database/config
    
    Returns:
        dict: {successful: int, failed: int, skipped: int}
    """
    if subscribers is None:
        # Default mock subscribers for development
        subscribers = [
            {"chat_id": "123456789", "coins": ["BTC_USD", "ETH_USD"], "risk_level": "medium"},
        ]
    
    results = {
        "successful": 0,
        "failed": 0,
        "skipped": 0,
    }
    
    for subscriber in subscribers:
        chat_id = subscriber.get("chat_id")
        if not chat_id:
            results["skipped"] += 1
            continue
        
        if send_message(str(chat_id), message):
            results["successful"] += 1
        else:
            results["failed"] += 1
    
    log.info(f"Telegram broadcast: {results['successful']} sent, {results['failed']} failed, {results['skipped']} skipped")
    return results


def send_signal_card(coin: str, signal_card: dict, subscribers: Optional[list] = None) -> dict:
    """
    Send a formatted signal card to subscribers who track this coin.
    
    Args:
        coin: Coin name (e.g., 'BTC_USD')
        signal_card: Dict with formatted signal info
        subscribers: List of subscribing users (optional filter)
    
    Returns:
        dict: Broadcast results
    """
    # Format the signal card into a readable message
    sig = signal_card.get("signal", "HOLD")
    conf = signal_card.get("confidence", 0)
    price = signal_card.get("price", "?")
    target = signal_card.get("target", "?")
    stop_loss = signal_card.get("stop_loss", "?")
    
    message = (
        f"🎯 *{coin} SIGNAL*\n"
        f"Signal: {sig}\n"
        f"Confidence: {conf:.1%}\n"
        f"Price: ${price}\n"
        f"Target: ${target}\n"
        f"Stop Loss: ${stop_loss}\n"
    )
    
    # Filter subscribers to only those tracking this coin
    if subscribers:
        subscribers = [
            s for s in subscribers 
            if coin in s.get("coins", [])
        ]
    
    return send_to_all_subscribers(message, subscribers)


if __name__ == "__main__":
    # Test function
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
    )
    
    test_message = "🤖 AlgoBot Pro Test Message\nIf you see this, Telegram is working!"
    results = send_to_all_subscribers(test_message)
    print(f"Test broadcast results: {results}")