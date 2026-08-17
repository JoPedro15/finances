"""
Unit tests for main.py CLI commands using Typer's CliRunner.
"""

from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from main import app
from src.core.models import PortfolioSnapshot

runner: CliRunner = CliRunner()


def test_get_snapshot_command_success() -> None:
    """Tests 'get-snapshot' CLI command on successful execution."""
    mock_snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-16T20:00:00",
        total_value_eur=1000.0,
        assets_snapshot=[],
    )
    with (
        patch("main.get_snapshot", return_value=mock_snapshot),
        patch("main.display_snapshot") as mock_display,
    ):
        result = runner.invoke(app, ["get-snapshot"])
        assert result.exit_code == 0
        mock_display.assert_called_once_with(mock_snapshot)


def test_get_snapshot_command_failure() -> None:
    """Tests 'get-snapshot' CLI command exiting with code 1 on failure."""
    with patch("main.get_snapshot", return_value=None):
        result = runner.invoke(app, ["get-snapshot"])
        assert result.exit_code == 1


def test_save_snapshot_command_success() -> None:
    """Tests 'save-snapshot' CLI command on successful execution."""
    mock_snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-16T20:00:00",
        total_value_eur=1000.0,
        assets_snapshot=[],
    )
    with (
        patch("main.get_snapshot", return_value=mock_snapshot),
        patch("main.save_snapshot") as mock_save,
    ):
        result = runner.invoke(app, ["save-snapshot"])
        assert result.exit_code == 0
        mock_save.assert_called_once_with(mock_snapshot)


def test_save_snapshot_command_failure() -> None:
    """Tests 'save-snapshot' CLI command exiting with code 1 on failure."""
    with patch("main.get_snapshot", return_value=None):
        result = runner.invoke(app, ["save-snapshot"])
        assert result.exit_code == 1


def test_analyze_command() -> None:
    """Tests 'analyze' CLI command execution."""
    with patch("main.analyze_overall_performance") as mock_analyze:
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0
        mock_analyze.assert_called_once()


def test_check_dips_command_success() -> None:
    """Tests 'check-dips' CLI command with matches found."""
    mock_watchlist: list[dict[str, str]] = [{"name": "Apple", "ticker": "AAPL"}]
    mock_matches: list[dict[str, Any]] = [
        {"name": "Apple", "ticker": "AAPL", "drop_pct": 7.0}
    ]
    with (
        patch("main.load_watchlist", return_value=mock_watchlist),
        patch("main.scan_watchlist", return_value=mock_matches),
    ):
        result = runner.invoke(app, ["check-dips"])
        assert result.exit_code == 0
        assert "Found 1 dip opportunities" in result.output


def test_check_dips_command_empty_watchlist() -> None:
    """Tests 'check-dips' CLI command when watchlist fails to load."""
    with patch("main.load_watchlist", return_value=[]):
        result = runner.invoke(app, ["check-dips"])
        assert result.exit_code == 1
