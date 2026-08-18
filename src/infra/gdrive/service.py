"""
Service wrapper for Google Drive file upload, download, and backup operations.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from googleapiclient.discovery import Resource, build  # type: ignore[import-untyped]
from googleapiclient.http import (  # type: ignore[import-untyped]
    MediaFileUpload,
    MediaIoBaseDownload,
)

from src.infra.gdrive.auth import get_google_service_credentials
from src.utils.logger.logger import logger


class GDriveService:
    """Service wrapper for uploading, downloading,
    and backing up files to Google Drive."""

    def __init__(
        self,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        folder_id: str | None = None,
    ) -> None:
        if credentials_path and not Path(credentials_path).exists():
            raise FileNotFoundError(
                f"Missing Google credentials.json: {credentials_path}"
            )

        self.credentials_path: str | Path | None = credentials_path
        self.token_path: str | Path | None = token_path
        self.folder_id: str | None = folder_id or os.getenv("GDRIVE_CONFIG_FOLDER_ID")
        self._service: Resource | None = None

    def _get_service(self) -> Resource | None:
        if self._service is None:
            try:
                creds: Any = get_google_service_credentials(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                )
                if creds is None:
                    logger.warning("No valid Google Drive credentials.json available.")
                    return None
                self._service = build("drive", "v3", credentials=creds)
            except Exception as e:
                logger.warning(f"Failed to build Google Drive API service: {e}")
                return None
        return self._service

    def file_exists(self, file_name: str, folder_id: str | None = None) -> bool:
        """Checks if a file exists in the target Google Drive folder."""
        service: Resource | None = self._get_service()
        if service is None:
            return False

        target_folder: str | None = folder_id or self.folder_id
        query: str = f"name = '{file_name}' and trashed = false"
        if target_folder:
            query += f" and '{target_folder}' in parents"

        try:
            response: dict[str, Any] = (
                service.files().list(q=query, fields="files(id, name)").execute()
            )
            files: list[dict[str, Any]] = response.get("files", [])
            return len(files) > 0
        except Exception as e:
            logger.warning(f"Failed to check file existence for '{file_name}': {e}")
            return False

    def list_files(
        self, folder_id: str | None = None, limit: int = 10
    ) -> list[dict[str, str]]:
        """Lists files inside a target Google Drive folder."""
        service: Resource | None = self._get_service()
        if service is None:
            return []

        target_folder: str | None = folder_id or self.folder_id
        query: str = "trashed = false"
        if target_folder:
            query += f" and '{target_folder}' in parents"

        try:
            response: dict[str, Any] = (
                service.files()
                .list(q=query, pageSize=limit, fields="files(id, name)")
                .execute()
            )
            raw_files: list[dict[str, Any]] = response.get("files", [])
            return [
                {"id": str(f.get("id")), "name": str(f.get("name"))} for f in raw_files
            ]
        except Exception as e:
            logger.warning(f"Failed to list files in Google Drive: {e}")
            return []

    def upload_file(
        self,
        file_path: str | Path,
        folder_id: str | None = None,
        overwrite: bool = False,
        mime_type: str = "application/octet-stream",
    ) -> Any:
        """Uploads or updates a file on Google Drive."""
        path: Path = Path(file_path)
        if not path.exists():
            logger.warning(f"Cannot upload non-existent file '{path}'.")
            return False

        service: Resource | None = self._get_service()
        if service is None:
            return False

        target_folder: str | None = folder_id or self.folder_id
        media: MediaFileUpload = MediaFileUpload(
            str(path), mimetype=mime_type, resumable=True
        )

        try:
            if overwrite:
                query: str = f"name = '{path.name}' and trashed = false"
                if target_folder:
                    query += f" and '{target_folder}' in parents"

                existing_resp: dict[str, Any] = (
                    service.files().list(q=query, fields="files(id)").execute()
                )
                existing_files: list[dict[str, Any]] = existing_resp.get("files", [])

                if existing_files:
                    file_id: str = str(existing_files[0]["id"])
                    updated_file: dict[str, Any] = (
                        service.files()
                        .update(
                            fileId=file_id,
                            media_body=media,
                            fields="id",
                        )
                        .execute()
                    )
                    logger.info(
                        f"File '{path.name}' updated successfully on Google Drive."
                    )
                    return updated_file.get("id", file_id)

            file_metadata: dict[str, Any] = {"name": path.name}
            if target_folder:
                file_metadata["parents"] = [target_folder]

            created_file: dict[str, Any] = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name",
                )
                .execute()
            )
            logger.info(f"File '{path.name}' uploaded successfully to Google Drive.")
            return created_file.get("id", True)
        except Exception as e:
            logger.warning(f"Google Drive upload failed for '{path.name}': {e}")
            return False

    def download_file(
        self,
        file_name: str,
        destination_path: str | Path,
        folder_id: str | None = None,
    ) -> bool:
        """Downloads a file from Google Drive to local disk."""
        dest: Path = Path(destination_path)
        service: Resource | None = self._get_service()
        if service is None:
            return False

        target_folder: str | None = folder_id or self.folder_id
        query: str = f"name = '{file_name}' and trashed = false"
        if target_folder:
            query += f" and '{target_folder}' in parents"

        try:
            response: dict[str, Any] = (
                service.files().list(q=query, fields="files(id, name)").execute()
            )
            files: list[dict[str, Any]] = response.get("files", [])
            if not files:
                logger.warning(f"File '{file_name}' not found on Google Drive.")
                return False

            file_id: str = str(files[0]["id"])
            request = service.files().get_media(fileId=file_id)
            dest.parent.mkdir(parents=True, exist_ok=True)

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            fh.seek(0)
            with open(dest, "wb") as f:
                f.write(fh.read())

            logger.info(f"File '{file_name}' downloaded successfully to '{dest}'.")
            return True
        except Exception as e:
            logger.warning(f"Google Drive download failed for '{file_name}': {e}")
            return False

    def backup_file(self, file_path: str | Path, folder_id: str | None = None) -> bool:
        """Helper method to back up a critical file to Google Drive non-blockingly."""
        res: Any = self.upload_file(file_path, folder_id=folder_id, overwrite=True)
        return bool(res)


GoogleDriveService = GDriveService
