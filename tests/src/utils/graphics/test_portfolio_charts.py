"""Unit tests for PortfolioChartExporter class."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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


def test_parse_dates_space_separated_datetime(tmp_path: Path) -> None:
    """Validates _parse_dates handles space-separated datetime strings."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=PortfolioTimeSeries(
            value_history=[
                TimeSeriesPoint(date="2026-01-15 08:30:00", value=1000.0),
                TimeSeriesPoint(date="2026-02-15 09:00:00", value=1100.0),
            ],
            ath_history=[],
        ),
        asset_series=[],
        class_series=[],
        asset_summaries=[],
    )

    file_path: Path = exporter.export_portfolio_valuation_chart(overview)

    assert file_path.exists()
    assert file_path.stat().st_size > 0


def test_parse_dates_date_only_format(tmp_path: Path) -> None:
    """Validates _parse_dates handles plain date-only strings as fallback."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)
    overview: DashboardOverview = DashboardOverview(
        portfolio_history=PortfolioTimeSeries(
            value_history=[
                TimeSeriesPoint(date="2026-03-01", value=900.0),
                TimeSeriesPoint(date="2026-04-01", value=950.0),
            ],
            ath_history=[],
        ),
        asset_series=[],
        class_series=[],
        asset_summaries=[],
    )

    file_path: Path = exporter.export_portfolio_valuation_chart(overview)

    assert file_path.exists()
    assert file_path.stat().st_size > 0


def test_parse_dates_fallback_space_separated_strptime(tmp_path: Path) -> None:
    """Validates _parse_dates fallback via strptime for %Y-%m-%d %H:%M:%S format."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)

    pt_a = MagicMock()
    pt_a.date = "2026-01-15 08:30:00"
    pt_a.value = 1000.0
    pt_b = MagicMock()
    pt_b.date = "2026-02-15 09:00:00"
    pt_b.value = 1100.0

    from unittest.mock import patch

    with patch("src.utils.graphics.portfolio_charts.datetime") as mock_dt:
        mock_dt.fromisoformat.side_effect = ValueError("forced")
        mock_dt.strptime.side_effect = lambda s, fmt: __import__(
            "datetime"
        ).datetime.strptime(s, fmt)
        dates = exporter._parse_dates([pt_a, pt_b])

    assert len(dates) == 2


def test_parse_dates_fallback_date_only_strptime(tmp_path: Path) -> None:
    """Validates _parse_dates fallback via strptime for %Y-%m-%d date-only format."""
    exporter: PortfolioChartExporter = PortfolioChartExporter(output_dir=tmp_path)

    pt = MagicMock()
    pt.date = "2026-03-15"
    pt.value = 500.0

    from unittest.mock import patch

    with patch("src.utils.graphics.portfolio_charts.datetime") as mock_dt:
        mock_dt.fromisoformat.side_effect = ValueError("forced")
        mock_dt.strptime.side_effect = [
            ValueError("not matching"),
            __import__("datetime").datetime(2026, 3, 15),
        ]
        dates = exporter._parse_dates([pt])

    assert len(dates) == 1
