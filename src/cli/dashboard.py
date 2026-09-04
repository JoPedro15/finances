"""CLI command handler for portfolio performance dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from src.cli.portfolio_dashboard import PortfolioDashboardPresenter
from src.config import DATA_DIR
from src.core.models import Asset, DashboardOverview
from src.core.portfolio_analytics import PortfolioAnalyticsEngine
from src.core.repositories import SqlitePortfolioRepository
from src.infra.database.connection import DEFAULT_DB_PATH
from src.infra.database.finance_sql_extraction import (
    AssetHistoricalRecord,
    FinanceSQLExtractor,
    PortfolioHistoricalRecord,
)
from src.infra.notifications.discord import send_dashboard_notification
from src.utils.graphics.portfolio_charts import PortfolioChartExporter

app: typer.Typer = typer.Typer(
    help="Portfolio historical performance & analytics dashboard."
)


@app.callback()
def dashboard_callback() -> None:
    """Dashboard CLI module callback."""


@app.command(name="show")
def show_dashboard(
    db_path: Annotated[
        Path,
        typer.Option(
            "--db-path",
            "-d",
            help="Path to finances SQLite database file.",
        ),
    ] = DEFAULT_DB_PATH,
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to portfolio JSON configuration file.",
        ),
    ] = DATA_DIR
    / "portfolio.json",
    ticker: Annotated[
        str | None,
        typer.Option(
            "--ticker",
            "-t",
            help="Filter detail analysis for a specific asset ticker.",
        ),
    ] = None,
    export_plots: Annotated[
        bool,
        typer.Option(
            "--export-plots",
            "-p",
            help="Export PNG performance charts to output directory.",
        ),
    ] = False,
    notify: Annotated[
        bool,
        typer.Option(
            "--notify",
            help="Dispatch summary and charts to Discord webhook if configured.",
        ),
    ] = False,
) -> None:
    """Executes analytics computation and displays performance dashboard."""
    console: Console = Console()

    extractor: FinanceSQLExtractor = FinanceSQLExtractor(db_path=db_path)
    asset_records: list[AssetHistoricalRecord] = extractor.fetch_asset_history()
    portfolio_records: list[PortfolioHistoricalRecord] = (
        extractor.fetch_portfolio_history()
    )

    current_assets: list[Asset] = []
    if db_path.exists():
        try:
            repo: SqlitePortfolioRepository = SqlitePortfolioRepository(db_path)
            current_assets = repo.load_assets()
        except Exception:
            current_assets = []

    if not current_assets and config_path.exists():
        try:
            raw_content: str = config_path.read_text(encoding="utf-8")
            raw_data: Any = json.loads(raw_content)
            items: list[dict[str, Any]] = (
                raw_data if isinstance(raw_data, list) else raw_data.get("assets", [])
            )
            current_assets = [Asset.from_dict(item) for item in items]
        except Exception as err:
            console.print(
                f"[bold yellow]Warning:[/bold yellow] Could not load config "
                f"'{config_path}': {err}"
            )

    engine: PortfolioAnalyticsEngine = PortfolioAnalyticsEngine()
    overview: DashboardOverview = engine.build_dashboard_overview(
        asset_records=asset_records,
        portfolio_records=portfolio_records,
        current_assets=current_assets,
    )

    presenter: PortfolioDashboardPresenter = PortfolioDashboardPresenter(
        console=console
    )

    if ticker:
        matched_summary = next(
            (s for s in overview.asset_summaries if s.ticker.upper() == ticker.upper()),
            None,
        )
        if not matched_summary:
            console.print(
                f"[bold red]Error:[/bold red] Ticker '{ticker}' not found "
                "in snapshot history."
            )
            raise typer.Exit(code=1)

        matched_series = next(
            (s for s in overview.asset_series if s.ticker.upper() == ticker.upper()),
            None,
        )
        presenter.render_asset_detail_panel(matched_summary, matched_series)
    else:
        presenter.render_full_dashboard(overview)

    if export_plots:
        chart_exporter: PortfolioChartExporter = PortfolioChartExporter()
        val_path: Path = chart_exporter.export_portfolio_valuation_chart(overview)
        class_path: Path = chart_exporter.export_asset_class_chart(overview)
        console.print(
            f"[bold green]✓ Charts exported successfully:[/bold green]\n"
            f"  • {val_path}\n"
            f"  • {class_path}"
        )

        # Dispatch Discord notification if explicitly requested
        if notify:
            send_dashboard_notification(
                total_value=overview.portfolio_history.value_history[-1].value
                if overview.portfolio_history.value_history
                else 0.0,
                max_drawdown=overview.max_drawdown_percent,
                top_contributor=overview.top_growth_contributor,
                image_paths=[val_path, class_path],
            )
