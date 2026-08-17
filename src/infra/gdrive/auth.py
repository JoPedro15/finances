from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Final, cast

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]

from src.utils.logger.logger import logger

DEFAULT_SCOPES: Final[list[str]] = [
    "https://www.googleapis.com/auth/drive",
]


def get_google_service_credentials(
    credentials_path: str | Path,
    token_path: str | Path,
    scopes: list[str] | None = None,
    headless: bool = False,
) -> Credentials:
    """Handles the OAuth2 flow and returns valid credentials."""
    selected_scopes: Final[list[str]] = scopes or DEFAULT_SCOPES
    creds_file: Final[Path] = Path(credentials_path)
    token_file: Final[Path] = Path(token_path)

    creds: Credentials | None = None

    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
                str(token_file), selected_scopes
            )
        except Exception as e:
            logger.warning(f"Existing token at {token_file.name} is invalid: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Access token expired. Refreshing session...")
            try:
                creds.refresh(Request())  # type: ignore[no-untyped-call]
            except RefreshError:
                logger.error(
                    "Token refresh failed (Revoked/Expired). Re-authenticating."
                )
                creds = None
            except Exception as e:
                logger.error(f"Unexpected error during token refresh: {e}")
                creds = None

        if not creds or not creds.valid:
            if headless:
                logger.error("Headless mode enabled. Cannot perform manual login.")
                raise PermissionError(
                    "Authentication required but headless mode is on."
                )

            if not creds_file.exists():
                error_msg: str = f"Missing client secrets at {creds_file.absolute()}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            if not sys.stdin.isatty():
                logger.error(
                    "Non-interactive environment detected. Manual login impossible."
                )
                raise PermissionError("Manual OAuth flow requires user interaction.")

            logger.section("Google OAuth2 Authentication")
            logger.info("Opening browser for authorization...")

            flow: InstalledAppFlow = InstalledAppFlow.from_client_secrets_file(
                str(creds_file), selected_scopes
            )
            creds = flow.run_local_server(port=0)

        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
        logger.success(f"Authentication successful. Token saved to {token_file.name}")

    return creds


def load_credentials_safe(file_path: str | Path) -> dict[str, Any]:
    """Safe loader to prevent JSONDecodeError in CI/CD pipelines."""
    path: Final[Path] = Path(file_path)

    if not path.exists() or path.stat().st_size == 0:
        return {"status": "empty_or_missing", "path": str(path.absolute())}

    try:
        with open(path, encoding="utf-8") as f:
            data: Any = json.load(f)
            if not isinstance(data, dict):
                return {"status": "invalid_json", "path": str(path.absolute())}
            return cast(dict[str, Any], data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format in {path.name}: {e}")
        return {"status": "invalid_json", "path": str(path.absolute())}
