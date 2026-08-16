"""
This file contains the logic for creating and managing portfolio value snapshots.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from src.core.exceptions import StorageError
from src.core.get_quotation import get_exchange_rate, get_quotation
from src.core.models import Asset, AssetSnapshot, PortfolioSnapshot, Quotation
from src.core.repositories import (
    HistoryRepository,
    JsonHistoryRepository,
    JsonPortfolioRepository,
    PortfolioRepository,
)
from src.utils.logger.logger import logger

# --- Configuration ---
DATA_DIR: str = os.path.join(os.path.dirname(__file__), "../..", "data")
PORTFOLIO_FILE: str = os.path.join(DATA_DIR, "portfolio.json")
HISTORY_FILE: str = os.path.join(DATA_DIR, "history.json")


def get_snapshot(
    portfolio_repo: PortfolioRepository | None = None,
    max_workers: int = 5,
) -> PortfolioSnapshot | None:
    """Calculates the current value of all assets in the portfolio concurrently."""
    logger.section("Getting Portfolio Snapshot")

    repo: PortfolioRepository = portfolio_repo or JsonPortfolioRepository(
        PORTFOLIO_FILE
    )

    try:
        assets: list[Asset] = repo.load_assets()
    except StorageError as e:
        logger.error(f"Error reading portfolio repository: {e}", exception=e)
        return None

    if not assets:
        return PortfolioSnapshot(
            timestamp=datetime.now().isoformat(),
            total_value_eur=0.0,
            assets_snapshot=[],
        )

    def fetch_asset_quotation(asset: Asset) -> tuple[Asset, Quotation | None]:
        raw_quotation = get_quotation(asset.yahoo_ticker)
        if not raw_quotation:
            return asset, None
        if isinstance(raw_quotation, Quotation):
            return asset, raw_quotation
        if isinstance(raw_quotation, dict):
            return asset, Quotation(
                price=float(raw_quotation["price"]),
                currency=str(raw_quotation.get("currency", "N/A")),
            )
        return asset, None

    quotations_map: dict[str, Quotation] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_asset_quotation, asset) for asset in assets]
        for future in as_completed(futures):
            asset, fetched_quotation = future.result()
            if fetched_quotation:
                quotations_map[asset.yahoo_ticker] = fetched_quotation
            else:
                logger.warning(f"Skipping {asset.yahoo_ticker} from calculation.")

    assets_snapshot: list[AssetSnapshot] = []
    total_portfolio_value_eur: float = 0.0
    exchange_rates_cache: dict[str, float | None] = {"EUR": 1.0}

    for asset in assets:
        quotation: Quotation | None = quotations_map.get(asset.yahoo_ticker)
        if not quotation:
            continue

        native_price: float = quotation.price
        native_currency: str = quotation.currency.upper()
        value_native: float = native_price * asset.quantity

        if native_currency not in exchange_rates_cache:
            exchange_rates_cache[native_currency] = get_exchange_rate(
                native_currency, "EUR"
            )

        rate: float | None = exchange_rates_cache[native_currency]
        if rate is None:
            logger.warning(
                f"Could not retrieve exchange rate for {native_currency}. "
                f"Skipping {asset.yahoo_ticker} from calculation."
            )
            continue

        value_eur: float = value_native * rate

        assets_snapshot.append(
            AssetSnapshot(
                name=asset.name,
                isin=asset.isin,
                yahoo_ticker=asset.yahoo_ticker,
                native_price=native_price,
                native_currency=native_currency,
                value_eur=round(value_eur, 2),
            )
        )
        total_portfolio_value_eur += value_eur

    return PortfolioSnapshot(
        timestamp=datetime.now().isoformat(),
        total_value_eur=round(total_portfolio_value_eur, 2),
        assets_snapshot=assets_snapshot,
    )


def display_snapshot(snapshot_data: PortfolioSnapshot | dict[str, Any]) -> None:
    """Prints a formatted summary of a snapshot to the console."""
    logger.section("Displaying Snapshot")

    snapshot: PortfolioSnapshot = (
        snapshot_data
        if isinstance(snapshot_data, PortfolioSnapshot)
        else PortfolioSnapshot.from_dict(snapshot_data)
    )

    logger.info(f"Timestamp: {snapshot.timestamp}")
    logger.info(f"Total Portfolio Value: {snapshot.total_value_eur:.2f} EUR")

    for asset in snapshot.assets_snapshot:
        logger.print(f"  - {asset.name}: {asset.value_eur:.2f} EUR")


def save_snapshot(
    snapshot_data: PortfolioSnapshot | dict[str, Any],
    history_repo: HistoryRepository | None = None,
) -> None:
    """Appends a snapshot to the history storage."""
    logger.section("Saving Snapshot")

    snapshot: PortfolioSnapshot = (
        snapshot_data
        if isinstance(snapshot_data, PortfolioSnapshot)
        else PortfolioSnapshot.from_dict(snapshot_data)
    )

    repo: HistoryRepository = history_repo or JsonHistoryRepository(HISTORY_FILE)

    try:
        repo.save_snapshot(snapshot)
    except StorageError as e:
        logger.error(f"Failed to write history snapshot: {e}", exception=e)
        return

    logger.success(f"Snapshot successfully saved to {HISTORY_FILE}")
