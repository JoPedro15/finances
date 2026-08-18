"""
Unit tests for the Google Drive automated backup workflow.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.models import PortfolioSnapshot
from src.core.snapshot import save_snapshot, trigger_gdrive_backup


def test_trigger_gdrive_backup_success() -> None:
    """Verifies that trigger_gdrive_backup returns True upon successful upload."""
    with patch("src.infra.gdrive.service.GoogleDriveService") as mock_service_cls:
        mock_instance: MagicMock = MagicMock()
        mock_instance.backup_file.return_value = True
        mock_service_cls.return_value = mock_instance

        result: bool = trigger_gdrive_backup(Path("data/finances.db"))
        assert result is True
        mock_instance.backup_file.assert_called_once_with(Path("data/finances.db"))


def test_trigger_gdrive_backup_failure_handling() -> None:
    """Verifies that trigger_gdrive_backup handles exceptions
    gracefully and returns False."""
    with patch("src.infra.gdrive.service.GoogleDriveService") as mock_service_cls:
        mock_instance: MagicMock = MagicMock()
        mock_instance.backup_file.side_effect = Exception("API Network Timeout")
        mock_service_cls.return_value = mock_instance

        result: bool = trigger_gdrive_backup(Path("data/finances.db"))
        assert result is False


def test_save_snapshot_triggers_backup() -> None:
    """Verifies that save_snapshot invokes Google Drive backup when enabled."""
    mock_history_repo: MagicMock = MagicMock()
    dummy_snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-17T19:00:00",
        total_value_eur=1000.0,
        assets_snapshot=[],
    )

    with patch("src.core.snapshot.trigger_gdrive_backup") as mock_backup:
        with patch.object(Path, "exists", return_value=True):
            save_snapshot(
                dummy_snapshot, history_repo=mock_history_repo, backup_to_gdrive=True
            )

            mock_history_repo.save_snapshot.assert_called_once_with(dummy_snapshot)
            assert mock_backup.call_count >= 1


def test_save_snapshot_disabled_backup() -> None:
    """Verifies that save_snapshot skips Google Drive
    backup when backup_to_gdrive is False."""
    mock_history_repo: MagicMock = MagicMock()
    dummy_snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-17T19:00:00",
        total_value_eur=1000.0,
        assets_snapshot=[],
    )

    with patch("src.core.snapshot.trigger_gdrive_backup") as mock_backup:
        save_snapshot(
            dummy_snapshot, history_repo=mock_history_repo, backup_to_gdrive=False
        )

        mock_history_repo.save_snapshot.assert_called_once_with(dummy_snapshot)
        mock_backup.assert_not_called()
