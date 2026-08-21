"""Unit tests for src/infra/gdrive/service.py covering Google Drive uploads,
downloads, batch synchronization, overwriting, file existence checks,
directory listing, and error handling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infra.gdrive.service import GDriveService


def test_init_raises_file_not_found_when_creds_missing(tmp_path: Path) -> None:
    """Validates GDriveService init fails if credentials file is missing."""
    missing_creds: Path = tmp_path / "credentials.json"

    with pytest.raises(FileNotFoundError, match="Missing Google credentials file:"):
        GDriveService(
            credentials_path=str(missing_creds),
            token_path=str(tmp_path / "token.json"),
        )


@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_get_service_returns_none_when_creds_fail(
    mock_get_creds: MagicMock, tmp_path: Path
) -> None:
    """Validates _get_service returns None when credential loading fails."""
    mock_get_creds.return_value = None
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    service: GDriveService = GDriveService(credentials_path=str(creds_file))
    assert service._get_service() is None


@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_get_service_build_exception(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates _get_service handles build exceptions gracefully."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_get_creds.return_value = MagicMock()
    mock_build.side_effect = Exception("Build API failure")

    service: GDriveService = GDriveService(credentials_path=str(creds_file))
    assert service._get_service() is None


@patch("src.infra.gdrive.service.GDriveService._get_service")
def test_operations_when_service_is_none(
    mock_get_service: MagicMock, tmp_path: Path
) -> None:
    """Validates API methods return default empty/None when service is None."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_get_service.return_value = None
    service: GDriveService = GDriveService(credentials_path=str(creds_file))

    assert service.file_exists("test.db") is False
    assert service.list_files() == []
    assert service.upload_file(creds_file) is None
    assert service.download_file("test.db", tmp_path / "out.db") is False


@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_file_exists_scenarios(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates file_exists handles hits, misses, and API exceptions."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value

    service: GDriveService = GDriveService(credentials_path=str(creds_file))

    # 1. File exists
    mock_files.list.return_value.execute.return_value = {"files": [{"id": "123"}]}
    assert service.file_exists("test.db", folder_id="f123") is True

    # 2. File does not exist
    mock_files.list.return_value.execute.return_value = {"files": []}
    assert service.file_exists("missing.db") is False

    # 3. Exception thrown
    mock_files.list.return_value.execute.side_effect = Exception("API error")
    assert service.file_exists("error.db") is False


@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_list_files_scenarios(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates list_files formatting and exception fallback."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value

    service: GDriveService = GDriveService(credentials_path=str(creds_file))

    # 1. Success
    mock_files.list.return_value.execute.return_value = {
        "files": [{"id": "1", "name": "a.db"}, {"id": "2", "name": "b.db"}]
    }
    result = service.list_files(folder_id="f123", limit=2)
    assert len(result) == 2
    assert result[0] == {"id": "1", "name": "a.db"}

    # 2. Exception
    mock_files.list.return_value.execute.side_effect = Exception("List failed")
    assert service.list_files() == []


@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_upload_file_new_and_missing(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates upload_file handles missing local files and creates new uploads."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    service: GDriveService = GDriveService(credentials_path=str(creds_file))

    # 1. Non-existent local file
    assert service.upload_file(tmp_path / "missing.txt") is None

    # 2. Upload new local file (overwrite=False)
    sample_file: Path = tmp_path / "sample.txt"
    sample_file.write_text("content", encoding="utf-8")

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value
    mock_files.create.return_value.execute.return_value = {
        "id": "new_id",
        "name": "sample.txt",
    }

    assert service.upload_file(sample_file, folder_id="folder_1") == "new_id"


@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_upload_file_overwrite_existing_and_new(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates upload_file updates existing files
    or creates new when overwrite=True."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    sample_file: Path = tmp_path / "existing.txt"
    sample_file.write_text("updated content", encoding="utf-8")

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value

    # 1. File exists on drive -> updates
    mock_files.list.return_value.execute.return_value = {
        "files": [{"id": "existing_id"}]
    }
    mock_files.update.return_value.execute.return_value = {"id": "existing_id"}

    service: GDriveService = GDriveService(credentials_path=str(creds_file))
    res = service.upload_file(sample_file, folder_id="folder_1", overwrite=True)

    assert res == "existing_id"
    mock_files.update.assert_called_once()

    # 2. File does not exist on drive with overwrite=True -> creates new
    mock_files.list.return_value.execute.return_value = {"files": []}
    mock_files.create.return_value.execute.return_value = {"id": "created_override_id"}

    res2 = service.upload_file(sample_file, folder_id="folder_1", overwrite=True)
    assert res2 == "created_override_id"


@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_upload_file_api_exception(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates upload_file handles API exceptions during create/update."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    sample_file: Path = tmp_path / "data.db"
    sample_file.write_text("dummy", encoding="utf-8")

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value
    mock_files.create.side_effect = Exception("API Upload Error")

    service: GDriveService = GDriveService(credentials_path=str(creds_file))
    assert service.upload_file(sample_file) is None


@patch("src.infra.gdrive.service.MediaIoBaseDownload")
@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_download_file_success_and_not_found(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    mock_download_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates download_file when file is found vs when missing on Drive."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value

    service: GDriveService = GDriveService(credentials_path=str(creds_file))

    # 1. File not found
    mock_files.list.return_value.execute.return_value = {"files": []}
    dest_file: Path = tmp_path / "dest.txt"
    assert service.download_file("missing.txt", dest_file) is False

    # 2. File found and downloaded
    mock_files.list.return_value.execute.return_value = {"files": [{"id": "dl_id"}]}
    mock_downloader = MagicMock()
    mock_downloader.next_chunk.return_value = (None, True)
    mock_download_cls.return_value = mock_downloader

    assert service.download_file("found.txt", dest_file) is True
    assert dest_file.exists()


@patch("src.infra.gdrive.service.MediaIoBaseDownload")
@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_download_file_creates_parent_directories(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    mock_download_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates download_file creates nested destination parent directories."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value
    mock_files.list.return_value.execute.return_value = {"files": [{"id": "dl_id"}]}

    mock_downloader = MagicMock()
    mock_downloader.next_chunk.return_value = (None, True)
    mock_download_cls.return_value = mock_downloader

    service: GDriveService = GDriveService(credentials_path=str(creds_file))
    nested_dest: Path = tmp_path / "nested" / "sub" / "output.db"

    assert service.download_file("found.txt", nested_dest) is True
    assert nested_dest.exists()


@patch("src.infra.gdrive.service.build")
@patch("src.infra.gdrive.service.get_google_service_credentials")
def test_download_file_downloader_exception(
    mock_get_creds: MagicMock,
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates download_file handles chunk downloader exceptions."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_service: MagicMock = MagicMock()
    mock_build.return_value = mock_service
    mock_files: MagicMock = mock_service.files.return_value
    mock_files.list.return_value.execute.return_value = {"files": [{"id": "dl_123"}]}
    mock_files.get_media.side_effect = Exception("Network interrupted")

    service: GDriveService = GDriveService(credentials_path=str(creds_file))
    dest_path: Path = tmp_path / "downloaded.db"

    assert service.download_file("data.db", dest_path) is False


@patch("src.infra.gdrive.service.GDriveService.download_file")
def test_sync_files_pull_success(mock_download: MagicMock, tmp_path: Path) -> None:
    """Validates sync_files in 'pull' direction calls download_file for each path."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_download.return_value = True
    service: GDriveService = GDriveService(credentials_path=str(creds_file))

    file_paths: list[Path] = [tmp_path / "portfolio.json", tmp_path / "finances.db"]
    results: dict[str, bool] = service.sync_files(file_paths, direction="pull")

    assert results["portfolio.json"] is True
    assert results["finances.db"] is True


@patch("src.infra.gdrive.service.GDriveService.upload_file")
def test_sync_files_push_success(mock_upload: MagicMock, tmp_path: Path) -> None:
    """Validates sync_files in 'push' direction uploads each file with overwrite."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    mock_upload.return_value = "file_id"
    service: GDriveService = GDriveService(credentials_path=str(creds_file))

    file_paths: list[Path] = [tmp_path / "portfolio.json"]
    results: dict[str, bool] = service.sync_files(file_paths, direction="push")

    assert results["portfolio.json"] is True
    mock_upload.assert_called_once_with(file_paths[0], overwrite=True)


def test_sync_files_invalid_direction(tmp_path: Path) -> None:
    """Validates sync_files handles invalid direction gracefully."""
    creds_file: Path = tmp_path / "credentials.json"
    creds_file.touch()

    service: GDriveService = GDriveService(credentials_path=str(creds_file))
    results: dict[str, bool] = service.sync_files(
        [tmp_path / "portfolio.json"], direction="invalid"
    )

    assert results["portfolio.json"] is False
