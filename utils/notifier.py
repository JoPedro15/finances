# utils/notifier.py
# This module provides utilities for sending email alerts.

import os
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, List

from .logger.logger import logger


def send_email_alert(matches: List[Dict[str, Any]]) -> None:
    """Sends an email alert with stock dip opportunities using SMTP.

    Args:
        matches (List[Dict[str, Any]]): A list of dictionaries containing dip
          details.
    """
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    sender: str = os.getenv("SMTP_USER", "")
    password: str = os.getenv("SMTP_PASSWORD", "")
    recipient: str = os.getenv("DEST_EMAIL", "")

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
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
            logger.info(f"Email alert successfully sent to {recipient}")
    except Exception as e:
        logger.error("Error sending email alert via SMTP", exception=e)
