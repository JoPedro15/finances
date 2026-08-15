# utils/analysis.py
# This file contains functions for analyzing portfolio performance.

import json
import os
from typing import Dict, Any, List

from .logger.logger import logger

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PORTFOLIO_FILE: str = os.path.join(DATA_DIR, "portfolio.json")
HISTORY_FILE: str = os.path.join(DATA_DIR, "history.json")


def analyze_overall_performance():
    """
    Analyzes the performance of each asset individually and then the overall portfolio,
    comparing acquisition costs with the latest market values.
    """
    logger.section("Portfolio Performance Analysis")

    # 1. Read necessary data
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            portfolio: Dict[str, Any] = json.load(f)
        with open(HISTORY_FILE, 'r') as f:
            history: List[Dict[str, Any]] = json.load(f)
            if not history:
                logger.warning("History file is empty. Cannot perform analysis.")
                return
            latest_snapshot = history[-1]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Could not read data files: {e}")
        return

    # Create a quick lookup for latest asset values by ISIN
    latest_asset_values = {
        asset['isin']: asset['value_eur'] for asset in latest_snapshot['assets_snapshot']
    }

    # 2. Individual Asset Analysis
    for asset in portfolio.get("assets", []):
        isin = asset["isin"]
        name = asset["name"]
        
        logger.subsection(name)
        
        acquisition_cost = asset["quantity"] * asset["averageBuyPrice"]
        latest_value = latest_asset_values.get(isin)

        if latest_value is None:
            logger.warning(f"No recent market data found for {name}. Skipping.")
            logger.print("--------------------")
            continue

        logger.info(f"Acquisition Cost: {acquisition_cost:.2f} EUR")
        logger.info(f"Latest Market Value: {latest_value:.2f} EUR")

        absolute_gain = latest_value - acquisition_cost
        if absolute_gain >= 0:
            logger.success(f"Absolute Gain: +{absolute_gain:.2f} EUR")
        else:
            logger.warning(f"Absolute Loss: {absolute_gain:.2f} EUR")
        
        logger.print("--------------------")

    # 3. Global Analysis
    logger.subsection("Global Analysis")
    
    total_acquisition_cost = sum(
        a["quantity"] * a["averageBuyPrice"] for a in portfolio.get("assets", [])
    )
    total_latest_value = latest_snapshot["total_value_eur"]
    
    logger.info(f"Total Acquisition Cost: {total_acquisition_cost:.2f} EUR")
    logger.info(f"Latest Market Value:   {total_latest_value:.2f} EUR")

    total_absolute_gain = total_latest_value - total_acquisition_cost
    if total_absolute_gain >= 0:
        logger.success(f"Absolute Gain: +{total_absolute_gain:.2f} EUR")
    else:
        logger.warning(f"Absolute Loss: {total_absolute_gain:.2f} EUR")

    roi_percentage = (total_absolute_gain / total_acquisition_cost) * 100 if total_acquisition_cost != 0 else 0
    if roi_percentage >= 0:
        logger.success(f"Return on Investment (ROI): +{roi_percentage:.2f}%")
    else:
        logger.warning(f"Return on Investment (ROI): {roi_percentage:.2f}%")
