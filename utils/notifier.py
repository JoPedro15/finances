# utils/notifier.py
# This module provides utilities for sending email alerts.

import os
import smtplib
import socket
from email.mime.text import MIMEText
from typing import Any, Dict, List
from dotenv import load_dotenv  # type: ignore[import-untyped]

from .logger.logger import logger

load_dotenv()


def send_email_alert(matches: List[Dict[str, Any]]) -> None:
    """Sends an email alert with stock dip opportunities using SMTP."""
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    sender: str = os.getenv("SMTP_USER", "")
    password: str = os.getenv("SMTP_PASSWORD", "")
    recipient: str = os.getenv("DEST_EMAIL", sender)

    if not sender or not password or not recipient:
        logger.error("Missing SMTP configuration or recipient credentials.")
        return

    subject: str = f"⚠️ Stock Dip Alert: {len(matches)} opportunities found"

    lines: List[str] = ["Dip opportunities detected:\n"]
    for match in matches:
        details: str = (
            f"• {match.get('name', match['ticker'])} ({match['ticker']}): "
            f"Dropped {match['drop_pct']}% from peak "
            f"(${match['peak_price']} -> ${match['current_price']})"
        )
        lines.append(details)

    body: str = "\n".join(lines)
    msg: MIMEText = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    try:
        logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")

        # Switch to SMTP_SSL if port is 465, otherwise use STARTTLS on 587
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(sender, password)
                server.sendmail(sender, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, [recipient], msg.as_string())

        logger.info(f"Email alert successfully sent to {recipient}")

    except (socket.timeout, TimeoutError) as e:
        logger.error(
            f"Network timeout reaching {smtp_server}:{smtp_port}. "
            "Check local firewall, VPN, or ISP port blocks.",
            exception=e,
        )
    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            "SMTP Authentication failed. Verify SMTP_USER and App Password.",
            exception=e,
        )
    except smtplib.SMTPException as e:
        logger.error("SMTP protocol error occurred", exception=e)
    except Exception as e:
        logger.error("Unexpected error sending email alert", exception=e)
