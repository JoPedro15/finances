# tests/test_gdrive_service.py

from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

from utils.gdrive.service import GDriveService


def test_init_raises_file_not_found_when_creds_missing(tmp_path: Path) -> None:
    """Tests that GDriveService initialization fails if credentials file is missing."""
    missing_creds: Path = tmp_path / "credentials.json"
    token_path: Path = tmp_path / "token.json"

    with pytest.raises(FileNotFoundError, match="Missing Google credentials:"):
        GDriveService(
            credentials_path=str(missing_creds),
            token_path=str(token_path),
        )


@patch("utils.gdrive.service.build")
@patch("utils.gdrive.service.get_google_service_credentials")
def test_upload_file_new(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Tests uploading a new file to Google Drive."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}', encoding="utf-8")

    dummy_file: Path = tmp_path / "sample.txt"
    dummy_file.write_text("hello world", encoding="utf-8")

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value

    mock_files.create.return_value.execute.return_value = {"id": "new_file_id"}

    service: GDriveService = GDriveService(
        credentials_path=str(creds_file),
        token_path=str(tmp_path / "token.json"),
    )

    file_id: str = service.upload_file(
        file_path=dummy_file,
        folder_id="folder_123",
        overwrite=False,
    )

    assert file_id == "new_file_id"
    mock_files.create.assert_called_once()


@patch("utils.gdrive.service.build")
@patch("utils.gdrive.service.get_google_service_credentials")
def test_upload_file_overwrite(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Tests overwriting an existing file in Google Drive."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}', encoding="utf-8")

    dummy_file: Path = tmp_path / "sample.txt"
    dummy_file.write_text("hello world", encoding="utf-8")

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value

    mock_files.list.return_value.execute.return_value = {
        "files": [{"id": "existing_id"}]
    }
    mock_files.update.return_value.execute.return_value = {"id": "existing_id"}

    service: GDriveService = GDriveService(
        credentials_path=str(creds_file),
        token_path=str(tmp_path / "token.json"),
    )

    file_id: str = service.upload_file(
        file_path=dummy_file,
        folder_id="folder_123",
        overwrite=True,
    )

    assert file_id == "existing_id"
    mock_files.update.assert_called_once()


@patch("utils.gdrive.service.build")
@patch("utils.gdrive.service.get_google_service_credentials")
def test_file_exists_returns_true(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Tests file_exists method returning True when file exists."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}', encoding="utf-8")

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value
    mock_files.list.return_value.execute.return_value = {"files": [{"id": "some_id"}]}

    service: GDriveService = GDriveService(
        credentials_path=str(creds_file),
        token_path=str(tmp_path / "token.json"),
    )

    exists: bool = service.file_exists("test.json", "folder_123")
    assert exists is True


@patch("utils.gdrive.service.build")
@patch("utils.gdrive.service.get_google_service_credentials")
def test_list_files(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Tests listing files inside a target Google Drive folder."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}', encoding="utf-8")

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value
    mock_files.list.return_value.execute.return_value = {
        "files": [
            {"id": "id_1", "name": "file1.txt"},
            {"id": "id_2", "name": "file2.txt"},
        ]
    }

    service: GDriveService = GDriveService(
        credentials_path=str(creds_file),
        token_path=str(tmp_path / "token.json"),
    )

    files: List[Dict[str, str]] = service.list_files(folder_id="folder_123", limit=5)
    assert len(files) == 2
    assert files[0]["name"] == "file1.txt"
