"""Unit tests for src/infra/gdrive/auth.py covering OAuth2 flows, Service Account
authentication, token refresh, headless mode, and safe credential loading.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.infra.gdrive.auth import (
    SCOPES,
    get_google_service_credentials,
    load_credentials_safe,
)


@patch("src.infra.gdrive.auth.ServiceAccountCredentials.from_service_account_file")
def test_get_credentials_service_account_env(
    mock_sa_from_file: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates loading credentials via GDRIVE_SERVICE_ACCOUNT_FILE environment
    setting.
    """
    sa_file: Path = tmp_path / "sa.json"
    sa_file.write_text('{"type": "service_account"}', encoding="utf-8")

    mock_sa_creds: MagicMock = MagicMock()
    mock_sa_from_file.return_value = mock_sa_creds

    with patch(
        "src.infra.gdrive.auth.settings.gdrive_service_account_file", str(sa_file)
    ):
        creds: Any = get_google_service_credentials(
            credentials_path=tmp_path / "non_existent_creds.json",
            token_path=tmp_path / "non_existent_token.json",
            headless=True,
        )

    assert creds == mock_sa_creds
    mock_sa_from_file.assert_called_once_with(str(sa_file), scopes=SCOPES)


@patch("src.infra.gdrive.auth.Credentials")
def test_valid_token_file_returns_credentials(
    mock_credentials_cls: MagicMock, tmp_path: Path
) -> None:
    """Validates that a valid token file directly loads and returns credentials."""
    token_file: Path = tmp_path / "token.json"
    token_file.write_text('{"token": "fake"}', encoding="utf-8")

    mock_creds: MagicMock = MagicMock()
    mock_creds.valid = True
    mock_credentials_cls.from_authorized_user_file.return_value = mock_creds

    result: Any = get_google_service_credentials(
        credentials_path=tmp_path / "credentials.json",
        token_path=token_file,
    )

    assert result == mock_creds


@patch("src.infra.gdrive.auth.Credentials")
def test_corrupted_token_file_falls_back(
    mock_credentials_cls: MagicMock, tmp_path: Path
) -> None:
    """Validates that a corrupted token file falls back to client secret
    authentication.
    """
    token_file: Path = tmp_path / "token.json"
    token_file.write_text("corrupted", encoding="utf-8")
    mock_credentials_cls.from_authorized_user_file.side_effect = Exception(
        "Invalid JSON"
    )

    with pytest.raises(PermissionError):
        get_google_service_credentials(
            credentials_path=tmp_path / "credentials.json",
            token_path=token_file,
            headless=True,
        )


@patch("src.infra.gdrive.auth.Request")
@patch("src.infra.gdrive.auth.Credentials")
def test_expired_token_refreshes_successfully(
    mock_credentials_cls: MagicMock,
    mock_request_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates that an expired token with refresh_token refreshes successfully."""
    token_file: Path = tmp_path / "token.json"
    token_file.write_text('{"token": "expired"}', encoding="utf-8")

    mock_creds: MagicMock = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh_token"

    def refresh_side_effect(*args: Any, **kwargs: Any) -> None:
        mock_creds.valid = True

    mock_creds.refresh.side_effect = refresh_side_effect
    mock_credentials_cls.from_authorized_user_file.return_value = mock_creds

    result: Any = get_google_service_credentials(
        credentials_path=tmp_path / "credentials.json",
        token_path=token_file,
    )

    mock_creds.refresh.assert_called_once()
    assert result == mock_creds


@patch("src.infra.gdrive.auth.Request")
@patch("src.infra.gdrive.auth.Credentials")
def test_expired_token_refresh_exception_falls_back(
    mock_credentials_cls: MagicMock,
    mock_request_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates that refresh failure falls back gracefully."""
    token_file: Path = tmp_path / "token.json"
    token_file.write_text('{"token": "expired"}', encoding="utf-8")

    mock_creds: MagicMock = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "invalid_refresh"
    mock_creds.refresh.side_effect = Exception("Refresh token revoked")
    mock_credentials_cls.from_authorized_user_file.return_value = mock_creds

    with pytest.raises(PermissionError):
        get_google_service_credentials(
            credentials_path=tmp_path / "credentials.json",
            token_path=token_file,
            headless=True,
        )


@patch("src.infra.gdrive.auth.InstalledAppFlow")
def test_interactive_auth_flow_saves_token(
    mock_flow_cls: MagicMock, tmp_path: Path
) -> None:
    """Validates local server flow runs and writes new token to token_path."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}', encoding="utf-8")
    token_file: Path = tmp_path / "sub" / "token.json"

    mock_creds: MagicMock = MagicMock()
    mock_creds.to_json.return_value = '{"new_token": "valid"}'

    mock_flow: MagicMock = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds
    mock_flow_cls.from_client_secrets_file.return_value = mock_flow

    result: Any = get_google_service_credentials(
        credentials_path=creds_file,
        token_path=token_file,
        headless=False,
    )

    assert result == mock_creds
    assert token_file.exists()
    assert token_file.read_text(encoding="utf-8") == '{"new_token": "valid"}'


def test_headless_mode_raises_permission_error(tmp_path: Path) -> None:
    """Validates headless mode raises PermissionError when re-auth is needed."""
    credentials_file: Path = tmp_path / "credentials.json"
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
    """Validates missing client secrets file raises FileNotFoundError."""
    missing_creds: Path = tmp_path / "missing_creds.json"

    with pytest.raises(FileNotFoundError, match="Missing client secrets at"):
        get_google_service_credentials(
            credentials_path=missing_creds,
            token_path=tmp_path / "non_existent_token.json",
            headless=False,
        )


def test_load_credentials_safe_missing_or_empty(tmp_path: Path) -> None:
    """Validates load_credentials_safe handles missing and empty files."""
    assert load_credentials_safe(tmp_path / "missing.json") == {
        "status": "empty_or_missing"
    }
    empty_file: Path = tmp_path / "empty.json"
    empty_file.touch()
    assert load_credentials_safe(empty_file) == {"status": "empty_or_missing"}


def test_load_credentials_safe_valid_and_invalid_json(tmp_path: Path) -> None:
    """Validates load_credentials_safe parses valid dicts and flags non-dict or
    malformed JSON.
    """
    valid_file: Path = tmp_path / "valid.json"
    valid_file.write_text('{"key": "value"}', encoding="utf-8")
    assert load_credentials_safe(valid_file) == {"key": "value"}

    invalid_json: Path = tmp_path / "invalid.json"
    invalid_json.write_text("{broken", encoding="utf-8")
    assert load_credentials_safe(invalid_json) == {"status": "invalid_json"}

    non_dict_json: Path = tmp_path / "list.json"
    non_dict_json.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_credentials_safe(non_dict_json) == {"status": "invalid_json"}
