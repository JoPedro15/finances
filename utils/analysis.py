# utils/analysis.py
# This file contains functions for analyzing portfolio performance.

import json
import os
from typing import Dict, Any, List, Optional

from .logger.logger import logger

# --- Configuration ---
DATA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "data")
PORTFOLIO_FILE: str = os.path.join(DATA_DIR, "portfolio.json")
HISTORY_FILE: str = os.path.join(DATA_DIR, "history.json")


def analyze_overall_performance() -> None:
    """
    Analyzes the performance of each asset individually and then the overall portfolio,
    comparing acquisition costs with the latest market values.
    """
    logger.section("Portfolio Performance Analysis")

    # 1. Read necessary data
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            portfolio: Dict[str, Any] = json.load(f)
        with open(HISTORY_FILE, "r") as f:
            history: List[Dict[str, Any]] = json.load(f)
            if not history:
                logger.warning("History file is empty. Cannot perform analysis.")
                return
            latest_snapshot: Dict[str, Any] = history[-1]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Could not read data files: {e}")
        return

    # Create a quick lookup for latest asset values by ISIN
    latest_asset_values: Dict[str, float] = {
        asset["isin"]: asset["value_eur"]
        for asset in latest_snapshot.get("assets_snapshot", [])
    }

    # Track valid acquisition cost and market value for assets present in the snapshot
    valid_acquisition_cost: float = 0.0
    valid_latest_value: float = 0.0

    # 2. Individual Asset Analysis
    for asset in portfolio.get("assets", []):
        isin: str = asset["isin"]
        name: str = asset["name"]

        logger.subsection(name)

        acquisition_cost: float = asset["quantity"] * asset["averageBuyPrice"]
        latest_value: Optional[float] = latest_asset_values.get(isin)

        if latest_value is None:
            logger.warning(f"No recent market data found for {name}. Skipping.")
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

    # 3. Global Analysis
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
