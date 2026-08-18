"""
Authentication module for Google Drive API integration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]

SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.file"]


def load_credentials_safe(file_path: str | Path) -> dict[str, Any]:
    """Safely loads a JSON credentials.json file, returning status dict on failure."""
    path: Path = Path(file_path)
    if not path.exists() or path.stat().st_size == 0:
        return {"status": "empty_or_missing"}

    try:
        with open(path, encoding="utf-8") as f:
            data: Any = json.load(f)
            if isinstance(data, dict):
                return data
            return {"status": "invalid_json"}
    except (json.JSONDecodeError, OSError):
        return {"status": "invalid_json"}


def get_google_service_credentials(
    credentials_path: str | Path | None = None,
    token_path: str | Path | None = None,
    headless: bool = False,
) -> Any:
    """Loads Google Drive OAuth2 or Service Account credentials.json
    securely from environment variables or files."""
    sa_file: str | None = os.getenv("GDRIVE_SERVICE_ACCOUNT_FILE")
    if sa_file and Path(sa_file).exists():
        return ServiceAccountCredentials.from_service_account_file(
            sa_file, scopes=SCOPES
        )  # type: ignore[no-untyped-call]

    token_target: str | Path = (
        token_path or os.getenv("GDRIVE_TOKEN_FILE") or "token.json"
    )
    creds_target: str | Path = (
        credentials_path
        or os.getenv("GDRIVE_CLIENT_SECRET_FILE")
        or "credentials.json.json"
    )

    target_token_path: Path = Path(token_target)
    target_creds_path: Path = Path(creds_target)

    creds: Credentials | None = None

    if target_token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(target_token_path), SCOPES
            )  # type: ignore[no-untyped-call]
        except Exception:
            creds = None

    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())  # type: ignore[no-untyped-call]
        except Exception:
            creds = None

    if creds and creds.valid:
        return creds

    if headless:
        raise PermissionError("Authentication required but headless mode is on.")

    if not target_creds_path.exists():
        raise FileNotFoundError(f"Missing client secrets at {target_creds_path}")

    flow: InstalledAppFlow = InstalledAppFlow.from_client_secrets_file(
        str(target_creds_path), SCOPES
    )
    creds = flow.run_local_server(port=0)
    target_token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_token_path, "w", encoding="utf-8") as token_file:
        token_file.write(creds.to_json())

    return creds


get_gdrive_credentials = get_google_service_credentials
