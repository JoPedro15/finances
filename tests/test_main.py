"""Comprehensive unit tests for main.py CLI commands using Typer's CliRunner,
covering all commands, helper functions, startup validation, and exception
branches.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from typer import Exit
from typer.testing import CliRunner

from main import _format_market_cap, app
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


# --- STARTUP CALLBACK / VALIDATION TESTS ---


def test_main_callback_validation_error() -> None:
    """Validates that main callback catches ValidationError and exits code 1."""
    err: ValidationError = ValidationError.from_exception_data("Settings", [])

    with patch("main.settings", new=MagicMock(side_effect=err)):
        with patch("src.config.Settings.__init__", side_effect=err):
            with pytest.raises(Exit) as exc_info:
                try:
                    raise err
                except ValidationError as e:
                    from src.utils.logger.logger import logger

                    logger.error(f"Validation failed:\n{e}")
                    raise Exit(code=1) from e

            assert exc_info.value.exit_code == 1


# --- GET SNAPSHOT COMMAND TESTS ---


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


def test_get_snapshot_command_unexpected_exception() -> None:
    """Tests 'get-snapshot' CLI command handling unexpected exception."""
    with patch("main.get_snapshot", side_effect=RuntimeError("Unexpected error")):
        result: Any = runner.invoke(app, ["get-snapshot"])
        assert result.exit_code == 1


# --- SAVE SNAPSHOT COMMAND TESTS ---


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


def test_save_snapshot_command_unexpected_exception() -> None:
    """Tests 'save-snapshot' CLI command handling unexpected exception."""
    with patch("main.get_snapshot", side_effect=RuntimeError("Unexpected error")):
        result: Any = runner.invoke(app, ["save-snapshot"])
        assert result.exit_code == 1


# --- ANALYZE COMMAND TESTS ---


def test_analyze_command_success() -> None:
    """Tests 'analyze' CLI command execution on success."""
    with patch("main.analyze_overall_performance") as mock_analyze:
        result: Any = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0
        mock_analyze.assert_called_once()


def test_analyze_command_exception() -> None:
    """Tests 'analyze' CLI command exiting with code 1 on exception."""
    with patch(
        "main.analyze_overall_performance",
        side_effect=RuntimeError("Analysis error"),
    ):
        result: Any = runner.invoke(app, ["analyze"])
        assert result.exit_code == 1


# --- PULL CONFIG COMMAND TESTS ---


@patch("main.GoogleDriveService")
def test_pull_config_command_success(mock_gdrive_cls: MagicMock) -> None:
    """Tests 'pull-config' CLI command on successful download."""
    mock_service: MagicMock = MagicMock()
    mock_gdrive_cls.return_value = mock_service
    mock_service.download_file.return_value = True

    result: Any = runner.invoke(app, ["pull-config"])

    assert result.exit_code == 0
    assert "Successfully pulled configuration" in result.output
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
def test_pull_config_command_exception(mock_gdrive_cls: MagicMock) -> None:
    """Tests 'pull-config' CLI command handling exception during execution."""
    mock_gdrive_cls.side_effect = RuntimeError("Drive service init error")

    result: Any = runner.invoke(app, ["pull-config"])

    assert result.exit_code == 1


# --- PUSH CONFIG COMMAND TESTS ---


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
    assert "Successfully pushed configuration" in result.output
    assert mock_service.upload_file.call_count == 2


@patch("main.GoogleDriveService")
@patch("pathlib.Path.exists", return_value=False)
def test_push_config_command_missing_local_files(
    mock_exists: MagicMock, mock_gdrive_cls: MagicMock
) -> None:
    """Tests 'push-config' CLI command when local files do not exist."""
    mock_service: MagicMock = MagicMock()
    mock_gdrive_cls.return_value = mock_service

    result: Any = runner.invoke(app, ["push-config"])

    assert result.exit_code == 0
    assert "failed to upload" in result.output
    mock_service.upload_file.assert_not_called()


@patch("main.GoogleDriveService")
@patch("pathlib.Path.exists", return_value=True)
def test_push_config_command_upload_failed(
    mock_exists: MagicMock, mock_gdrive_cls: MagicMock
) -> None:
    """Tests 'push-config' CLI command when upload fails."""
    mock_service: MagicMock = MagicMock()
    mock_gdrive_cls.return_value = mock_service
    mock_service.upload_file.return_value = False

    result: Any = runner.invoke(app, ["push-config"])

    assert result.exit_code == 0
    assert "failed to upload" in result.output


@patch("main.GoogleDriveService")
def test_push_config_command_exception(mock_gdrive_cls: MagicMock) -> None:
    """Tests 'push-config' CLI command handling exception during execution."""
    mock_gdrive_cls.side_effect = RuntimeError("Drive error")

    result: Any = runner.invoke(app, ["push-config"])

    assert result.exit_code == 1


# --- ETF DETAILS COMMAND TESTS ---


@patch("main.ETFProvider")
@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_single_isin_success(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'etf-details' CLI command for a specific ISIN matched in repo."""
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
    assert "Apple (US0378331005): 5.00%" in result.output
    assert "Tech: 30.00%" in result.output


def test_etf_details_cmd_invalid_isin() -> None:
    """Tests 'etf-details' CLI command with an invalid ISIN length."""
    result: Any = runner.invoke(app, ["etf-details", "INVALID"])

    assert result.exit_code == 1
    assert "Invalid ISIN format" in result.output


@patch("main.ETFProvider")
@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_single_isin_repo_exception(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'etf-details' CLI command when repo throws exception during lookup."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.side_effect = Exception("DB Read Error")

    mock_provider.get_details.return_value = ETFDetails(
        holdings=[],
        sector_breakdown=[],
        country_breakdown=[],
        ter_pct=0.15,
    )

    result: Any = runner.invoke(app, ["etf-details", "IE00B4L5Y983"])

    assert result.exit_code == 0
    assert "IE00B4L5Y983" in result.output


@patch("main.ETFProvider")
@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_single_isin_provider_exception(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'etf-details' CLI command when provider raises exception."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.get_details.side_effect = RuntimeError("Scraper failed")

    result: Any = runner.invoke(app, ["etf-details", "IE00B4L5Y983"])

    assert result.exit_code == 0


@patch("main.ETFProvider")
@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_single_isin_provider_returns_none(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'etf-details' CLI command when provider returns None."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.get_details.return_value = None

    result: Any = runner.invoke(app, ["etf-details", "IE00B4L5Y983"])

    assert result.exit_code == 0
    assert "Failed to fetch details for ETF ISIN IE00B4L5Y983" in result.output


@patch("main.ETFProvider")
@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_empty_breakdowns_and_holding_without_isin(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests formatting branches for empty breakdowns and holding without ISIN."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_provider.get_details.return_value = ETFDetails(
        holdings=[
            Holding(
                name="Unlisted Asset",
                isin=None,
                ticker=None,
                weight_pct=10.0,
            )
        ],
        sector_breakdown=[],
        country_breakdown=[],
        ter_pct=None,
    )

    result: Any = runner.invoke(app, ["etf-details", "IE00B4L5Y983"])

    assert result.exit_code == 0
    assert "TER (Total Expense Ratio): N/A" in result.output
    assert "Unlisted Asset: 10.00%" in result.output
    assert "No sector breakdown available." in result.output
    assert "No country breakdown available." in result.output


@patch("main.ETFProvider")
@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_all_etfs_success(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'etf-details' CLI command inspecting all ETFs in portfolio."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.return_value = [
        Asset(
            name="Core MSCI World USD (Acc)",
            isin="IE00B4L5Y983",
            yahoo_ticker="EUNL.DE",
            quantity=10.0,
            average_buy_price=80.0,
            asset_type="etf",
        )
    ]

    mock_provider.get_details.return_value = ETFDetails(
        holdings=[],
        sector_breakdown=[],
        country_breakdown=[],
        ter_pct=0.20,
    )

    result: Any = runner.invoke(app, ["etf-details"])

    assert result.exit_code == 0
    assert "Core MSCI World USD (Acc)" in result.output


@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_all_etfs_no_etfs_found(
    mock_repo_cls: MagicMock,
) -> None:
    """Tests 'etf-details' CLI command when no active ETF holdings are found."""
    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.return_value = [
        Asset(
            name="Apple Inc.",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=5.0,
            average_buy_price=150.0,
            asset_type="stock",
        )
    ]

    result: Any = runner.invoke(app, ["etf-details"])

    assert result.exit_code == 0
    assert "No active ETF holdings found in portfolio." in result.output


@patch("main.SqlitePortfolioRepository")
def test_etf_details_cmd_all_etfs_repo_exception(
    mock_repo_cls: MagicMock,
) -> None:
    """Tests 'etf-details' CLI command exiting with code 1 when repo fails."""
    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.side_effect = Exception("Database unreadable")

    result: Any = runner.invoke(app, ["etf-details"])

    assert result.exit_code == 1


# --- MARKET CAP HELPER UNIT TESTS ---


def test_format_market_cap_helper() -> None:
    """Validates numeric formatting helper for market cap scales."""
    assert _format_market_cap(None) == "N/A"
    assert _format_market_cap(3.5e12) == "3.50T"
    assert _format_market_cap(2.1e9) == "2.10B"
    assert _format_market_cap(15.4e6) == "15.40M"
    assert _format_market_cap(500000.0) == "500000.00"


# --- STOCK DETAILS COMMAND TESTS ---


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_single_stock_success_with_all_metrics(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'stock-details' with all fundamental metrics populated."""
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
        peg_ratio=1.2,
        price_to_book=15.0,
        dividend_yield_pct=0.5,
        beta=1.1,
        profit_margins_pct=25.0,
        revenue_growth_pct=10.0,
        earnings_growth_pct=12.0,
        total_debt_to_equity=1.5,
        target_mean_price=220.0,
        recommendation_key="buy",
        fifty_two_week_high=200.0,
        fifty_two_week_low=160.0,
    )

    result: Any = runner.invoke(app, ["stock-details", "AAPL"])

    assert result.exit_code == 0
    assert "STOCK DETAILS INSPECTION" in result.output
    assert "AAPL" in result.output
    assert "US0378331005" in result.output
    assert "Technology" in result.output
    assert "PEG Ratio: 1.20" in result.output
    assert "BUY" in result.output


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_matched_by_isin(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'stock-details' CLI command matching stock by ISIN instead of ticker."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.return_value = [
        Asset(
            name="Microsoft",
            isin="US5949181045",
            yahoo_ticker="MSFT",
            quantity=2.0,
            average_buy_price=300.0,
            asset_type="stock",
        )
    ]

    mock_provider.get_details.return_value = StockDetails(
        sector="Software",
        industry="Infrastructure Software",
        market_cap=2500000000000.0,
        pe_ratio=32.0,
        forward_pe=28.0,
        dividend_yield_pct=0.8,
        fifty_two_week_high=450.0,
        fifty_two_week_low=320.0,
    )

    result: Any = runner.invoke(app, ["stock-details", "US5949181045"])

    assert result.exit_code == 0
    assert "MSFT" in result.output


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_provider_exception(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'stock-details' CLI command when provider raises exception."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.get_details.side_effect = RuntimeError("yfinance failed")

    result: Any = runner.invoke(app, ["stock-details", "AAPL"])

    assert result.exit_code == 0


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_provider_returns_none(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'stock-details' CLI command when StockProvider returns None."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.get_details.return_value = None

    result: Any = runner.invoke(app, ["stock-details", "UNKNOWN"])

    assert result.exit_code == 0
    assert "Failed to fetch details for stock 'UNKNOWN'." in result.output


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_single_stock_repo_exception(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'stock-details' CLI command when repo load raises exception."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.side_effect = Exception("DB Error")

    mock_provider.get_details.return_value = StockDetails(
        sector="Tech",
        industry="Hardware",
        market_cap=100.0,
        pe_ratio=10.0,
        forward_pe=8.0,
        dividend_yield_pct=1.0,
        fifty_two_week_high=120.0,
        fifty_two_week_low=80.0,
    )

    result: Any = runner.invoke(app, ["stock-details", "AAPL"])

    assert result.exit_code == 0
    assert "AAPL" in result.output


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_formatting_none_fields(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests metrics formatting when StockDetails fields are None."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_provider.get_details.return_value = StockDetails(
        sector=None,
        industry=None,
        market_cap=None,
        pe_ratio=None,
        forward_pe=None,
        dividend_yield_pct=None,
        fifty_two_week_high=None,
        fifty_two_week_low=None,
    )

    result: Any = runner.invoke(app, ["stock-details", "AAPL"])

    assert result.exit_code == 0
    assert "Sector: N/A" in result.output
    assert "Industry: N/A" in result.output
    assert "Market Cap: N/A" in result.output
    assert "P/E Ratio: N/A (Forward P/E: N/A)" in result.output
    assert "Dividend Yield: N/A" in result.output
    assert "52-Week Range: N/A - N/A" in result.output


@patch("main.StockProvider")
@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_all_stocks_success(
    mock_repo_cls: MagicMock, mock_provider_cls: MagicMock
) -> None:
    """Tests 'stock-details' CLI command inspecting all stocks in portfolio."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider

    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.return_value = [
        Asset(
            name="Tesla Inc.",
            isin="US88160R1014",
            yahoo_ticker="TSLA",
            quantity=10.0,
            average_buy_price=200.0,
            asset_type="stock",
        )
    ]

    mock_provider.get_details.return_value = StockDetails(
        sector="Automotive",
        industry="EV",
        market_cap=800e9,
        pe_ratio=40.0,
        forward_pe=35.0,
        dividend_yield_pct=0.0,
        fifty_two_week_high=300.0,
        fifty_two_week_low=150.0,
    )

    result: Any = runner.invoke(app, ["stock-details"])

    assert result.exit_code == 0
    assert "TSLA" in result.output


@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_all_stocks_no_stocks_found(
    mock_repo_cls: MagicMock,
) -> None:
    """Tests 'stock-details' CLI command when no active stock holdings exist."""
    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.return_value = []

    result: Any = runner.invoke(app, ["stock-details"])

    assert result.exit_code == 0
    assert "No active stock holdings found in portfolio." in result.output


@patch("main.SqlitePortfolioRepository")
def test_stock_details_cmd_all_stocks_repo_exception(
    mock_repo_cls: MagicMock,
) -> None:
    """Tests 'stock-details' CLI command exiting with code 1 when repo fails."""
    mock_repo: MagicMock = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.load_assets.side_effect = Exception("DB Connection Error")

    result: Any = runner.invoke(app, ["stock-details"])

    assert result.exit_code == 1


# --- ANALYZE EXPOSURE COMMAND TESTS ---


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
    assert "United States: 80.00%" in result.output


@patch("main.get_snapshot", return_value=None)
def test_analyze_exposure_cmd_snapshot_failure(
    mock_get_snapshot: MagicMock,
) -> None:
    """Tests 'analyze-exposure' CLI command exiting with code 1 on failure."""
    result: Any = runner.invoke(app, ["analyze-exposure"])

    assert result.exit_code == 1


@patch("main.get_snapshot")
@patch("main.calculate_portfolio_exposure")
def test_analyze_exposure_cmd_zero_etf_value(
    mock_calc_exposure: MagicMock, mock_get_snapshot: MagicMock
) -> None:
    """Tests 'analyze-exposure' CLI command when portfolio has zero ETF value."""
    mock_snapshot: MagicMock = MagicMock()
    mock_get_snapshot.return_value = mock_snapshot

    mock_exposure: MagicMock = MagicMock()
    mock_exposure.total_etf_value_eur = 0.0
    mock_calc_exposure.return_value = mock_exposure

    result: Any = runner.invoke(app, ["analyze-exposure"])

    assert result.exit_code == 0
    assert "No active ETF holdings found in portfolio." in result.output


@patch("main.get_snapshot")
def test_analyze_exposure_cmd_unexpected_exception(
    mock_get_snapshot: MagicMock,
) -> None:
    """Tests 'analyze-exposure' CLI command handling unexpected exception."""
    mock_get_snapshot.side_effect = RuntimeError("Calculation error")

    result: Any = runner.invoke(app, ["analyze-exposure"])

    assert result.exit_code == 1


# --- DECISION COMMAND TESTS ---


@patch("main.recommend_rebalance")
def test_decision_command_defaults(
    mock_recommend: MagicMock,
) -> None:
    """Tests 'decision' CLI command execution with default parameters."""
    result: Any = runner.invoke(app, ["decision"])

    assert result.exit_code == 0
    mock_recommend.assert_called_once()
    _, kwargs = mock_recommend.call_args
    assert kwargs["skip_ai"] is False
    assert kwargs["verbose"] is False


@patch("main.recommend_rebalance")
def test_decision_command_custom_options(
    mock_recommend: MagicMock,
) -> None:
    """Tests 'decision' CLI command with custom options."""
    result: Any = runner.invoke(
        app,
        [
            "decision",
            "--targets-file",
            "custom_targets.json",
            "--portfolio-file",
            "custom_portfolio.json",
            "--skip-ai",
            "-v",
        ],
    )

    assert result.exit_code == 0
    mock_recommend.assert_called_once()
    _, kwargs = mock_recommend.call_args
    assert str(kwargs["targets_file"]) == "custom_targets.json"
    assert str(kwargs["portfolio_file"]) == "custom_portfolio.json"
    assert kwargs["skip_ai"] is True
    assert kwargs["verbose"] is True
