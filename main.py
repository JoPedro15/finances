"""
CLI entry point for the finances application powered by Typer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from src.config import DEFAULT_DIP_CONFIG
from src.core.analysis import (
    PortfolioExposure,
    analyze_overall_performance,
    calculate_portfolio_exposure,
)
from src.core.dip_detector import load_watchlist, scan_watchlist
from src.core.models import Asset, ETFDetails, PortfolioSnapshot
from src.core.providers import ETFProvider
from src.core.repositories import JsonPortfolioRepository
from src.core.snapshot import display_snapshot, get_snapshot, save_snapshot
from src.utils.logger.logger import logger

app: typer.Typer = typer.Typer(
    name="finances",
    help="CLI tool for monitoring portfolio performance and stock price dips.",
    add_completion=False,
)


@app.command(name="get-snapshot")
def get_snapshot_cmd() -> None:
    """Calculates and displays the current portfolio valuation."""
    snapshot_data: PortfolioSnapshot | None = get_snapshot()
    if not snapshot_data:
        logger.error("Failed to calculate portfolio snapshot.")
        raise typer.Exit(code=1)

    display_snapshot(snapshot_data)


@app.command(name="save-snapshot")
def save_snapshot_cmd() -> None:
    """Calculates current portfolio valuation and saves it to history."""
    snapshot_data: PortfolioSnapshot | None = get_snapshot()
    if not snapshot_data:
        logger.error("Failed to calculate portfolio snapshot.")
        raise typer.Exit(code=1)

    save_snapshot(snapshot_data)


@app.command(name="analyze")
def analyze_cmd() -> None:
    """Analyzes historical performance and ROI for all portfolio assets."""
    analyze_overall_performance()


@app.command(name="check-dips")
def check_dips_cmd(
    watchlist_path: Annotated[
        Path,
        typer.Option(
            "--watchlist",
            "-w",
            help="Path to the watchlist JSON file.",
        ),
    ] = Path("data/watchlist.json"),
    min_drop: Annotated[
        float,
        typer.Option(
            "--min-drop",
            help="Minimum dip percentage threshold.",
        ),
    ] = DEFAULT_DIP_CONFIG.min_drop_pct,
    max_drop: Annotated[
        float,
        typer.Option(
            "--max-drop",
            help="Maximum dip percentage threshold.",
        ),
    ] = DEFAULT_DIP_CONFIG.max_drop_pct,
    lookback_days: Annotated[
        int,
        typer.Option(
            "--lookback",
            "-l",
            help="Number of days to search for historical peak.",
        ),
    ] = DEFAULT_DIP_CONFIG.lookback_days,
) -> None:
    """Scans watchlist assets for stock price dip opportunities."""
    logger.section("Scanning Watchlist for Price Dips")
    items: list[dict[str, str]] = load_watchlist(str(watchlist_path))

    if not items:
        logger.error(
            f"No items found or failed to load watchlist from '{watchlist_path}'."
        )
        raise typer.Exit(code=1)

    matches: list[dict[str, Any]] = scan_watchlist(
        items=items,
        min_drop_pct=min_drop,
        max_drop_pct=max_drop,
        lookback_days=lookback_days,
    )

    if matches:
        logger.info(f"Found {len(matches)} dip opportunities:")
        for match in matches:
            logger.info(f" -> {match}")
    else:
        logger.info("No tickers met the dip criteria.")


def _display_single_etf_details(isin: str, name: str, provider: ETFProvider) -> None:
    """Helper function to fetch and print formatted details for a single ETF ISIN."""
    logger.section("ETF Details Inspection")
    logger.info(f"ETF Name: {name}")
    logger.info(f"ETF ISIN: {isin}")

    dummy_asset: Asset = Asset(
        name=name,
        isin=isin,
        yahoo_ticker="",
        quantity=0,
        average_buy_price=0.0,
    )

    details: ETFDetails | None = provider.get_details(dummy_asset)

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
    """Inspects composition, TER, holdings, and breakdowns

    for an ETF ISIN or all portfolio ETFs.
    """
    provider: ETFProvider = ETFProvider()
    repo: JsonPortfolioRepository = JsonPortfolioRepository("data/portfolio.json")

    if isin:
        clean_isin: str = isin.strip().upper()
        if len(clean_isin) != 12:
            logger.error(f"Invalid ISIN format '{isin}'. Expected a 12-character code.")
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
        a for a in assets if a.asset_type == "etf" and a.isin and len(a.isin) == 12
    ]
    if not etf_assets:
        logger.warning("No active ETF holdings found in portfolio.")
        return

    for asset in etf_assets:
        _display_single_etf_details(asset.isin, asset.name, provider)


@app.command(name="analyze-exposure")
def analyze_exposure_cmd() -> None:
    """Analyzes consolidated portfolio sector and country exposure."""
    logger.section("Analyzing Consolidated Portfolio Exposure")

    snapshot: PortfolioSnapshot | None = get_snapshot()
    if not snapshot:
        logger.error("Failed to calculate portfolio snapshot for exposure analysis.")
        raise typer.Exit(code=1)

    exposure: PortfolioExposure = calculate_portfolio_exposure(snapshot)

    if exposure.total_etf_value_eur == 0.0:
        logger.warning("No active ETF holdings found in portfolio.")
        return

    logger.info(f"Total ETF Portfolio Value: {exposure.total_etf_value_eur:.2f} EUR")

    logger.info("Consolidated Sector Exposure:")
    for sector, pct in exposure.sector_exposure.items():
        logger.print(f"  - {sector}: {pct:.2f}%")

    logger.info("Consolidated Country Exposure:")
    for country, pct in exposure.country_exposure.items():
        logger.print(f"  - {country}: {pct:.2f}%")


if __name__ == "__main__":
    app()
