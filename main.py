"""CLI entry point for the finances application powered by Typer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.cli.dashboard import app as dashboard_app
from src.cli.fundamentals import sync_portfolio_fundamentals
from src.cli.opportunity import recommend_rebalance
from src.cli.quality import analyze_quality_cmd
from src.config import DATA_DIR, settings
from src.core.exposure import ExposureEngine
from src.core.models import (
    Asset,
    ETFDetails,
    PortfolioSnapshot,
    StockDetails,
)
from src.core.providers import ETFProvider, StockProvider
from src.core.repositories import (
    SqliteHistoryRepository,
    SqlitePortfolioRepository,
)
from src.core.snapshot import get_snapshot, save_snapshot
from src.infra.database.connection import DEFAULT_DB_PATH
from src.infra.gdrive.service import GDriveService
from src.utils.logger.logger import logger

# Configuration files mapped to GDRIVE_CONFIG_FOLDER_ID
CONFIG_FILES: list[Path] = [
    DATA_DIR / "portfolio.json",
    DATA_DIR / "portfolio_targets.json",
    DATA_DIR / "etf_cache.json",
    DATA_DIR / "system_instruction.json",
]

# Database file mapped dynamically to DEFAULT_DB_PATH to avoid filename mismatch
DB_FILE: Path = Path(DEFAULT_DB_PATH)

app: typer.Typer = typer.Typer(
    name="finances",
    help="CLI tool for monitoring portfolio performance and "
    "investment opportunity evaluation ranking.",
    add_completion=False,
)

app.add_typer(dashboard_app, name="dashboard")

console: Console = Console()


def _pull_cloud_data() -> bool:
    """Pulls database and configuration files from Drive folders."""
    db_service: GDriveService = GDriveService(
        folder_id=settings.gdrive_database_folder_id
    )
    db_ok: bool = bool(db_service.download_file(DB_FILE.name, DB_FILE))

    config_service: GDriveService = GDriveService(
        folder_id=settings.gdrive_config_folder_id
    )
    results: dict[str, bool] = config_service.sync_files(CONFIG_FILES, direction="pull")
    return db_ok and all(results.values())


def _push_cloud_data() -> bool:
    """Pushes database and config files to respective Drive folders."""
    db_ok: bool = True
    if DB_FILE.exists():
        db_service: GDriveService = GDriveService(
            folder_id=settings.gdrive_database_folder_id
        )
        db_ok = bool(db_service.upload_file(DB_FILE, overwrite=True))

    existing_config: list[Path] = [f for f in CONFIG_FILES if f.exists()]
    config_ok: bool = True
    if existing_config:
        config_service: GDriveService = GDriveService(
            folder_id=settings.gdrive_config_folder_id
        )
        results: dict[str, bool] = config_service.sync_files(
            existing_config, direction="push"
        )
        config_ok = all(results.values())

    return db_ok and config_ok


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Validates environment settings on startup."""
    try:
        _ = settings
    except ValidationError as err:
        logger.error(f"Environment configuration validation failed:\n{err}")
        raise typer.Exit(code=1) from err
    except Exception as e:
        logger.error(f"Failed to validate environment configuration: {e}")


@app.command(name="save-snapshot")
def save_snapshot_cmd() -> None:
    """Calculates valuation and saves history snapshot to local database."""
    try:
        snapshot_data: PortfolioSnapshot | None = get_snapshot()
        if not snapshot_data:
            logger.error("Failed to calculate portfolio snapshot.")
            raise typer.Exit(code=1)

        save_snapshot(snapshot_data)
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Unexpected error saving snapshot: {err}")
        raise typer.Exit(code=1) from err


@app.command(name="pull-config")
def pull_config_cmd() -> None:
    """Pulls configuration files and database from Google Drive."""
    logger.section("Pulling Configuration from Google Drive")
    try:
        success: bool = _pull_cloud_data()
        if success:
            logger.success("Successfully pulled configuration files from Google Drive.")
        else:
            logger.warning("One or more configuration files failed to download.")
    except Exception as err:
        logger.error(f"Google Drive pull failed: {err}")
        raise typer.Exit(code=1) from err


@app.command(name="push-config")
def push_config_cmd() -> None:
    """Pushes local configuration files and database to Google Drive."""
    logger.section("Pushing Configuration to Google Drive")
    try:
        success: bool = _push_cloud_data()
        if success:
            logger.success("Successfully pushed configuration files to Google Drive.")
        else:
            logger.warning("One or more configuration files failed to upload.")
    except Exception as err:
        logger.error(f"Google Drive push failed: {err}")
        raise typer.Exit(code=1) from err


def _display_single_etf_details(
    isin: str, name: str, provider: ETFProvider, ticker: str | None = None
) -> None:
    """Displays detailed composition and breakdowns for an ETF using Rich Panel."""
    display_ticker: str = ticker or isin
    dummy_asset: Asset = Asset(
        isin=isin,
        name=name,
        yahoo_ticker=display_ticker,
        quantity=0.0,
        average_buy_price=0.0,
        asset_type="ETF",
    )
    details: ETFDetails | None = provider.get_details(dummy_asset)
    if not details:
        console.print(f"[red]Failed to fetch details for {name} ({isin}).[/red]")
        return

    ter_str: str = f"{details.ter_pct:.2f}%" if details.ter_pct is not None else "N/A"

    card_text: Text = Text()
    card_text.append("Asset Name: ", style="bold white")
    card_text.append(f"{name} ({isin})\n", style="bold yellow")
    card_text.append("Asset Type: ", style="bold blue")
    card_text.append("ETF\n", style="bold blue")
    card_text.append("TER: ", style="bold white")
    card_text.append(f"{ter_str}\n", style="bold green")

    if details.holdings:
        card_text.append("\nTop Holdings:\n", style="bold underline")
        for h in details.holdings[:10]:
            h_isin: str = f" ({h.isin})" if h.isin else ""
            card_text.append("  • ", style="dim")
            card_text.append(f"{h.name}{h_isin}: ", style="bold white")
            card_text.append(f"{h.weight_pct:.2f}%\n")

    if details.sector_breakdown:
        card_text.append("\nSector Breakdown:\n", style="bold underline")
        for s in details.sector_breakdown[:5]:
            card_text.append("  • ", style="dim")
            card_text.append(f"{s.sector_name}: ", style="bold white")
            card_text.append(f"{s.weight_pct:.2f}%\n")

    if details.country_breakdown:
        card_text.append("\nCountry Breakdown:\n", style="bold underline")
        for c in details.country_breakdown[:5]:
            card_text.append("  • ", style="dim")
            card_text.append(f"{c.country_name}: ", style="bold white")
            card_text.append(f"{c.weight_pct:.2f}%\n")

    panel: Panel = Panel(
        card_text,
        title=f"[bold cyan]ETF DETAILS - {display_ticker}[/bold cyan]",
    )
    console.print(panel)


@app.command(name="etf-details")
def etf_details_cmd(
    isin: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional ISIN of the ETF to inspect. "
                "If omitted, inspects all ETFs in portfolio."
            )
        ),
    ] = None,
) -> None:
    """Inspects composition, TER, holdings, and breakdowns for ETFs."""
    provider: ETFProvider = ETFProvider()
    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(DEFAULT_DB_PATH)

    try:
        if isin:
            clean_isin: str = isin.strip().upper()
            if len(clean_isin) != 12:
                logger.error(f"Invalid ISIN format '{isin}'. Expected 12-char code.")
                raise typer.Exit(code=1)

            assets_lookup: list[Asset] = []
            try:
                assets_lookup = repo.load_assets()
            except Exception:
                assets_lookup = []

            matched_asset: Asset | None = next(
                (a for a in assets_lookup if a.isin and a.isin.upper() == clean_isin),
                None,
            )
            asset_name: str = matched_asset.name if matched_asset else clean_isin
            ticker: str = matched_asset.yahoo_ticker if matched_asset else clean_isin
            _display_single_etf_details(clean_isin, asset_name, provider, ticker=ticker)
            return

        try:
            assets: list[Asset] = repo.load_assets()
        except Exception as e:
            logger.error(f"Failed to load portfolio assets: {e}")
            raise typer.Exit(code=1) from e

        etf_assets: list[Asset] = [
            a
            for a in assets
            if str(a.asset_type).upper() == "ETF" and a.isin and len(a.isin) == 12
        ]
        if not etf_assets:
            logger.warning("No active ETF holdings found in portfolio.")
            return

        for asset in etf_assets:
            _display_single_etf_details(
                asset.isin, asset.name, provider, ticker=asset.yahoo_ticker
            )
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Unexpected error fetching ETF details: {err}")
        raise typer.Exit(code=1) from err


def _format_market_cap(val: float | None) -> str:
    """Formats market cap values with dynamic scale suffixes (B/T)."""
    if val is None:
        return "N/A"
    if val >= 1_000_000_000_000:
        return f"{val / 1_000_000_000_000:.2f}T"
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    return f"{val:.2f}"


def _display_single_stock_details(
    ticker: str, name: str, provider: StockProvider
) -> None:
    """Displays fundamental financial metrics for a single stock using Rich Panel."""
    dummy_asset: Asset = Asset(
        isin=ticker if len(ticker) == 12 else "",
        name=name,
        yahoo_ticker=ticker,
        quantity=0.0,
        average_buy_price=0.0,
        asset_type="STOCK",
    )
    details: StockDetails | None = provider.get_details(dummy_asset)
    if not details:
        console.print(
            f"[red]Failed to fetch fundamental metrics for {name} ({ticker}).[/red]"
        )
        return

    mcap_str: str = _format_market_cap(details.market_cap)
    pe_str: str = f"{details.pe_ratio:.2f}" if details.pe_ratio is not None else "N/A"
    fwd_str: str = (
        f"{details.forward_pe:.2f}" if details.forward_pe is not None else "N/A"
    )
    div_str: str = (
        f"{details.dividend_yield_pct:.2f}%"
        if details.dividend_yield_pct is not None
        else "N/A"
    )

    card_text: Text = Text()
    card_text.append("Asset Name: ", style="bold white")
    card_text.append(f"{name} ({ticker})\n", style="bold yellow")
    card_text.append("Asset Type: ", style="bold white")
    card_text.append("STOCK\n", style="bold blue")
    card_text.append("Sector: ", style="bold white")
    card_text.append(f"{details.sector or 'N/A'}\n")
    card_text.append("Industry: ", style="bold white")
    card_text.append(f"{details.industry or 'N/A'}\n")
    card_text.append("Market Cap: ", style="bold white")
    card_text.append(f"{mcap_str}\n", style="yellow")
    card_text.append("P/E Ratio: ", style="bold white")
    card_text.append(f"{pe_str}\n")
    card_text.append("Forward P/E: ", style="bold white")
    card_text.append(f"{fwd_str}\n")
    card_text.append("Dividend Yield: ", style="bold white")
    card_text.append(f"{div_str}\n", style="green")

    panel: Panel = Panel(
        card_text,
        title=f"[bold cyan]STOCK DETAILS - {ticker}[/bold cyan]",
    )
    console.print(panel)


@app.command(name="analyze-quality")
def analyze_quality_cli(
    ticker: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional ticker symbol or ISIN to analyze. "
                "If omitted, analyzes all active portfolio assets."
            )
        ),
    ] = None,
) -> None:
    """Evaluates absolute quality tiers and metrics for assets."""
    try:
        analyze_quality_cmd(ticker=ticker)
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Failed to analyze asset quality: {err}")
        raise typer.Exit(code=1) from err


@app.command(name="stock-details")
def stock_details_cmd(
    ticker: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional stock ticker symbol or ISIN. "
                "If omitted, inspects all stocks in portfolio."
            )
        ),
    ] = None,
) -> None:
    """Inspects fundamental financial metrics for portfolio stocks."""
    provider: StockProvider = StockProvider()
    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(DEFAULT_DB_PATH)

    try:
        if ticker:
            clean_ticker: str = ticker.strip()
            assets_lookup: list[Asset] = []
            try:
                assets_lookup = repo.load_assets()
            except Exception:
                assets_lookup = []

            matched_asset: Asset | None = next(
                (
                    a
                    for a in assets_lookup
                    if a.yahoo_ticker.upper() == clean_ticker.upper()
                    or (a.isin and a.isin.upper() == clean_ticker.upper())
                ),
                None,
            )
            asset_name: str = matched_asset.name if matched_asset else clean_ticker
            _display_single_stock_details(clean_ticker, asset_name, provider)
            return

        try:
            assets: list[Asset] = repo.load_assets()
        except Exception as e:
            logger.error(f"Failed to load portfolio assets: {e}")
            raise typer.Exit(code=1) from e

        stock_assets: list[Asset] = [
            a for a in assets if str(a.asset_type).upper() == "STOCK"
        ]
        if not stock_assets:
            logger.warning("No active stock holdings found in portfolio.")
            return

        for asset in stock_assets:
            _display_single_stock_details(asset.yahoo_ticker, asset.name, provider)
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Unexpected error fetching stock details: {err}")
        raise typer.Exit(code=1) from err


@app.command(name="exposure-check")
def check_exposure() -> None:
    """Displays consolidated look-through exposure in terminal."""
    exposure_engine: ExposureEngine = ExposureEngine()
    history_repo: SqliteHistoryRepository = SqliteHistoryRepository(DEFAULT_DB_PATH)
    history: list[PortfolioSnapshot] = history_repo.load_history()

    if not history:
        console.print("[red]No portfolio history found for exposure check.[/red]")
        return

    latest_snapshot: PortfolioSnapshot = history[-1]

    with console.status("[bold cyan]Calculating look-through exposures..."):
        sectors: dict[str, float]
        countries: dict[str, float]
        sectors, countries = exposure_engine.calculate_consolidated_exposure(
            latest_snapshot
        )
        companies: dict[str, float] = exposure_engine.calculate_company_exposure(
            latest_snapshot
        )

        sector_violations: list[str] = exposure_engine.validate_exposure_limits(
            sectors, countries
        )
        company_violations: list[str] = exposure_engine.validate_company_limits(
            companies
        )

    card_text: Text = Text()

    card_text.append("Consolidated Sector Exposure:\n", style="bold underline")
    for sector, pct in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
        is_tech: bool = "technology" in sector.lower() or "tech" in sector.lower()
        sector_limit: float = (
            settings.max_tech_allocation_pct
            if is_tech
            else settings.max_other_sector_allocation_pct
        )
        sector_status_style: str = "bold red" if pct > sector_limit else "green"
        card_text.append("  • ", style="dim")
        card_text.append(f"{sector}: ", style="bold white")
        card_text.append(f"{pct:.2f}% ", style=sector_status_style)
        card_text.append(f"(Max: {sector_limit:.1f}%)\n", style="dim")

    card_text.append("\nConsolidated Country Exposure:\n", style="bold underline")
    for country, pct in sorted(countries.items(), key=lambda x: x[1], reverse=True):
        country_limit: float = settings.max_country_allocation_pct
        country_status_style: str = "bold red" if pct > country_limit else "green"
        card_text.append("  • ", style="dim")
        card_text.append(f"{country}: ", style="bold white")
        card_text.append(f"{pct:.2f}% ", style=country_status_style)
        card_text.append(f"(Max: {country_limit:.1f}%)\n", style="dim")

    card_text.append("\nTop Look-Through Company Exposure:\n", style="bold underline")
    for comp, pct in sorted(companies.items(), key=lambda x: x[1], reverse=True)[:10]:
        comp_limit: float = settings.max_company_allocation_pct
        comp_status_style: str = "bold red" if pct > comp_limit else "green"
        card_text.append("  • ", style="dim")
        card_text.append(f"{comp}: ", style="bold white")
        card_text.append(f"{pct:.2f}%\n", style=comp_status_style)

    card_text.append("\nPolicy Compliance Status:\n", style="bold underline")
    violations: list[str] = sector_violations + company_violations
    if violations:
        card_text.append("  ⚠️ Policy Violations Detected:\n", style="bold red")
        for v in violations:
            card_text.append(f"    - {v}\n", style="red")
    else:
        card_text.append("  ✓ All exposure limits are respected.\n", style="bold green")

    panel: Panel = Panel(
        card_text,
        title="[bold cyan]PORTFOLIO LOOK-THROUGH EXPOSURE ANALYSIS[/bold cyan]",
    )
    console.print(panel)


@app.command(name="opportunity_evaluation")
def opportunity_cmd(
    targets_file: Annotated[
        Path,
        typer.Option(
            "--targets-file",
            "-t",
            help="Path to JSON file containing target wishlist.",
        ),
    ] = DATA_DIR
    / "portfolio_targets.json",
    portfolio_file: Annotated[
        Path,
        typer.Option(
            "--portfolio-file",
            "-p",
            help="Path to JSON file containing active holdings.",
        ),
    ] = DATA_DIR
    / "portfolio.json",
    db_path: Annotated[
        Path,
        typer.Option(
            "--db-path",
            help="Path to SQLite database file.",
        ),
    ] = DEFAULT_DB_PATH,
    skip_ai: Annotated[
        bool,
        typer.Option(
            "--skip-ai",
            help="Skip Gemini AI analysis and display quant scores only.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Display detailed score factors breakdown.",
        ),
    ] = False,
) -> None:
    """Ranks targets and provides AI-driven recommendations."""
    recommend_rebalance(
        targets_file=targets_file,
        portfolio_file=portfolio_file,
        db_path=db_path,
        skip_ai=skip_ai,
        verbose=verbose,
    )


@app.command(name="sync-fundamentals")
def sync_fundamentals_cmd(
    db_path: Annotated[
        Path,
        typer.Option(
            "--db-path",
            help="Path to SQLite database file.",
        ),
    ] = DEFAULT_DB_PATH,
) -> None:
    """Synchronizes portfolio fundamentals into local SQLite database."""
    try:
        sync_portfolio_fundamentals(db_path=db_path)
    except Exception as err:
        logger.error(f"Failed to synchronize portfolio fundamentals: {err}")
        raise typer.Exit(code=1) from err


if __name__ == "__main__":
    app()