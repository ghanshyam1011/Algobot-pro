"""
src/delivery/email_sender.py
==============================
PURPOSE:
    Send daily signal digest emails to subscribers.
    Summarises all signals from the past 24 hours in one clean email.

    Unlike Telegram (which sends instant alerts), email is used for:
    - Daily morning summary (what happened overnight)
    - Weekly performance report
    - System alerts (pipeline failures, errors)

EMAIL TYPES:
    1. Daily digest     — summary of yesterday's signals + P&L
    2. Signal alert     — instant email for one signal (optional)
    3. System alert     — errors, downtime, model retraining needed

SETUP:
    Gmail (recommended):
    1. Enable 2-Factor Authentication on your Gmail account
    2. Go to Google Account → Security → App Passwords
    3. Create an App Password for "Mail"
    4. Add to .env:
       EMAIL_SENDER=youremail@gmail.com
       EMAIL_PASSWORD=your_app_password_here
       EMAIL_SMTP_HOST=smtp.gmail.com
       EMAIL_SMTP_PORT=587

DEPENDENCIES:
    Built-in: smtplib, email (no pip install needed)
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

from config.settings import (
    EMAIL_SENDER,
    EMAIL_PASSWORD,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    LABEL_EMOJIS,
)

log = logging.getLogger(__name__)


def _is_configured() -> bool:
    """Return True if email credentials are set in .env"""
    return bool(EMAIL_SENDER and EMAIL_PASSWORD)


def send_email(
    to_address: str,
    subject: str,
    body_html: str,
    body_text: str = None,
) -> bool:
    """
    Send an email using the configured SMTP server.

    Args:
        to_address: Recipient email address
        subject:    Email subject line
        body_html:  HTML email body (shown in modern email clients)
        body_text:  Plain text fallback (shown in old clients or if HTML fails)

    Returns:
        bool: True if sent successfully, False otherwise

    Example:
        >>> from src.delivery.email_sender import send_email
        >>> ok = send_email("user@example.com", "Test", "<h1>Hello</h1>")
    """
    if not _is_configured():
        log.warning(
            "Email not configured. Add EMAIL_SENDER and EMAIL_PASSWORD to .env"
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"AlgoBot Pro <{EMAIL_SENDER}>"
        msg["To"]      = to_address

        # Attach plain text first, HTML second (email clients prefer the last one)
        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_address, msg.as_string())

        log.info(f"  Email sent to {to_address}: '{subject}'")
        return True

    except smtplib.SMTPAuthenticationError:
        log.error(
            "Email authentication failed. Check EMAIL_SENDER and EMAIL_PASSWORD in .env.\n"
            "If using Gmail, make sure you're using an App Password, not your main password."
        )
        return False
    except smtplib.SMTPException as e:
        log.error(f"  SMTP error sending email to {to_address}: {e}")
        return False
    except Exception as e:
        log.error(f"  Unexpected email error: {e}")
        return False


def send_daily_digest(
    to_address: str,
    signals: list,
    capital: float = 50000.0,
) -> bool:
    """
    Send a daily digest email summarising all signals from the past 24 hours.

    Args:
        to_address: Recipient email address
        signals:    List of signal dicts from signal_log.json
        capital:    User's capital (for P&L display)

    Returns:
        bool: True if sent successfully

    Example:
        >>> from src.delivery.email_sender import send_daily_digest
        >>> from src.data_pipeline.data_store import load_signal_log
        >>> signals = load_signal_log()[-24:]   # Last 24 signals
        >>> send_daily_digest("user@gmail.com", signals)
    """
    now       = datetime.now(timezone.utc)
    date_str  = now.strftime("%d %B %Y")
    subject   = f"AlgoBot Pro — Daily Digest {date_str}"

    # Filter to last 24 hours
    cutoff    = now - timedelta(hours=24)
    recent    = []
    for s in signals:
        try:
            ts = datetime.fromisoformat(
                s.get("timestamp", s.get("logged_at", "2000-01-01"))
                .replace("Z", "+00:00")
            )
            if ts >= cutoff:
                recent.append(s)
        except Exception:
            continue

    # Count signal types
    buy_count  = sum(1 for s in recent if s.get("signal") == "BUY")
    sell_count = sum(1 for s in recent if s.get("signal") == "SELL")
    hold_count = sum(1 for s in recent if s.get("signal") == "HOLD")
    total      = len(recent)

    # Build HTML email
    signal_rows = ""
    for s in recent[-20:]:   # Show last 20
        sig   = s.get("signal", "?")
        emoji = LABEL_EMOJIS.get(sig, "⚪")
        color = {"BUY": "#16a34a", "SELL": "#dc2626", "HOLD": "#d97706"}.get(sig, "#666")
        ts    = s.get("timestamp", "")[:16].replace("T", " ")
        coin  = s.get("coin", "?").replace("_", "/")
        conf  = s.get("confidence", 0)
        price = s.get("price", 0)

        signal_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">{ts} UTC</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">{coin}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;color:{color};font-weight:bold;">
                {emoji} {sig}
            </td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">{conf:.0%}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">₹{price:,.2f}</td>
        </tr>
        """

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#333;">

        <div style="background:#1B3A5C;color:white;padding:24px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:24px;">📈 AlgoBot Pro</h1>
            <p style="margin:8px 0 0;opacity:0.8;">Daily Signal Digest — {date_str}</p>
        </div>

        <div style="background:#f8f9fa;padding:20px;border-radius:0 0 8px 8px;">

            <!-- Summary Cards -->
            <div style="display:flex;gap:12px;margin-bottom:20px;">
                <div style="flex:1;background:white;padding:16px;border-radius:8px;
                            border-left:4px solid #2563EB;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#2563EB;">{total}</div>
                    <div style="font-size:12px;color:#666;">Total Signals</div>
                </div>
                <div style="flex:1;background:white;padding:16px;border-radius:8px;
                            border-left:4px solid #16a34a;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#16a34a;">{buy_count}</div>
                    <div style="font-size:12px;color:#666;">BUY Signals</div>
                </div>
                <div style="flex:1;background:white;padding:16px;border-radius:8px;
                            border-left:4px solid #dc2626;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#dc2626;">{sell_count}</div>
                    <div style="font-size:12px;color:#666;">SELL Signals</div>
                </div>
                <div style="flex:1;background:white;padding:16px;border-radius:8px;
                            border-left:4px solid #d97706;text-align:center;">
                    <div style="font-size:28px;font-weight:bold;color:#d97706;">{hold_count}</div>
                    <div style="font-size:12px;color:#666;">HOLD Signals</div>
                </div>
            </div>

            <!-- Signal Table -->
            <div style="background:white;border-radius:8px;padding:16px;">
                <h3 style="margin:0 0 12px;font-size:16px;">Signals (last 24 hours)</h3>
                {'<p style="color:#999;text-align:center;padding:20px;">No signals in the last 24 hours.</p>' if not recent else f"""
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead>
                        <tr style="background:#f8f9fa;">
                            <th style="padding:8px;text-align:left;color:#666;">Time</th>
                            <th style="padding:8px;text-align:left;color:#666;">Coin</th>
                            <th style="padding:8px;text-align:left;color:#666;">Signal</th>
                            <th style="padding:8px;text-align:left;color:#666;">Confidence</th>
                            <th style="padding:8px;text-align:left;color:#666;">Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {signal_rows}
                    </tbody>
                </table>
                """}
            </div>

            <!-- Footer -->
            <div style="text-align:center;margin-top:20px;font-size:11px;color:#999;">
                <p>AlgoBot Pro | Signals generated every hour automatically</p>
                <p>⚠️ For educational purposes only. Not financial advice.</p>
            </div>
        </div>
    </body>
    </html>
    """

    body_text = (
        f"AlgoBot Pro — Daily Digest {date_str}\n\n"
        f"Total signals: {total} | BUY: {buy_count} | SELL: {sell_count} | HOLD: {hold_count}\n\n"
        f"Recent signals:\n" +
        "\n".join(
            f"  {s.get('coin','?').replace('_','/')}: "
            f"{s.get('signal','?')} ({s.get('confidence',0):.0%}) "
            f"@ {s.get('price',0):,.2f}"
            for s in recent[-10:]
        )
    )

    return send_email(to_address, subject, body_html, body_text)


def send_system_alert(
    to_address: str,
    title: str,
    message: str,
    level: str = "WARNING",
) -> bool:
    """
    Send a system alert email (errors, pipeline failures, etc.)

    Args:
        to_address: Recipient email
        title:      Alert title
        message:    Detailed message
        level:      'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

    Returns:
        bool: True if sent
    """
    colors = {
        "INFO":     "#2563EB",
        "WARNING":  "#d97706",
        "ERROR":    "#dc2626",
        "CRITICAL": "#7c3aed",
    }
    color   = colors.get(level, "#666")
    subject = f"[AlgoBot Pro {level}] {title}"

    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;">
        <div style="background:{color};color:white;padding:16px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;">🚨 {level}: {title}</h2>
        </div>
        <div style="background:#f8f9fa;padding:20px;border-radius:0 0 8px 8px;">
            <pre style="background:white;padding:12px;border-radius:4px;
                        font-size:13px;white-space:pre-wrap;">{message}</pre>
            <p style="font-size:12px;color:#999;">
                AlgoBot Pro System Alert — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
            </p>
        </div>
    </div>
    """

    return send_email(to_address, subject, body_html, f"{level}: {title}\n\n{message}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if not _is_configured():
        print("Email not configured. Add EMAIL_SENDER and EMAIL_PASSWORD to .env")
    else:
        print("Email configured. Sending test alert ...")
        ok = send_system_alert(
            EMAIL_SENDER,
            "Test Alert",
            "This is a test alert from AlgoBot Pro.\nSystem is running normally.",
            level="INFO"
        )
        print("Sent!" if ok else "Failed — check logs.")