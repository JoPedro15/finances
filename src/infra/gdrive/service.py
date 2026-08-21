"""
Service wrapper for Google Drive file upload, download, and backup operations.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path

from googleapiclient.discovery import Resource, build  # type: ignore[import-untyped]
from googleapiclient.http import (  # type: ignore[import-untyped]
    MediaFileUpload,
    MediaIoBaseDownload,
)

from src.config import settings
from src.infra.gdrive.auth import get_google_service_credentials
from src.utils.logger.logger import logger


class GDriveService:
    """Service wrapper for Google Drive operations."""

    def __init__(
        self,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        folder_id: str | None = None,
    ) -> None:
        if credentials_path and not Path(credentials_path).exists():
            raise FileNotFoundError(
                f"Missing Google credentials file: {credentials_path}"
            )

        self.credentials_path = credentials_path
        self.token_path = token_path
        # Ensures folder_id defaults to the config defined in .env
        self.folder_id: str | None = folder_id or settings.gdrive_config_folder_id
        self._service: Resource | None = None

    def _get_service(self) -> Resource | None:
        if self._service is None:
            try:
                creds = get_google_service_credentials(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                )
                if not creds:
                    logger.warning("No valid Google Drive credentials available.")
                    return None
                self._service = build("drive", "v3", credentials=creds)
            except Exception as e:
                logger.error(f"Failed to build Google Drive API service: {e}")
                return None
        return self._service

    def file_exists(self, file_name: str, folder_id: str | None = None) -> bool:
        """Checks whether a file exists on Google Drive."""
        service = self._get_service()
        if not service:
            return False

        target_folder = folder_id or self.folder_id
        query = f"name = '{file_name}' and trashed = false"
        if target_folder:
            query += f" and '{target_folder}' in parents"

        try:
            response: dict[str, list[dict[str, str]]] = (
                service.files().list(q=query, fields="files(id)").execute()
            )
            return len(response.get("files", [])) > 0
        except Exception as e:
            logger.error(f"Failed to check file existence for '{file_name}': {e}")
            return False

    def list_files(
        self, folder_id: str | None = None, limit: int = 100
    ) -> list[dict[str, str]]:
        """Lists files in a Google Drive folder."""
        service = self._get_service()
        if not service:
            return []

        target_folder = folder_id or self.folder_id
        query = "trashed = false"
        if target_folder:
            query = f"'{target_folder}' in parents and trashed = false"

        try:
            response: dict[str, list[dict[str, str]]] = (
                service.files()
                .list(q=query, pageSize=limit, fields="files(id, name)")
                .execute()
            )
            return response.get("files", [])
        except Exception as e:
            logger.error(f"Failed to list Google Drive files: {e}")
            return []

    def upload_file(
        self,
        file_path: str | Path,
        folder_id: str | None = None,
        overwrite: bool = False,
        mime_type: str = "application/octet-stream",
    ) -> str | None:
        """Uploads or updates a file on Google Drive, returning the File ID."""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Cannot upload non-existent file '{path}'.")
            return None

        service = self._get_service()
        if not service:
            return None

        # Fallback to default folder_id from configuration settings if not specified
        target_folder = folder_id or self.folder_id
        media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)

        try:
            if overwrite:
                query = f"name = '{path.name}' and trashed = false"
                if target_folder:
                    query += f" and '{target_folder}' in parents"

                existing_resp: dict[str, list[dict[str, str]]] = (
                    service.files().list(q=query, fields="files(id)").execute()
                )
                existing_files = existing_resp.get("files", [])

                if existing_files:
                    file_id = existing_files[0]["id"]
                    service.files().update(
                        fileId=file_id,
                        media_body=media,
                    ).execute()
                    logger.info(f"File '{path.name}' updated on Google Drive.")
                    return file_id

            file_metadata = {
                "name": path.name,
                "parents": [target_folder] if target_folder else [],
            }
            created_file: dict[str, str] = (
                service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            logger.info(f"File '{path.name}' uploaded successfully.")
            return created_file.get("id")
        except Exception as e:
            logger.error(f"Google Drive upload failed for '{path.name}': {e}")
            return None

    def download_file(
        self,
        file_name: str,
        destination_path: str | Path,
        folder_id: str | None = None,
    ) -> bool:
        """Downloads a file from Google Drive to local disk."""
        dest = Path(destination_path)
        service = self._get_service()
        if not service:
            return False

        # Use explicitly provided folder_id or fallback to settings
        target_folder = folder_id or self.folder_id
        query = f"name = '{file_name}' and trashed = false"
        if target_folder:
            query += f" and '{target_folder}' in parents"

        try:
            response: dict[str, list[dict[str, str]]] = (
                service.files().list(q=query, fields="files(id)").execute()
            )
            files = response.get("files", [])
            if not files:
                logger.warning(
                    f"File '{file_name}' not found in Google Drive "
                    f"folder '{target_folder}'."
                )
                return False

            file_id = files[0]["id"]
            request = service.files().get_media(fileId=file_id)
            dest.parent.mkdir(parents=True, exist_ok=True)

            with io.BytesIO() as fh:
                downloader = MediaIoBaseDownload(fh, request)
                while not downloader.next_chunk()[1]:
                    pass
                dest.write_bytes(fh.getvalue())

            logger.info(f"File '{file_name}' downloaded successfully to '{dest}'.")
            return True
        except Exception as e:
            logger.error(f"Google Drive download failed for '{file_name}': {e}")
            return False

    def backup_file(self, file_path: str | Path, folder_id: str | None = None) -> bool:
        """Backs up a local file to Google Drive using overwrite mode."""
        return (
            self.upload_file(file_path, folder_id=folder_id, overwrite=True) is not None
        )

    def sync_files(
        self, file_paths: Sequence[str | Path], direction: str = "pull"
    ) -> dict[str, bool]:
        """Batch synchronize files."""
        results: dict[str, bool] = {}
        for file_path in file_paths:
            path = Path(file_path)
            try:
                if direction == "pull":
                    # Downloading assumes the file should be in the Config Folder
                    results[path.name] = self.download_file(path.name, path)
                elif direction == "push":
                    # Uploading forces overwrite to keep Cloud as the SSOT
                    results[path.name] = (
                        self.upload_file(path, overwrite=True) is not None
                    )
                else:
                    raise ValueError(f"Invalid direction: {direction}")
            except Exception as e:
                logger.error(f"Sync failed for {path.name}: {e}")
                results[path.name] = False
        return results


# Backward compatibility alias
GoogleDriveService = GDriveService
