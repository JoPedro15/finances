# utils/gdrive/service.py

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Final

from googleapiclient.discovery import Resource, build  # type: ignore
from googleapiclient.http import MediaFileUpload  # type: ignore
from googleapiclient.http import MediaIoBaseDownload  # type: ignore

from utils.config import (
    CREDS_PATH_GDRIVE,
    GDRIVE_FOLDER_ID,
    TOKEN_PATH_GDRIVE,
)
from utils.logger.logger import logger
from .auth import get_google_service_credentials

__all__: list[str] = ["GDriveService"]


class GDriveService:
    """Module to interact with Google Drive API v3."""

    _MIME_EXPORT_MAP: Final[dict[str, str]] = {
        "application/vnd.google-apps.spreadsheet": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        "application/vnd.google-apps.document": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        "application/vnd.google-apps.presentation": (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
    }

    def __init__(
        self,
        credentials_path: str = str(CREDS_PATH_GDRIVE),
        token_path: str = str(TOKEN_PATH_GDRIVE),
        output_folder_id: str | None = None,
    ) -> None:
        self.credentials_path: str = credentials_path
        self.token_path: str = token_path
        self.output_folder_id: str | None = output_folder_id or GDRIVE_FOLDER_ID

        Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)

        self.scopes: Final[list[str]] = ["https://www.googleapis.com/auth/drive"]
        self.service: Resource = self._init_service()

    def _init_service(self) -> Resource:
        """Builds the authorized Google Drive API service resource."""
        if not os.path.exists(self.credentials_path):
            logger.error(f"Credentials file not found at: {self.credentials_path}")
            raise FileNotFoundError(
                f"Missing Google credentials: {self.credentials_path}"
            )

        creds: Any = get_google_service_credentials(
            self.credentials_path, self.token_path, self.scopes
        )
        return build("drive", "v3", credentials=creds)

    def upload_file(
        self, file_path: str | Path, folder_id: str, overwrite: bool = True
    ) -> str:
        """Uploads a file to a specific GDrive folder."""
        str_path: str = str(file_path)
        file_name: str = os.path.basename(str_path)
        media: MediaFileUpload = MediaFileUpload(str_path, resumable=True)

        if overwrite:
            safe_name: str = file_name.replace("'", "\\'")
            query: str = (
                f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"
            )
            response: dict[str, Any] = (
                self.service.files().list(q=query, fields="files(id)").execute()
            )
            existing_files: list[dict[str, str]] = response.get("files", [])

            if existing_files:
                file_id: str = existing_files[0]["id"]
                logger.info(f"Overwriting file: {file_name} (ID: {file_id})")
                updated_file = (
                    self.service.files()
                    .update(fileId=file_id, media_body=media)
                    .execute()
                )
                return str(updated_file.get("id"))

        file_metadata: dict[str, Any] = {
            "name": file_name,
            "parents": [folder_id],
        }
        logger.info(f"Creating new file: {file_name}")
        new_file = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        return str(new_file.get("id"))

    def file_exists(self, file_name: str, folder_id: str) -> bool:
        """Verifies if a file exists within a specific folder."""
        safe_name: str = file_name.replace("'", "\\'")
        query: str = (
            f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"
        )
        results: dict[str, Any] = (
            self.service.files()
            .list(q=query, spaces="drive", fields="files(id)")
            .execute()
        )

        return len(results.get("files", [])) > 0

    def download_file(self, file_id: str, local_path: str | Path) -> None:
        """Downloads a file. Supports binary files and Workspace exports."""
        str_local_path: str = str(local_path)
        file_metadata: dict[str, Any] = (
            self.service.files().get(fileId=file_id, fields="mimeType, name").execute()
        )

        mime_type: str = file_metadata.get("mimeType", "")
        logger.info(f"Downloading {file_metadata.get('name')} (MIME: {mime_type})")

        if mime_type in self._MIME_EXPORT_MAP:
            export_mime: str = self._MIME_EXPORT_MAP[mime_type]
            request = self.service.files().export_media(
                fileId=file_id, mimeType=export_mime
            )
        else:
            request = self.service.files().get_media(fileId=file_id)

        with io.FileIO(str_local_path, "wb") as fh:
            downloader: MediaIoBaseDownload = MediaIoBaseDownload(fh, request)
            done: bool = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"Download Progress: {int(status.progress() * 100)}%")

        logger.success(f"File saved to: {str_local_path}")

    def list_files(
        self, folder_id: str | None = None, limit: int = 10
    ) -> list[dict[str, str]]:
        """Lists files in a specific folder or default output folder."""
        query: str = "trashed = false"
        target_folder: str | None = folder_id or self.output_folder_id

        if target_folder:
            query += f" and '{target_folder}' in parents"

        results: dict[str, Any] = (
            self.service.files()
            .list(q=query, spaces="drive", fields="files(id, name)", pageSize=limit)
            .execute()
        )

        return results.get("files", [])
