"""Unit tests for main.py CLI commands using Typer's CliRunner."""

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
    StockDetails,
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


@patch("main.GoogleDriveService")
def test_pull_config_command_success(mock_gdrive_cls: MagicMock) -> None:
    """Tests 'pull-config' CLI command on successful download."""
    mock_service: MagicMock = MagicMock()
    mock_gdrive_cls.return_value = mock_service
    mock_service.download_file.return_value = True

    result: Any = runner.invoke(app, ["pull-config"])

    assert result.exit_code == 0
    assert "PULLING CONFIGURATION FROM GOOGLE DRIVE" in result.output
    assert mock_service.download_file.call_count == 2


@patch("main.GoogleDriveService")
def test_pull_config_command_failure(mock_gdrive_cls: MagicMock) -> None:
    """Tests 'pull-config' CLI command when download fails."""
    mock_service: MagicMock = MagicMock()
    mock_gdrive_cls.return_value = mock_service
    mock_service.download_file.return_value = False

    result: Any = runner.invoke(app, ["pull-config"])

    assert result.exit_code == 0
    assert "failed to download" in result.output


@patch("main.GoogleDriveService")
@patch("pathlib.Path.exists", return_value=True)
def test_push_config_command_success(
    mock_exists: MagicMock, mock_gdrive_cls: MagicMock
) -> None:
    """Tests 'push-config' CLI command on successful upload."""
    mock_service: MagicMock = MagicMock()
    mock_gdrive_cls.return_value = mock_service
    mock_service.upload_file.return_value = True

    result: Any = runner.invoke(app, ["push-config"])

    assert result.exit_code == 0
    assert "PUSHING CONFIGURATION TO GOOGLE DRIVE" in result.output
    assert mock_service.upload_file.call_count == 2


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


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_success(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'stock-details' CLI command on successful execution."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=1.0,
            average_buy_price=180.0,
            asset_type="stock",
        )
    ]

    mock_provider.get_details.return_value = StockDetails(
        sector="Technology",
        industry="Consumer Electronics",
        market_cap=3000000000000.0,
        pe_ratio=30.0,
        forward_pe=25.0,
        dividend_yield_pct=0.5,
        fifty_two_week_high=200.0,
        fifty_two_week_low=160.0,
    )

    result: Any = runner.invoke(app, ["stock-details", "AAPL"])

    assert result.exit_code == 0
    assert "STOCK DETAILS INSPECTION" in result.output
    assert "AAPL" in result.output
    assert "Technology" in result.output


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
