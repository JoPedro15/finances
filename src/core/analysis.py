"""
This file contains functions for analyzing portfolio performance.
"""

from __future__ import annotations

import os

from src.core.exceptions import StorageError
from src.core.models import Asset, PortfolioSnapshot
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


def analyze_overall_performance(
    portfolio_repo: PortfolioRepository | None = None,
    history_repo: HistoryRepository | None = None,
) -> None:
    """Analyzes performance of individual assets and the overall portfolio."""
    logger.section("Portfolio Performance Analysis")

    p_repo: PortfolioRepository = portfolio_repo or JsonPortfolioRepository(
        PORTFOLIO_FILE
    )
    h_repo: HistoryRepository = history_repo or JsonHistoryRepository(HISTORY_FILE)

    try:
        assets: list[Asset] = p_repo.load_assets()
        history: list[PortfolioSnapshot] = h_repo.load_history()

        if not history:
            logger.warning("History file is empty. Cannot perform analysis.")
            return

        latest_snapshot: PortfolioSnapshot = history[-1]
    except StorageError as e:
        logger.error(f"Could not read data files: {e}")
        return

    latest_asset_values: dict[str, float] = {
        asset.isin: asset.value_eur for asset in latest_snapshot.assets_snapshot
    }

    valid_acquisition_cost: float = 0.0
    valid_latest_value: float = 0.0

    for asset in assets:
        logger.subsection(asset.name)

        acquisition_cost: float = asset.acquisition_cost
        latest_value: float | None = latest_asset_values.get(asset.isin)

        if latest_value is None:
            logger.warning(f"No recent market data found for {asset.name}. Skipping.")
            logger.print("--------------------")
            continue

        valid_acquisition_cost += acquisition_cost
        valid_latest_value += latest_value

        logger.info(f"Acquisition Cost: {acquisition_cost:.2f} EUR")
        logger.info(f"Latest Market Value: {latest_value:.2f} EUR")

        absolute_gain: float = latest_value - acquisition_cost
        if absolute_gain >= 0:
            logger.success(f"Absolute Gain: +{absolute_gain:.2f} EUR")
        else:
            logger.warning(f"Absolute Loss: {absolute_gain:.2f} EUR")

        logger.print("--------------------")

    logger.subsection("Global Analysis")

    total_acquisition_cost: float = valid_acquisition_cost
    total_latest_value: float = valid_latest_value

    logger.info(f"Total Acquisition Cost: {total_acquisition_cost:.2f} EUR")
    logger.info(f"Latest Market Value:   {total_latest_value:.2f} EUR")

    total_absolute_gain: float = total_latest_value - total_acquisition_cost
    if total_absolute_gain >= 0:
        logger.success(f"Absolute Gain: +{total_absolute_gain:.2f} EUR")
    else:
        logger.warning(f"Absolute Loss: {total_absolute_gain:.2f} EUR")

    roi_percentage: float = (
        (total_absolute_gain / total_acquisition_cost) * 100
        if total_acquisition_cost != 0
        else 0.0
    )
    if roi_percentage >= 0:
        logger.success(f"Return on Investment (ROI): +{roi_percentage:.2f}%")
    else:
        logger.warning(f"Return on Investment (ROI): {roi_percentage:.2f}%")
