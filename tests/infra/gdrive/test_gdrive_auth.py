"""
Unit tests for src/infra/gdrive/auth.py covering Google Service
credentials.json retrieval, token refreshment, headless mode verification,
and safe credential loading.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.infra.gdrive.auth import (
    get_google_service_credentials,
    load_credentials_safe,
)


@patch("src.infra.gdrive.auth.Credentials")
def test_valid_token_file_returns_credentials(
    mock_credentials_cls: MagicMock, tmp_path: Path
) -> None:
    """Tests that a valid token file directly loads and returns credentials.json."""
    token_file: Path = tmp_path / "token.json"
    token_file.write_text('{"token": "fake"}', encoding="utf-8")

    mock_creds: MagicMock = MagicMock()
    mock_creds.valid = True
    mock_credentials_cls.from_authorized_user_file.return_value = mock_creds

    result: Any = get_google_service_credentials(
        credentials_path=tmp_path / "credentials.json.json",
        token_path=token_file,
    )

    assert result == mock_creds


@patch("src.infra.gdrive.auth.Request")
@patch("src.infra.gdrive.auth.Credentials")
def test_expired_token_refreshes_successfully(
    mock_credentials_cls: MagicMock,
    mock_request_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Tests that an expired token is refreshed successfully."""
    token_file: Path = tmp_path / "token.json"
    token_file.write_text('{"token": "expired"}', encoding="utf-8")

    mock_creds: MagicMock = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh_token"
    mock_creds.to_json.return_value = '{"token": "refreshed"}'

    def refresh_side_effect(*args: Any, **kwargs: Any) -> None:
        mock_creds.valid = True

    mock_creds.refresh.side_effect = refresh_side_effect
    mock_credentials_cls.from_authorized_user_file.return_value = mock_creds

    result: Any = get_google_service_credentials(
        credentials_path=tmp_path / "credentials.json.json",
        token_path=token_file,
    )

    mock_creds.refresh.assert_called_once()
    assert result == mock_creds
    assert result.valid is True


def test_headless_mode_raises_permission_error(tmp_path: Path) -> None:
    """Tests that headless mode raises PermissionError when re-auth is needed."""
    credentials_file: Path = tmp_path / "credentials.json.json"
    credentials_file.write_text('{"installed": {}}', encoding="utf-8")

    with pytest.raises(
        PermissionError, match="Authentication required but headless mode is on."
    ):
        get_google_service_credentials(
            credentials_path=credentials_file,
            token_path=tmp_path / "non_existent_token.json",
            headless=True,
        )


def test_missing_credentials_file_raises_file_not_found(tmp_path: Path) -> None:
    """Tests that a missing client secrets file raises FileNotFoundError."""
    missing_creds: Path = tmp_path / "missing_creds.json"

    with patch("sys.stdin.isatty", return_value=True):
        with pytest.raises(FileNotFoundError, match="Missing client secrets at"):
            get_google_service_credentials(
                credentials_path=missing_creds,
                token_path=tmp_path / "non_existent_token.json",
                headless=False,
            )


def test_load_credentials_safe_missing_file(tmp_path: Path) -> None:
    """Tests loading credentials.json from a non-existent file."""
    result: dict[str, Any] = load_credentials_safe(tmp_path / "missing.json")
    assert result["status"] == "empty_or_missing"


def test_load_credentials_safe_valid_json(tmp_path: Path) -> None:
    """Tests loading credentials.json from a valid JSON file."""
    file_path: Path = tmp_path / "valid.json"
    file_path.write_text('{"key": "value"}', encoding="utf-8")

    result: dict[str, Any] = load_credentials_safe(file_path)
    assert result == {"key": "value"}


def test_load_credentials_safe_invalid_json(tmp_path: Path) -> None:
    """Tests loading credentials.json from a corrupted JSON file."""
    file_path: Path = tmp_path / "invalid.json"
    file_path.write_text("{invalid_json}", encoding="utf-8")

    result: dict[str, Any] = load_credentials_safe(file_path)
    assert result["status"] == "invalid_json"
