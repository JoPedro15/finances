"""Module for generating and exporting portfolio performance charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.core.models import DashboardOverview


class PortfolioChartExporter:
    """Exports matplotlib charts for portfolio and asset performance history."""

    def __init__(self, output_dir: Path | str = "output/plots") -> None:
        """Initializes the chart exporter with a target output directory."""
        self.output_dir: Path = Path(output_dir)

    def _ensure_output_dir(self) -> None:
        """Ensures the output directory exists on disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_portfolio_valuation_chart(self, overview: DashboardOverview) -> Path:
        """Generates and exports the global portfolio valuation and ATH chart."""
        self._ensure_output_dir()
        output_path: Path = self.output_dir / "portfolio_valuation.png"

        history = overview.portfolio_history.value_history
        ath_history = overview.portfolio_history.ath_history

        if not history:
            return output_path

        dates: list[str] = [pt.date for pt in history]
        values: list[float] = [pt.value for pt in history]
        aths: list[float] = [pt.value for pt in ath_history]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(
            dates,
            values,
            label="Portfolio Value (€)",
            color="#1f77b4",
            linewidth=2,
        )
        ax.plot(
            dates,
            aths,
            label="All-Time High (€)",
            color="#2ca02c",
            linestyle="--",
            linewidth=1.5,
        )

        ax.set_title("Portfolio Valuation History", fontsize=14, fontweight="bold")
        ax.set_xlabel("Snapshot Date", fontsize=10)
        ax.set_ylabel("Value (EUR)", fontsize=10)
        ax.grid(True, linestyle=":", alpha=0.6)
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

        fig, ax = plt.subplots(figsize=(10, 5))
        has_data: bool = False

        for class_series in overview.class_series:
            if not class_series.value_history:
                continue
            has_data = True
            dates: list[str] = [pt.date for pt in class_series.value_history]
            values: list[float] = [pt.value for pt in class_series.value_history]
            ax.plot(
                dates,
                values,
                label=f"Class: {class_series.asset_type}",
                linewidth=2,
            )

        if not has_data:
            plt.close(fig)
            return output_path

        ax.set_title("Asset Class Valuation History", fontsize=14, fontweight="bold")
        ax.set_xlabel("Snapshot Date", fontsize=10)
        ax.set_ylabel("Value (EUR)", fontsize=10)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper left")
        plt.xticks(rotation=45)
        plt.tight_layout()

        fig.savefig(output_path, dpi=300)
        plt.close(fig)

        return output_path
