"""Unit tests for PortfolioDashboardPresenter class."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from src.cli.portfolio_dashboard import PortfolioDashboardPresenter
from src.core.models import (
    AssetPerformanceSummary,
    AssetTimeSeries,
    DashboardOverview,
    PortfolioTimeSeries,
    TimeSeriesPoint,
)


def test_render_full_dashboard(tmp_path: Path) -> None:
    """Validates full dashboard rendering output."""
    console: Console = Console(record=True, width=120)
    presenter: PortfolioDashboardPresenter = PortfolioDashboardPresenter(
        console=console
    )

    portfolio_ts: PortfolioTimeSeries = PortfolioTimeSeries(
        value_history=[TimeSeriesPoint(date="2026-08-22", value=10000.0)]
    )
    summary: AssetPerformanceSummary = AssetPerformanceSummary(
        ticker="AAPL",
        name="Apple Inc.",
        asset_type="STOCK",
        latest_quantity=10.0,
        latest_value_eur=2000.0,
        cost_basis_eur=1500.0,
        roi_eur=500.0,
        roi_percent=33.33,
        portfolio_share_percent=20.0,
    )
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=portfolio_ts,
        asset_series=[],
        class_series=[],
        asset_summaries=[summary],
        top_growth_contributor="AAPL",
        max_drawdown_percent=-2.5,
    )

    presenter.render_full_dashboard(overview)
    output: str = console.export_text()

    assert "GLOBAL PORTFOLIO EXECUTIVE SUMMARY" in output
    assert "asset positions & performance breakdown" in output.lower()
    assert "10,000.00 €" in output
    assert "AAPL" in output


def test_render_executive_panel_negative_roi() -> None:
    """Validates executive panel rendering when ROI is negative."""
    console: Console = Console(record=True, width=120)
    presenter: PortfolioDashboardPresenter = PortfolioDashboardPresenter(
        console=console
    )

    portfolio_ts: PortfolioTimeSeries = PortfolioTimeSeries(
        value_history=[TimeSeriesPoint(date="2026-08-22", value=800.0)]
    )
    summary: AssetPerformanceSummary = AssetPerformanceSummary(
        ticker="TSLA",
        name="Tesla",
        asset_type="STOCK",
        latest_quantity=5.0,
        latest_value_eur=800.0,
        cost_basis_eur=1000.0,
        roi_eur=-200.0,
        roi_percent=-20.0,
        portfolio_share_percent=100.0,
    )
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=portfolio_ts,
        asset_series=[],
        class_series=[],
        asset_summaries=[summary],
        top_growth_contributor=None,
        max_drawdown_percent=-15.0,
    )

    presenter.render_executive_panel(overview)
    output: str = console.export_text()

    assert "Total Portfolio Value:" in output
    assert "-200.00 €" in output


def test_render_asset_detail_panel() -> None:
    """Validates individual asset detail panel rendering."""
    console: Console = Console(record=True, width=120)
    presenter: PortfolioDashboardPresenter = PortfolioDashboardPresenter(
        console=console
    )

    summary: AssetPerformanceSummary = AssetPerformanceSummary(
        ticker="VWCE.DE",
        name="Vanguard All-World",
        asset_type="ETF",
        latest_quantity=50.0,
        latest_value_eur=5000.0,
        cost_basis_eur=4500.0,
        roi_eur=500.0,
        roi_percent=11.11,
        portfolio_share_percent=50.0,
    )
    ts: AssetTimeSeries = AssetTimeSeries(
        ticker="VWCE.DE",
        name="Vanguard All-World",
        asset_type="ETF",
        value_history=[TimeSeriesPoint(date="2026-08-22", value=5000.0)],
    )

    presenter.render_asset_detail_panel(summary, ts)
    output: str = console.export_text()

    assert "ASSET DETAIL ANALYSIS - VWCE.DE" in output
    assert "Vanguard All-World" in output
    assert "Historical Snapshots Count: 1" in output


def test_export_assets_csv(tmp_path: Path) -> None:
    """Validates CSV export with positive and negative ROI items."""
    presenter: PortfolioDashboardPresenter = PortfolioDashboardPresenter()
    csv_file: Path = tmp_path / "test_export.csv"

    summaries: list[AssetPerformanceSummary] = [
        AssetPerformanceSummary(
            ticker="AAPL",
            name="Apple",
            asset_type="STOCK",
            latest_quantity=10.0,
            latest_value_eur=2000.0,
            cost_basis_eur=1500.0,
            roi_eur=500.0,
            roi_percent=33.33,
            portfolio_share_percent=50.0,
        ),
        AssetPerformanceSummary(
            ticker="TSLA",
            name="Tesla",
            asset_type="STOCK",
            latest_quantity=5.0,
            latest_value_eur=800.0,
            cost_basis_eur=1000.0,
            roi_eur=-200.0,
            roi_percent=-20.0,
            portfolio_share_percent=50.0,
        ),
    ]

    result_path: Path = presenter.export_assets_csv(summaries, csv_file)
    assert result_path.exists()

    content: str = result_path.read_text(encoding="utf-8")
    assert "AAPL" in content
    assert "+500.00" in content
    assert "TSLA" in content
    assert "-200.00" in content
