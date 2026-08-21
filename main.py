"""CLI entry point for the finances application powered by Typer."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from src.cli.decision import recommend_rebalance
from src.cli.fundamentals import sync_portfolio_fundamentals
from src.config import DATA_DIR, settings
from src.core.analysis import (
    PortfolioExposure,
    analyze_overall_performance,
    calculate_portfolio_exposure,
)
from src.core.models import (
    Asset,
    ETFDetails,
    PortfolioSnapshot,
    StockDetails,
)
from src.core.providers import ETFProvider, StockProvider
from src.core.repositories import SqlitePortfolioRepository
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
    """Helper to fetch and print formatted details for a single ETF ISIN."""
    logger.section("ETF Details Inspection")
    logger.subsection(f"ETF Name: {name}")
    logger.info(f"ETF ISIN: {isin}")

    dummy_asset: Asset = Asset(
        name=name,
        isin=isin,
        yahoo_ticker="",
        quantity=0,
        average_buy_price=0.0,
        asset_type="ETF",
    )

    try:
        details: ETFDetails | None = provider.get_details(dummy_asset)
    except Exception as err:
        logger.error(f"Failed to fetch details for ETF ISIN {isin}: {err}")
        return

    if details is None:
        logger.error(f"Failed to fetch details for ETF ISIN {isin}.")
        return

    ter_str: str = f"{details.ter_pct:.2f}%" if details.ter_pct is not None else "N/A"
    logger.info(f"TER (Total Expense Ratio): {ter_str}")

    logger.info("Top Holdings:")
    if details.holdings:
        for holding in details.holdings:
            isin_s: str = f" ({holding.isin})" if holding.isin else ""
            logger.print(f"  - {holding.name}{isin_s}: {holding.weight_pct:.2f}%")
    else:
        logger.print("  No holding details available.")

    logger.info("Sector Breakdown:")
    if details.sector_breakdown:
        for sector in details.sector_breakdown:
            logger.print(f"  - {sector.sector_name}: {sector.weight_pct:.2f}%")
    else:
        logger.print("  No sector breakdown available.")

    logger.info("Country Breakdown:")
    if details.country_breakdown:
        for country in details.country_breakdown:
            logger.print(f"  - {country.country_name}: {country.weight_pct:.2f}%")
    else:
        logger.print("  No country breakdown available.")


@app.command(name="etf-details")
def etf_details_cmd(
    isin: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional ISIN of the ETF to inspect. "
                "If omitted, inspects all ETFs in portfolio."
            ),
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
    finally:
        _trigger_cloud_push()


def _format_market_cap(val: float | None) -> str:
    """Formats market capitalization values with dynamic scale suffixes."""
    if val is None:
        return "N/A"
    if val >= 1e12:
        return f"{val / 1e12:.2f}T"
    if val >= 1e9:
        return f"{val / 1e9:.2f}B"
    if val >= 1e6:
        return f"{val / 1e6:.2f}M"
    return f"{val:.2f}"


def _display_single_stock_details(
    identifier: str,
    name: str,
    provider: StockProvider,
    asset: Asset | None = None,
) -> None:
    """Helper function to fetch and print formatted details for a stock."""
    logger.section("Stock Details Inspection")
    logger.subsection(f"Stock Name: {name}")
    if asset and asset.isin:
        logger.info(f"Stock ISIN: {asset.isin}")
    logger.info(f"Ticker: {identifier}")

    dummy_asset: Asset = asset or Asset(
        name=name,
        isin="",
        yahoo_ticker=identifier,
        quantity=0,
        average_buy_price=0.0,
        asset_type="STOCK",
    )

    try:
        details: StockDetails | None = provider.get_details(dummy_asset)
    except Exception as err:
        logger.error(f"Error retrieving stock details for '{identifier}': {err}")
        return

    if details is None:
        logger.error(f"Failed to fetch details for stock '{identifier}'.")
        return

    mcap_str: str = _format_market_cap(details.market_cap)
    pe_str: str = f"{details.pe_ratio:.2f}" if details.pe_ratio is not None else "N/A"
    fwd_pe_str: str = (
        f"{details.forward_pe:.2f}" if details.forward_pe is not None else "N/A"
    )
    peg_str: str = (
        f"{details.peg_ratio:.2f}" if details.peg_ratio is not None else "N/A"
    )
    pb_str: str = (
        f"{details.price_to_book:.2f}" if details.price_to_book is not None else "N/A"
    )
    div_str: str = (
        f"{details.dividend_yield_pct:.2f}%"
        if details.dividend_yield_pct is not None
        else "N/A"
    )
    beta_str: str = f"{details.beta:.2f}" if details.beta is not None else "N/A"
    margin_str: str = (
        f"{details.profit_margins_pct:.2f}%"
        if details.profit_margins_pct is not None
        else "N/A"
    )
    rev_growth_str: str = (
        f"{details.revenue_growth_pct:.2f}%"
        if details.revenue_growth_pct is not None
        else "N/A"
    )
    earn_growth_str: str = (
        f"{details.earnings_growth_pct:.2f}%"
        if details.earnings_growth_pct is not None
        else "N/A"
    )
    debt_eq_str: str = (
        f"{details.total_debt_to_equity:.2f}"
        if details.total_debt_to_equity is not None
        else "N/A"
    )
    target_price_str: str = (
        f"{details.target_mean_price:.2f} EUR"
        if details.target_mean_price is not None
        else "N/A"
    )
    rec_key_str: str = (
        details.recommendation_key.upper() if details.recommendation_key else "N/A"
    )
    high_str: str = (
        f"{details.fifty_two_week_high:.2f}"
        if details.fifty_two_week_high is not None
        else "N/A"
    )
    low_str: str = (
        f"{details.fifty_two_week_low:.2f}"
        if details.fifty_two_week_low is not None
        else "N/A"
    )

    logger.info(f"Sector: {details.sector or 'N/A'}")
    logger.info(f"Industry: {details.industry or 'N/A'}")
    logger.info(f"Market Cap: {mcap_str}")
    logger.info(f"P/E Ratio: {pe_str} (Forward P/E: {fwd_pe_str})")
    logger.info(f"PEG Ratio: {peg_str} | Price to Book: {pb_str}")
    logger.info(f"Dividend Yield: {div_str} | Beta: {beta_str}")
    logger.info(f"Profit Margins: {margin_str} | Debt/Equity: {debt_eq_str}")
    logger.info(
        f"Revenue Growth: {rev_growth_str} | Earnings Growth: {earn_growth_str}"
    )
    logger.info(f"Analyst Consensus: {rec_key_str} (Target Price: {target_price_str})")
    logger.info(f"52-Week Range: {low_str} - {high_str}")


@app.command(name="stock-details")
def stock_details_cmd(
    ticker_or_isin: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Optional Ticker or ISIN of the stock to inspect. "
                "If omitted, inspects all stocks in portfolio."
            ),
        ),
    ] = None,
) -> None:
    """Inspects fundamental metrics for portfolio stock holdings."""
    provider: StockProvider = StockProvider()
    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(DEFAULT_DB_PATH)

    if ticker_or_isin:
        clean_input: str = ticker_or_isin.strip().upper()
        assets_lookup: list[Asset] = []
        try:
            assets_lookup = repo.load_assets()
        except Exception:
            assets_lookup = []

        matched_asset: Asset | None = next(
            (
                a
                for a in assets_lookup
                if str(a.asset_type).upper() == "STOCK"
                and (
                    a.yahoo_ticker.upper() == clean_input
                    or (a.isin and a.isin.upper() == clean_input)
                )
            ),
            None,
        )

        ticker: str = matched_asset.yahoo_ticker if matched_asset else clean_input
        asset_name: str = matched_asset.name if matched_asset else clean_input
        _display_single_stock_details(
            identifier=ticker,
            name=asset_name,
            provider=provider,
            asset=matched_asset,
        )
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
        _display_single_stock_details(
            identifier=asset.yahoo_ticker,
            name=asset.name,
            provider=provider,
            asset=asset,
        )


@app.command(name="analyze-exposure")
def analyze_exposure_cmd() -> None:
    """Analyzes consolidated portfolio sector and country exposure."""
    logger.section("Analyzing Consolidated Portfolio Exposure")

    try:
        snapshot: PortfolioSnapshot | None = get_snapshot()
        if not snapshot:
            logger.error(
                "Failed to calculate portfolio snapshot for exposure analysis."
            )
            raise typer.Exit(code=1)

        exposure: PortfolioExposure = calculate_portfolio_exposure(snapshot)

        if exposure.total_etf_value_eur == 0.0:
            logger.warning("No active ETF holdings found in portfolio.")
            return

        logger.info(
            f"Total ETF Portfolio Value: {exposure.total_etf_value_eur:.2f} EUR"
        )

        logger.info("Consolidated Sector Exposure:")
        for sector, pct in exposure.sector_exposure.items():
            logger.print(f"  - {sector}: {pct:.2f}%")

        logger.info("Consolidated Country Exposure:")
        for country, pct in exposure.country_exposure.items():
            logger.print(f"  - {country}: {pct:.2f}%")
    except typer.Exit:
        raise
    except Exception as err:
        logger.error(f"Failed to analyze exposure: {err}")
        raise typer.Exit(code=1) from err


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
