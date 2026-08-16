# tests/test_notifier.py
# Unit tests for utils.notifier

import base64
import os
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import pytest

from utils.notifier import send_email_alert


@pytest.fixture
def mock_matches() -> List[Dict[str, Any]]:
    """Fixture providing a list of mock stock dip matches."""
    return [
        {
            "name": "Apple",
            "ticker": "AAPL",
            "current_price": 180.0,
            "peak_price": 200.0,
            "drop_pct": 10.0,
        },
        {
            "name": "NVIDIA",
            "ticker": "NVDA",
            "current_price": 110.0,
            "peak_price": 122.2,
            "drop_pct": 9.98,
        },
    ]


@patch("smtplib.SMTP")
@patch.dict(
    os.environ,
    {
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "test@example.com",
        "SMTP_PASSWORD": "secretpassword",
        "DEST_EMAIL": "alerts@example.com",
    },
)
def test_send_email_alert_success(
    mock_smtp_class: MagicMock, mock_matches: List[Dict[str, Any]]
) -> None:
    """Tests successful email delivery when all environment variables are present."""
    mock_server_instance: MagicMock = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server_instance

    send_email_alert(mock_matches)

    mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
    mock_server_instance.starttls.assert_called_once()
    mock_server_instance.login.assert_called_once_with(
        "test@example.com", "secretpassword"
    )
    mock_server_instance.sendmail.assert_called_once()

    call_args: tuple[Any, ...] = mock_server_instance.sendmail.call_args[0]
    assert call_args[0] == "test@example.com"
    assert call_args[1] == ["alerts@example.com"]

    # Decode base64 body payload from raw MIME string
    raw_email: str = call_args[2]
    payload_base64: str = raw_email.split("\n\n")[-1].replace("\n", "")
    decoded_body: str = base64.b64decode(payload_base64).decode("utf-8")

    assert "Apple (AAPL)" in decoded_body
    assert "NVIDIA (NVDA)" in decoded_body


@patch("smtplib.SMTP")
@patch.dict(
    os.environ,
    {
        "SMTP_USER": "",
        "SMTP_PASSWORD": "secretpassword",
        "DEST_EMAIL": "alerts@example.com",
    },
    clear=True,
)
def test_send_email_alert_missing_credentials(
    mock_smtp_class: MagicMock, mock_matches: List[Dict[str, Any]]
) -> None:
    """Tests that email is not sent when mandatory environment variables are missing."""
    send_email_alert(mock_matches)
    mock_smtp_class.assert_not_called()


@patch("smtplib.SMTP")
@patch.dict(
    os.environ,
    {
        "SMTP_USER": "test@example.com",
        "SMTP_PASSWORD": "secretpassword",
        "DEST_EMAIL": "alerts@example.com",
    },
)
def test_send_email_alert_smtp_exception(
    mock_smtp_class: MagicMock, mock_matches: List[Dict[str, Any]]
) -> None:
    """Tests graceful handling when an SMTP connection error occurs."""
    mock_smtp_class.side_effect = Exception("SMTP Connection Error")

    # Should handle the exception without crashing
    send_email_alert(mock_matches)
    mock_smtp_class.assert_called_once()
coslflefxqyohpek