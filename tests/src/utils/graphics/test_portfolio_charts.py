"""Unit tests for PortfolioChartExporter class."""

from __future__ import annotations

from pathlib import Path

from src.core.models import (
    AssetClassTimeSeries,
    DashboardOverview,
    PortfolioTimeSeries,
    TimeSeriesPoint,
)
from src.utils.graphics.portfolio_charts import PortfolioChartExporter


def test_init_accepts_str_path(tmp_path: Path) -> None:
    """Validates initialization with string path."""
    str_path: str = str(tmp_path / "str_plots")
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=str_path)
    assert exporter.output_dir == Path(str_path)


def test_export_portfolio_valuation_chart_success(tmp_path: Path) -> None:
    """Validates exporting portfolio valuation chart to PNG file."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)
    portfolio_ts: PortfolioTimeSeries = PortfolioTimeSeries(
        value_history=[
            TimeSeriesPoint(date="2026-08-01", value=1000.0),
            TimeSeriesPoint(date="2026-08-22", value=1200.0),
        ],
        ath_history=[
            TimeSeriesPoint(date="2026-08-01", value=1000.0),
            TimeSeriesPoint(date="2026-08-22", value=1200.0),
        ],
    )
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=portfolio_ts,
        asset_series=[],
        class_series=[],
        asset_summaries=[],
    )

    file_path: Path = exporter.export_portfolio_valuation_chart(overview)

    assert file_path.exists()
    assert file_path.stat().st_size > 0


def test_export_portfolio_valuation_chart_empty_history(
    tmp_path: Path,
) -> None:
    """Validates early return when portfolio history is empty."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=PortfolioTimeSeries(),
        asset_series=[],
        class_series=[],
        asset_summaries=[],
    )

    file_path: Path = exporter.export_portfolio_valuation_chart(overview)

    assert file_path == tmp_path / "portfolio_valuation.png"
    assert not file_path.exists()


def test_export_asset_class_chart_success(tmp_path: Path) -> None:
    """Validates exporting asset class trend chart with multiple classes."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)
    class_etf: AssetClassTimeSeries = AssetClassTimeSeries(
        asset_type="ETF",
        value_history=[TimeSeriesPoint(date="2026-08-22", value=5000.0)],
        share_history=[TimeSeriesPoint(date="2026-08-22", value=60.0)],
    )
    class_stock: AssetClassTimeSeries = AssetClassTimeSeries(
        asset_type="STOCK",
        value_history=[TimeSeriesPoint(date="2026-08-22", value=3000.0)],
        share_history=[TimeSeriesPoint(date="2026-08-22", value=40.0)],
    )
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=PortfolioTimeSeries(),
        asset_series=[],
        class_series=[class_etf, class_stock],
        asset_summaries=[],
    )

    file_path: Path = exporter.export_asset_class_chart(overview)

    assert file_path.exists()
    assert file_path.stat().st_size > 0


def test_export_asset_class_chart_empty_data(tmp_path: Path) -> None:
    """Validates handling of empty asset class series list."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)
    empty_class: AssetClassTimeSeries = AssetClassTimeSeries(
        asset_type="ETF",
        value_history=[],
        share_history=[],
    )
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=PortfolioTimeSeries(),
        asset_series=[],
        class_series=[empty_class],
        asset_summaries=[],
    )

    file_path: Path = exporter.export_asset_class_chart(overview)

    assert file_path == tmp_path / "asset_class_evolution.png"
    assert not file_path.exists()
