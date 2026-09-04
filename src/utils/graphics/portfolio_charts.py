"""Module for generating and exporting portfolio performance charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import matplotlib.dates as mdates
from datetime import datetime

from src.core.models import DashboardOverview


class PortfolioChartExporter:
    """Exports matplotlib charts for portfolio and asset performance history."""

    def __init__(self, output_dir: Path | str = "output/plots") -> None:
        """Initializes the chart exporter with a target output directory."""
        self.output_dir: Path = Path(output_dir)

    def _ensure_output_dir(self) -> None:
        """Ensures the output directory exists on disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _parse_dates(self, history_points: list[Any]) -> list[datetime]:
        """Parses snapshot date strings into datetime objects robustly."""
        parsed_dates: list[datetime] = []
        for pt in history_points:
            try:
                # handles ISO formats like '2024-09-04T11:29:32.123'
                clean_date = pt.date.replace(" ", "T")
                d = datetime.fromisoformat(clean_date)
            except Exception:
                # fallback for other formats
                try:
                    d = datetime.strptime(pt.date, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    d = datetime.strptime(pt.date, "%Y-%m-%d")
            parsed_dates.append(d)
        return parsed_dates

    def export_portfolio_valuation_chart(self, overview: DashboardOverview) -> Path:
        """Generates and exports the global portfolio valuation chart."""
        self._ensure_output_dir()
        output_path: Path = self.output_dir / "portfolio_valuation.png"

        history = overview.portfolio_history.value_history

        if not history:
            return output_path

        parsed_dates = self._parse_dates(history)
        values: list[float] = [pt.value for pt in history]

        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(
            parsed_dates,
            values,
            label="Portfolio Value (€)",
            color="#1f77b4",
            linewidth=2.5,
            marker='o',
            markersize=4,
            markerfacecolor='white',
            markeredgewidth=1.5
        )

        ax.set_title("Portfolio Valuation History", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Value (EUR)", fontsize=10, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.4)

        # Format X-axis to show only unique Months
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

        ax.legend(loc="upper left")

        plt.xticks(rotation=45)
        plt.tight_layout()

        fig.savefig(output_path, dpi=300)
        plt.close(fig)

        return output_path

    def export_asset_class_chart(self, overview: DashboardOverview) -> Path:
        """Generates and exports comparative asset class valuation trends."""
        self._ensure_output_dir()
        output_path: Path = self.output_dir / "asset_class_evolution.png"

        fig, ax = plt.subplots(figsize=(10, 6))

        has_data: bool = False

        # 1. Collect all unique dates across all series to align data
        all_dates_set: set[str] = set()
        for series in overview.class_series:
            for pt in series.value_history:
                all_dates_set.add(pt.date)

        if not all_dates_set:
            plt.close(fig)
            return output_path

        sorted_date_strings = sorted(list(all_dates_set))
        # Create dummy point objects for parsing
        class Pt:
            def __init__(self, d: str): self.date = d
        all_series_dates = self._parse_dates([Pt(d) for d in sorted_date_strings])

        # Sort class series to ensure consistent order
        sorted_series = sorted(overview.class_series, key=lambda x: x.asset_type)

        for class_series in sorted_series:
            has_data = True
            # Create a map for quick lookup
            data_map = {pt.date: pt.value for pt in class_series.value_history}
            # Align values to the global timeline, defaulting to 0.0 if no data for that date
            aligned_values = [data_map.get(date, 0.0) for date in sorted_date_strings]

            ax.plot(
                all_series_dates,
                aligned_values,
                label=f"{class_series.asset_type}",
                linewidth=2.5,
                marker='o',
                markersize=3
            )

        if not has_data:
            plt.close(fig)
            return output_path

        ax.set_title("Asset Class Valuation History", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Value (EUR)", fontsize=10, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.legend(loc="upper left")

        # Format X-axis
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

        plt.xticks(rotation=45)
        plt.tight_layout()

        fig.savefig(output_path, dpi=300)
        plt.close(fig)

        return output_path
