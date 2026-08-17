"""
Unit tests for main.py CLI commands using Typer's CliRunner.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from main import app
from src.core.models import (
    Asset,
    CountryExposure,
    ETFDetails,
    Holding,
    PortfolioSnapshot,
    SectorExposure,
)

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
        result: Any = runner.invoke(app, ["get-snapshot"])
        assert result.exit_code == 0
        mock_display.assert_called_once_with(mock_snapshot)


def test_get_snapshot_command_failure() -> None:
    """Tests 'get-snapshot' CLI command exiting with code 1 on failure."""
    with patch("main.get_snapshot", return_value=None):
        result: Any = runner.invoke(app, ["get-snapshot"])
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
        result: Any = runner.invoke(app, ["save-snapshot"])
        assert result.exit_code == 0
        mock_save.assert_called_once_with(mock_snapshot)


def test_save_snapshot_command_failure() -> None:
    """Tests 'save-snapshot' CLI command exiting with code 1 on failure."""
    with patch("main.get_snapshot", return_value=None):
        result: Any = runner.invoke(app, ["save-snapshot"])
        assert result.exit_code == 1


def test_analyze_command() -> None:
    """Tests 'analyze' CLI command execution."""
    with patch("main.analyze_overall_performance") as mock_analyze:
        result: Any = runner.invoke(app, ["analyze"])
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
        result: Any = runner.invoke(app, ["check-dips"])
        assert result.exit_code == 0
        assert "Found 1 dip opportunities" in result.output


def test_check_dips_command_empty_watchlist() -> None:
    """Tests 'check-dips' CLI command when watchlist fails to load."""
    with patch("main.load_watchlist", return_value=[]):
        result: Any = runner.invoke(app, ["check-dips"])
        assert result.exit_code == 1


@patch("main.ETFProvider")
@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_success(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'etf-details' CLI command on successful execution."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.return_value = [
        Asset(
            name="Core MSCI World USD (Acc)",
            isin="IE00B4L5Y983",
            yahoo_ticker="EUNL.DE",
            quantity=1.0,
            average_buy_price=90.0,
            asset_type="etf",
        )
    ]

    mock_provider.get_details.return_value = ETFDetails(
        holdings=[
            Holding(
                name="Apple",
                isin="US0378331005",
                ticker="AAPL",
                weight_pct=5.0,
            )
        ],
        sector_breakdown=[SectorExposure(sector_name="Tech", weight_pct=30.0)],
        country_breakdown=[CountryExposure(country_name="USA", weight_pct=70.0)],
        ter_pct=0.20,
    )

    result: Any = runner.invoke(app, ["etf-details", "IE00B4L5Y983"])

    assert result.exit_code == 0
    assert "ETF DETAILS INSPECTION" in result.output
    assert "IE00B4L5Y983" in result.output
    assert "Core MSCI World USD (Acc)" in result.output
    assert "Apple" in result.output
    assert "Tech: 30.00%" in result.output


def test_etf_details_cmd_invalid_isin() -> None:
    """Tests 'etf-details' CLI command with an invalid ISIN format."""
    result: Any = runner.invoke(app, ["etf-details", "INVALID"])

    assert result.exit_code == 1
    assert "Invalid ISIN format" in result.output


@patch("main.get_snapshot")
@patch("main.calculate_portfolio_exposure")
def test_analyze_exposure_cmd_success(
    mock_calc_exposure: MagicMock, mock_get_snapshot: MagicMock
) -> None:
    """Tests 'analyze-exposure' CLI command on successful execution."""
    mock_snapshot: MagicMock = MagicMock()
    mock_get_snapshot.return_value = mock_snapshot

    mock_exposure: MagicMock = MagicMock()
    mock_exposure.total_etf_value_eur = 1000.0
    mock_exposure.sector_exposure = {"Technology": 60.0}
    mock_exposure.country_exposure = {"United States": 80.0}
    mock_calc_exposure.return_value = mock_exposure

    result: Any = runner.invoke(app, ["analyze-exposure"])

    assert result.exit_code == 0
    assert "ANALYZING CONSOLIDATED PORTFOLIO EXPOSURE" in result.output
    assert "Technology: 60.00%" in result.output
