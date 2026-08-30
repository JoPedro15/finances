"""Portfolio analytics engine for processing metrics, ROI, and time series."""

from __future__ import annotations

from collections import defaultdict

from src.core.models import (
    Asset,
    AssetClassTimeSeries,
    AssetPerformanceSummary,
    AssetTimeSeries,
    DashboardOverview,
    PortfolioTimeSeries,
    TimeSeriesPoint,
)
from src.infra.database.finance_sql_extraction import (
    AssetHistoricalRecord,
    PortfolioHistoricalRecord,
)


class PortfolioAnalyticsEngine:
    """Engine responsible for calculating portfolio metrics and analytics."""

    def compute_portfolio_time_series(
        self, portfolio_records: list[PortfolioHistoricalRecord]
    ) -> PortfolioTimeSeries:
        """Calculates global valuation history, ATH, and drawdown series."""
        value_history: list[TimeSeriesPoint] = []
        ath_history: list[TimeSeriesPoint] = []
        drawdown_history: list[TimeSeriesPoint] = []

        current_ath: float = 0.0

        for record in portfolio_records:
            val: float = record.total_value_eur
            date: str = record.snapshot_date

            if val > current_ath:
                current_ath = val

            drawdown: float = (
                ((val - current_ath) / current_ath * 100.0) if current_ath > 0 else 0.0
            )

            value_history.append(TimeSeriesPoint(date=date, value=val))
            ath_history.append(TimeSeriesPoint(date=date, value=current_ath))
            drawdown_history.append(TimeSeriesPoint(date=date, value=drawdown))

        return PortfolioTimeSeries(
            value_history=value_history,
            ath_history=ath_history,
            drawdown_history=drawdown_history,
        )

    def compute_asset_time_series(
        self, asset_records: list[AssetHistoricalRecord]
    ) -> list[AssetTimeSeries]:
        """Groups historical asset records into individual time series."""
        grouped_values: dict[str, list[TimeSeriesPoint]] = defaultdict(list)
        grouped_qty: dict[str, list[TimeSeriesPoint]] = defaultdict(list)
        asset_info: dict[str, tuple[str, str]] = {}

        for rec in asset_records:
            ticker: str = rec.asset_ticker
            asset_info[ticker] = (rec.asset_name, rec.asset_type)
            grouped_values[ticker].append(
                TimeSeriesPoint(date=rec.snapshot_date, value=rec.value_eur)
            )
            grouped_qty[ticker].append(
                TimeSeriesPoint(date=rec.snapshot_date, value=rec.quantity)
            )

        series_list: list[AssetTimeSeries] = []
        for ticker, (name, a_type) in asset_info.items():
            series_list.append(
                AssetTimeSeries(
                    ticker=ticker,
                    name=name,
                    asset_type=a_type,
                    value_history=grouped_values[ticker],
                    quantity_history=grouped_qty[ticker],
                )
            )

        return series_list

    def compute_asset_class_time_series(
        self,
        asset_records: list[AssetHistoricalRecord],
        portfolio_records: list[PortfolioHistoricalRecord],
    ) -> list[AssetClassTimeSeries]:
        """Aggregates historical valuations and share percentage by asset class."""
        portfolio_totals: dict[str, float] = {
            rec.snapshot_date: rec.total_value_eur for rec in portfolio_records
        }

        class_values: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        for rec in asset_records:
            class_values[rec.asset_type][rec.snapshot_date] += rec.value_eur

        result: list[AssetClassTimeSeries] = []
        for a_type, dates_map in class_values.items():
            val_history: list[TimeSeriesPoint] = []
            share_history: list[TimeSeriesPoint] = []

            for date, class_val in sorted(dates_map.items()):
                total: float = portfolio_totals.get(date, 0.0)
                share: float = (class_val / total * 100.0) if total > 0 else 0.0

                val_history.append(TimeSeriesPoint(date=date, value=class_val))
                share_history.append(TimeSeriesPoint(date=date, value=share))

            result.append(
                AssetClassTimeSeries(
                    asset_type=a_type,
                    value_history=val_history,
                    share_history=share_history,
                )
            )

        return result

    def compute_asset_summaries(
        self,
        asset_records: list[AssetHistoricalRecord],
        current_assets: list[Asset],
        total_portfolio_value: float,
    ) -> list[AssetPerformanceSummary]:
        """Calculates current ROI, cost basis, and portfolio share per asset."""
        latest_records: dict[str, AssetHistoricalRecord] = {}
        for rec in asset_records:
            latest_records[rec.asset_ticker] = rec

        assets_by_ticker: dict[str, Asset] = {
            ast.yahoo_ticker: ast for ast in current_assets
        }

        summaries: list[AssetPerformanceSummary] = []
        for ticker, rec in latest_records.items():
            matched_asset: Asset | None = assets_by_ticker.get(ticker)
            cost_basis: float = (
                matched_asset.acquisition_cost
                if matched_asset
                else (rec.quantity * 0.0)
            )

            val: float = rec.value_eur
            roi_eur: float = val - cost_basis
            roi_pct: float = (roi_eur / cost_basis * 100.0) if cost_basis > 0 else 0.0
            share_pct: float = (
                (val / total_portfolio_value * 100.0)
                if total_portfolio_value > 0
                else 0.0
            )

            summaries.append(
                AssetPerformanceSummary(
                    ticker=ticker,
                    name=rec.asset_name,
                    asset_type=rec.asset_type,
                    latest_quantity=rec.quantity,
                    latest_value_eur=val,
                    cost_basis_eur=cost_basis,
                    roi_eur=roi_eur,
                    roi_percent=roi_pct,
                    portfolio_share_percent=share_pct,
                )
            )

        return summaries

    def build_dashboard_overview(
        self,
        asset_records: list[AssetHistoricalRecord],
        portfolio_records: list[PortfolioHistoricalRecord],
        current_assets: list[Asset] | None = None,
    ) -> DashboardOverview:
        """Builds the complete aggregated overview dataset for dashboard rendering."""
        assets_config: list[Asset] = current_assets or []
        portfolio_ts: PortfolioTimeSeries = self.compute_portfolio_time_series(
            portfolio_records
        )
        asset_series: list[AssetTimeSeries] = self.compute_asset_time_series(
            asset_records
        )
        class_series: list[AssetClassTimeSeries] = self.compute_asset_class_time_series(
            asset_records, portfolio_records
        )

        latest_total: float = (
            portfolio_records[-1].total_value_eur if portfolio_records else 0.0
        )
        summaries: list[AssetPerformanceSummary] = self.compute_asset_summaries(
            asset_records, assets_config, latest_total
        )

        max_drawdown: float = min(
            (pt.value for pt in portfolio_ts.drawdown_history), default=0.0
        )

        top_contributor: str | None = None
        if summaries:
            top_asset: AssetPerformanceSummary = max(summaries, key=lambda s: s.roi_eur)
            top_contributor = top_asset.ticker

        return DashboardOverview(
            portfolio_history=portfolio_ts,
            asset_series=asset_series,
            class_series=class_series,
            asset_summaries=summaries,
            top_growth_contributor=top_contributor,
            max_drawdown_percent=max_drawdown,
        )
