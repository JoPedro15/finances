"""Terminal presenter for rendering portfolio performance dashboards."""

from __future__ import annotations

import csv
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.core.models import (
    AssetPerformanceSummary,
    AssetTimeSeries,
    DashboardOverview,
)


class PortfolioDashboardPresenter:
    """Presents portfolio analytics in the terminal using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        """Initializes presenter with optional custom Rich console."""
        self.console: Console = console or Console()

    def render_executive_panel(self, overview: DashboardOverview) -> None:
        """Renders executive global portfolio summary panel."""
        latest_val: float = (
            overview.portfolio_history.value_history[-1].value
            if overview.portfolio_history.value_history
            else 0.0
        )

        total_cost: float = sum(
            item.cost_basis_eur for item in overview.asset_summaries
        )
        total_roi_eur: float = latest_val - total_cost
        total_roi_pct: float = (
            (total_roi_eur / total_cost * 100.0) if total_cost > 0 else 0.0
        )

        roi_style: str = "bold green" if total_roi_eur >= 0 else "bold red"
        roi_sign: str = "+" if total_roi_eur >= 0 else ""

        roi_formatted: str = (
            f"{roi_sign}{total_roi_eur:,.2f} € " f"({roi_sign}{total_roi_pct:.2f}%)\n"
        )

        # Aggregate values and percentages by asset class type
        class_totals: dict[str, float] = {}
        for summary in overview.asset_summaries:
            a_type: str = summary.asset_type.upper()
            class_totals[a_type] = (
                class_totals.get(a_type, 0.0) + summary.latest_value_eur
            )

        metrics_text: Text = Text()
        metrics_text.append("Total Portfolio Value: ", style="bold")
        metrics_text.append(f"{latest_val:,.2f} €\n", style="bold yellow")
        metrics_text.append("Total Cost Basis: ", style="bold")
        metrics_text.append(f"{total_cost:,.2f} €\n", style="bold blue")
        metrics_text.append("Total Un-realized ROI: ", style="bold")
        metrics_text.append(roi_formatted, style=roi_style)

        metrics_text.append("\n", style="dim")
        metrics_text.append("Portfolio Composition Split:\n", style="bold underline")
        for a_type, val in sorted(class_totals.items()):
            pct: float = (val / latest_val * 100.0) if latest_val > 0 else 0.0
            metrics_text.append(f"  • {a_type}: ", style="bold")
            metrics_text.append(f"{val:,.2f} € ({pct:.2f}%)\n", style="bold blue")

        metrics_text.append("\n", style="dim")
        metrics_text.append("Max Historical Drawdown: ", style="bold")
        metrics_text.append(
            f"{overview.max_drawdown_percent:.2f}%\n",
            style="bold red",
        )
        metrics_text.append("Top Growth Contributor: ", style="bold")
        metrics_text.append(
            f"{overview.top_growth_contributor or 'N/A'}",
            style="bold magenta",
        )

        panel: Panel = Panel(
            metrics_text,
            title="[bold cyan]GLOBAL PORTFOLIO EXECUTIVE SUMMARY[/bold cyan]",
        )
        self.console.print(panel)

    def export_assets_csv(
        self,
        summaries: list[AssetPerformanceSummary],
        output_path: Path = Path("output/asset_positions_performance_breakdown.csv"),
    ) -> Path:
        """Exports individual product positions to a CSV file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Ticker",
                    "Name",
                    "Type",
                    "Quantity",
                    "Value (€)",
                    "Cost Basis (€)",
                    "ROI (€)",
                    "ROI (%)",
                    "Share (%)",
                ]
            )
            for item in summaries:
                roi_sign: str = "+" if item.roi_eur >= 0 else ""
                writer.writerow(
                    [
                        item.ticker,
                        item.name,
                        item.asset_type.upper(),
                        f"{item.latest_quantity:.4f}",
                        f"{item.latest_value_eur:.2f}",
                        f"{item.cost_basis_eur:.2f}",
                        f"{roi_sign}{item.roi_eur:.2f}",
                        f"{roi_sign}{item.roi_percent:.2f}",
                        f"{item.portfolio_share_percent:.2f}",
                    ]
                )
        return output_path

    def render_asset_detail_panel(
        self,
        summary: AssetPerformanceSummary,
        time_series: AssetTimeSeries | None = None,
    ) -> None:
        """Renders deep-dive panel for a single specific asset."""
        roi_style: str = "bold green" if summary.roi_eur >= 0 else "bold red"
        roi_sign: str = "+" if summary.roi_eur >= 0 else ""

        roi_detail_str: str = (
            f"{roi_sign}{summary.roi_eur:,.2f} € "
            f"({roi_sign}{summary.roi_percent:.2f}%)\n"
        )

        detail_text: Text = Text()
        detail_text.append("Asset Name: ", style="bold white")
        detail_text.append(
            f"{summary.name} ({summary.ticker})\n",
            style="bold yellow",
        )
        detail_text.append("Asset Type: ", style="bold white")
        detail_text.append(f"{summary.asset_type.upper()}\n", style="bold blue")
        detail_text.append("Current Quantity: ", style="bold white")
        detail_text.append(f"{summary.latest_quantity:.4f}\n")
        detail_text.append("Current Market Value: ", style="bold white")
        detail_text.append(
            f"{summary.latest_value_eur:,.2f} €\n",
            style="bold yellow",
        )
        detail_text.append("Cost Basis: ", style="bold white")
        detail_text.append(f"{summary.cost_basis_eur:,.2f} €\n")
        detail_text.append("Un-realized Gain/Loss: ", style="bold white")
        detail_text.append(roi_detail_str, style=roi_style)
        detail_text.append("Portfolio Weight: ", style="bold white")
        detail_text.append(f"{summary.portfolio_share_percent:.2f}%\n")

        if time_series and time_series.value_history:
            detail_text.append(
                f"\nHistorical Snapshots Count: " f"{len(time_series.value_history)}",
                style="italic dim",
            )

        panel: Panel = Panel(
            detail_text,
            title=f"[cyan]ASSET DETAIL ANALYSIS - {summary.ticker}[/cyan]",
            border_style="bold",
        )
        self.console.print(panel)

    def render_full_dashboard(self, overview: DashboardOverview) -> None:
        """Renders complete unified dashboard layout."""
        self.render_executive_panel(overview)
        csv_path: Path = self.export_assets_csv(overview.asset_summaries)
        self.console.print(
            f"\n[bold green]✓[/bold green] Asset positions & performance "
            f"breakdown is available at: [bold cyan]{csv_path}[/bold cyan]\n"
        )
        for summary in overview.asset_summaries:
            series: AssetTimeSeries | None = next(
                (
                    s
                    for s in overview.asset_series
                    if s.ticker.upper() == summary.ticker.upper()
                ),
                None,
            )
            self.render_asset_detail_panel(summary, time_series=series)
