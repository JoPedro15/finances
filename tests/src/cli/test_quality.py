"""Unit tests for CLI quality module in src/cli/quality.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.quality import _format_tier, app
from src.core.exceptions import StorageError
from src.core.models import (
    Asset,
    CountryExposure,
    ETFDetails,
    Holding,
    SectorExposure,
    StockDetails,
)

runner = CliRunner()


def test_format_tier() -> None:
    """Validates tier color formatting for Tier A, Tier B, and Tier C."""
    assert "Tier A" in _format_tier("Tier A").plain
    assert "Tier B" in _format_tier("Tier B").plain
    assert "Tier C" in _format_tier("Tier C").plain
    assert "Custom Tier" in _format_tier("Custom Tier").plain


@patch("src.cli.quality.SqlitePortfolioRepository")
def test_analyze_quality_repo_error_exits(mock_repo_cls: MagicMock) -> None:
    """Validates analyze-quality exits cleanly when repository loading fails."""
    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.side_effect = StorageError("DB error")
    mock_repo_cls.return_value = mock_repo

    result = runner.invoke(app, [])
    assert result.exit_code == 1


@patch("src.cli.quality.SqlitePortfolioRepository")
def test_analyze_quality_no_assets(mock_repo_cls: MagicMock) -> None:
    """Validates analyze-quality logs warning and returns when portfolio is empty."""
    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = []
    mock_repo_cls.return_value = mock_repo

    result = runner.invoke(app, [])
    assert result.exit_code == 0


@patch("src.cli.quality.SqlitePortfolioRepository")
def test_analyze_quality_ticker_not_found(mock_repo_cls: MagicMock) -> None:
    """Validates analyze-quality exits with error when requested ticker is missing."""
    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            yahoo_ticker="AAPL",
            isin="US0378331005",
            asset_type="STOCK",
            quantity=1.0,
            average_buy_price=100.0,
        )
    ]
    mock_repo_cls.return_value = mock_repo

    result = runner.invoke(app, ["TSLA"])
    assert result.exit_code == 1
    assert "not found in active portfolio" in result.output


@patch("src.cli.quality.StockProvider")
@patch("src.cli.quality.SqlitePortfolioRepository")
def test_analyze_quality_stock_success(
    mock_repo_cls: MagicMock, mock_stock_cls: MagicMock
) -> None:
    """Validates analyze-quality successfully renders card for a stock asset."""
    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            yahoo_ticker="AAPL",
            isin="US0378331005",
            asset_type="STOCK",
            quantity=1.0,
            average_buy_price=100.0,
        )
    ]
    mock_repo_cls.return_value = mock_repo

    mock_stock: MagicMock = MagicMock()
    mock_stock.get_details.return_value = StockDetails(
        pe_ratio=25.0,
        forward_pe=20.0,
        peg_ratio=1.2,
        price_to_book=5.0,
        dividend_yield_pct=0.5,
        beta=1.1,
        profit_margins_pct=18.0,
        revenue_growth_pct=10.0,
        earnings_growth_pct=12.0,
        total_debt_to_equity=50.0,
        fifty_two_week_high=200.0,
        fifty_two_week_low=100.0,
    )
    mock_stock_cls.return_value = mock_stock

    result = runner.invoke(app, ["AAPL"])
    assert result.exit_code == 0
    assert "Apple (AAPL)" in result.output


@patch("src.cli.quality.ETFProvider")
@patch("src.cli.quality.SqlitePortfolioRepository")
def test_analyze_quality_etf_success(
    mock_repo_cls: MagicMock, mock_etf_cls: MagicMock
) -> None:
    """Validates analyze-quality successfully renders card for an ETF asset."""
    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Vanguard",
            yahoo_ticker="VWCE.DE",
            isin="IE00BK5BQT36",
            asset_type="ETF",
            quantity=1.0,
            average_buy_price=100.0,
        )
    ]
    mock_repo_cls.return_value = mock_repo

    mock_etf: MagicMock = MagicMock()
    mock_etf.get_details.return_value = ETFDetails(
        ter_pct=0.22,
        holdings=[Holding(name="MSFT", isin="US1", ticker="MSFT", weight_pct=5.0)],
        sector_breakdown=[SectorExposure(sector_name="Tech", weight_pct=50.0)],
        country_breakdown=[CountryExposure(country_name="US", weight_pct=100.0)],
    )
    mock_etf_cls.return_value = mock_etf

    result = runner.invoke(app, ["VWCE.DE"])
    assert result.exit_code == 0
    assert "Vanguard (VWCE.DE)" in result.output
    assert "Total Expense Ratio (TER)" in result.output


@patch("src.cli.quality.StockProvider")
@patch("src.cli.quality.SqlitePortfolioRepository")
def test_analyze_quality_stock_provider_none(
    mock_repo_cls: MagicMock, mock_stock_cls: MagicMock
) -> None:
    """Validates analyze-quality handles missing
    fundamental stock details gracefully."""
    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Unknown",
            yahoo_ticker="UNKN",
            isin="US0000000001",
            asset_type="STOCK",
            quantity=1.0,
            average_buy_price=100.0,
        )
    ]
    mock_repo_cls.return_value = mock_repo

    mock_stock: MagicMock = MagicMock()
    mock_stock.get_details.return_value = None
    mock_stock_cls.return_value = mock_stock

    result = runner.invoke(app, ["UNKN"])
    assert result.exit_code == 0
    assert "Fundamental data unavailable" in result.output


@patch("src.cli.quality.ETFProvider")
@patch("src.cli.quality.SqlitePortfolioRepository")
def test_analyze_quality_etf_provider_none(
    mock_repo_cls: MagicMock, mock_etf_cls: MagicMock
) -> None:
    """Validates analyze-quality handles missing ETF metadata gracefully."""
    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Unknown ETF",
            yahoo_ticker="ETFX",
            isin="IE0000000000",
            asset_type="ETF",
            quantity=1.0,
            average_buy_price=100.0,
        )
    ]
    mock_repo_cls.return_value = mock_repo

    mock_etf: MagicMock = MagicMock()
    mock_etf.get_details.return_value = None
    mock_etf_cls.return_value = mock_etf

    result = runner.invoke(app, ["ETFX"])
    assert result.exit_code == 0
    assert "Metadata unavailable" in result.output
