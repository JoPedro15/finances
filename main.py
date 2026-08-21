"""CLI entry point for the finances application powered by Typer."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from src.cli.decision import recommend_rebalance
from src.cli.fundamentals import sync_portfolio_fundamentals
from src.config import DATA_DIR, settings
from src.core.analysis import analyze_overall_performance
from src.core.exposure import ExposureEngine
from src.core.models import (
    Asset,
    ETFDetails,
    PortfolioSnapshot,
    StockDetails,
)
from src.core.providers import ETFProvider, StockProvider
from src.core.repositories import SqliteHistoryRepository, SqlitePortfolioRepository
from src.core.snapshot import display_snapshot, get_snapshot, save_snapshot
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

# Database file mapped to GDRIVE_DATABASE_FOLDER_ID
DB_FILE: Path = DATA_DIR / "finances.db"

app: typer.Typer = typer.Typer(
    name="finances",
    help="CLI tool for monitoring portfolio performance and "
    "investment decision ranking.",
    add_completion=False,
)

console: Console = Console()


def _pull_cloud_data() -> bool:
    """Pulls database and configuration files from their respective Drive folders."""
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
def main_callback() -> None:
    """Validates environment settings and pulls Cloud data on startup."""
    try:
        _ = settings
        logger.info("Synchronizing data from Cloud...")
        _pull_cloud_data()
    except ValidationError as err:
        logger.error(f"Environment configuration validation failed:\n{err}")
        raise typer.Exit(code=1) from err
    except Exception as e:
        logger.error(f"Failed to synchronize data from Cloud: {e}")
        logger.warning("Proceeding with local data only.")


def _trigger_cloud_push() -> None:
    """Helper to push updated local operational files back to Cloud."""
    logger.info("Synchronizing data back to Cloud...")
    try:
        _push_cloud_data()
        logger.success("Cloud synchronization complete.")
    except Exception as e:
        logger.error(f"Failed to push data to Cloud: {e}")


@app.command(name="get-snapshot")
def get_snapshot_cmd() -> None:
    """Calculates and displays the current portfolio valuation."""
    try:
        snapshot_data: PortfolioSnapshot | None = get_snapshot()
        if not snapshot_data:
            logger.error("Failed to calculate portfolio snapshot.")
            raise typer.Exit(code=1)

        display_snapshot(snapshot_data)
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Unexpected error calculating snapshot: {err}")
        raise typer.Exit(code=1) from err


@app.command(name="save-snapshot")
def save_snapshot_cmd() -> None:
    """Calculates valuation, saves history, and pushes to Cloud."""
    try:
        snapshot_data: PortfolioSnapshot | None = get_snapshot()
        if not snapshot_data:
            logger.error("Failed to calculate portfolio snapshot.")
            raise typer.Exit(code=1)

        save_snapshot(snapshot_data)
        _trigger_cloud_push()
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Unexpected error saving snapshot: {err}")
        raise typer.Exit(code=1) from err


@app.command(name="analyze")
def analyze_cmd() -> None:
    """Analyzes historical performance and ROI for all portfolio assets."""
    try:
        analyze_overall_performance()
    except Exception as err:
        logger.error(f"Failed to analyze portfolio performance: {err}")
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
            logger.warning(
                "One or more configuration files failed to download from Drive."
            )
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
            logger.warning("One or more configuration files failed to upload to Drive.")
    except Exception as err:
        logger.error(f"Google Drive push failed: {err}")
        raise typer.Exit(code=1) from err


def _display_single_etf_details(isin: str, name: str, provider: ETFProvider) -> None:
    """Displays detailed composition and breakdowns for a single ETF."""
    dummy_asset: Asset = Asset(
        isin=isin,
        name=name,
        yahoo_ticker=isin,
        quantity=0.0,
        average_buy_price=0.0,
        asset_type="ETF",
    )
    details: ETFDetails | None = provider.get_details(dummy_asset)
    console.print(f"\n[bold cyan]=== ETF DETAILS: {name} ({isin}) ===[/bold cyan]")
    if details:
        ter_str = f"{details.ter_pct}%" if details.ter_pct else "TER: N/A"
        console.print(f"TER: {ter_str}", highlight=False)
        if details.holdings:
            console.print("\nTop Holdings:", highlight=False)
            for h in details.holdings[:10]:
                console.print(
                    f"  • {h.name} ({h.isin or 'N/A'}): {h.weight_pct}%",
                    highlight=False,
                )
    else:
        console.print("[red]Failed to fetch details.[/red]")


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
    """Inspects composition, TER, holdings, and breakdowns for portfolio ETFs."""
    provider: ETFProvider = ETFProvider()
    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(DEFAULT_DB_PATH)

    try:
        if isin:
            clean_isin: str = isin.strip().upper()
            if len(clean_isin) != 12:
                logger.error(
                    f"Invalid ISIN format '{isin}'. Expected 12-character code."
                )
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
            _display_single_etf_details(clean_isin, asset_name, provider)
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
            _display_single_etf_details(asset.isin, asset.name, provider)

        _trigger_cloud_push()
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Unexpected error fetching ETF details: {err}")
        raise typer.Exit(code=1) from err


def _format_market_cap(val: float | None) -> str:
    """Formats market cap values with dynamic scale suffixes (B/T)

    rounded to two decimal places.
    """
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
    """Displays fundamental financial metrics for a single stock."""
    dummy_asset: Asset = Asset(
        isin=ticker if len(ticker) == 12 else "",
        name=name,
        yahoo_ticker=ticker,
        quantity=0.0,
        average_buy_price=0.0,
        asset_type="STOCK",
    )
    details: StockDetails | None = provider.get_details(dummy_asset)
    console.print(f"\n[bold cyan]=== STOCK DETAILS: {name} ({ticker}) ===[/bold cyan]")
    if details:
        console.print(f"Sector: {details.sector or 'N/A'}", highlight=False)
        console.print(f"Industry: {details.industry or 'N/A'}", highlight=False)
        mcap = _format_market_cap(details.market_cap)
        console.print(f"Market Cap: {mcap}", highlight=False)

        pe_str = f"{details.pe_ratio:.2f}" if details.pe_ratio is not None else "N/A"
        fwd_str = (
            f"{details.forward_pe:.2f}" if details.forward_pe is not None else "N/A"
        )
        div_str = (
            f"{details.dividend_yield_pct:.2f}%"
            if details.dividend_yield_pct is not None
            else "N/A"
        )

        console.print(f"P/E Ratio: {pe_str}", highlight=False)
        console.print(f"Forward P/E: {fwd_str}", highlight=False)
        console.print(f"Dividend Yield: {div_str}", highlight=False)
    else:
        console.print("[red]Failed to fetch fundamental metrics.[/red]")


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

        _trigger_cloud_push()
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Unexpected error fetching stock details: {err}")
        raise typer.Exit(code=1) from err


@app.command(name="exposure-check")
def check_exposure() -> None:
    """Displays consolidated look-through exposure (sectors, countries,
    and individual companies) in the terminal.
    """
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

    console.print("\n[bold yellow]=== CONSOLIDATED SECTOR EXPOSURE ===[/bold yellow]")
    for sector, pct in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
        is_tech: bool = "technology" in sector.lower() or "tech" in sector.lower()
        sector_limit: float = (
            settings.max_tech_allocation_pct
            if is_tech
            else settings.max_other_sector_allocation_pct
        )
        sector_status_style: str = "red" if pct > sector_limit else "green"
        console.print(
            f"  • {sector}: "
            f"[{sector_status_style}]{pct:.2f}%[/{sector_status_style}] "
            f"(Max: {sector_limit:.1f}%)"
        )

    console.print("\n[bold yellow]=== CONSOLIDATED COUNTRY EXPOSURE ===[/bold yellow]")
    for country, pct in sorted(countries.items(), key=lambda x: x[1], reverse=True):
        country_limit: float = settings.max_country_allocation_pct
        country_status_style: str = "red" if pct > country_limit else "green"
        console.print(
            f"  • {country}: "
            f"[{country_status_style}]{pct:.2f}%[/{country_status_style}] "
            f"(Max: {country_limit:.1f}%)"
        )

    console.print(
        "\n[bold yellow]=== CONSOLIDATED COMPANY EXPOSURE "
        "(Top Look-Through) ===[/bold yellow]"
    )
    for comp, pct in sorted(companies.items(), key=lambda x: x[1], reverse=True)[:10]:
        company_status_style: str = (
            "red" if pct > settings.max_company_allocation_pct else "green"
        )
        console.print(
            f"  • {comp}: "
            f"[{company_status_style}]{pct:.2f}%[/{company_status_style}]"
        )

    if company_violations or sector_violations:
        console.print("\n[bold red]⚠️ Policy Violations Detected:[/bold red]")
        for v in sector_violations + company_violations:
            console.print(f"  - {v}", style="red")
    else:
        console.print("\n[bold green]✓ All exposure limits are respected.[/bold green]")


@app.command(name="decision")
def decision_cmd(
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
            help="Skip Gemini AI analysis and display quantitative scores only.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Display detailed quantitative score factors breakdown.",
        ),
    ] = False,
) -> None:
    """Ranks targets and provides AI-driven investment decision recommendations."""
    recommend_rebalance(
        targets_file=targets_file,
        portfolio_file=portfolio_file,
        db_path=db_path,
        skip_ai=skip_ai,
        verbose=verbose,
    )
    _trigger_cloud_push()


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
    """Synchronizes portfolio fundamentals into database and pushes to Cloud."""
    try:
        sync_portfolio_fundamentals(db_path=db_path)
        _trigger_cloud_push()
    except Exception as err:
        logger.error(f"Failed to synchronize portfolio fundamentals: {err}")
        raise typer.Exit(code=1) from err


if __name__ == "__main__":
    app()
