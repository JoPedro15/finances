"""
CLI entry point for the finances application powered by Typer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from src.config import DEFAULT_DIP_CONFIG
from src.core.analysis import analyze_overall_performance
from src.core.dip_detector import load_watchlist, scan_watchlist
from src.core.models import PortfolioSnapshot
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


if __name__ == "__main__":
    app()
