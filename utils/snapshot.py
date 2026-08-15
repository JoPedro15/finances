# utils/snapshot.py
# This file contains the logic for creating and managing portfolio value snapshots.

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Import helper functions and the logger from the same utils package
from .get_quotation import get_quotation, get_usd_to_eur_rate
from .logger.logger import logger

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PORTFOLIO_FILE: str = os.path.join(DATA_DIR, "portfolio.json")
HISTORY_FILE: str = os.path.join(DATA_DIR, "history.json")


def get_snapshot() -> Optional[Dict[str, Any]]:
    """
    Calculates the current value of all assets in the portfolio.
    
    Returns:
        A dictionary representing the portfolio snapshot, or None on failure.
    """
    logger.section("Getting Portfolio Snapshot")
    
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            portfolio: Dict[str, Any] = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Error reading portfolio file", exception=e)
        return None

    usd_to_eur_rate = get_usd_to_eur_rate()
    if not usd_to_eur_rate:
        logger.error("Could not retrieve the USD/EUR exchange rate. Aborting.")
        return None

    assets_snapshot: List[Dict[str, Any]] = []
    total_portfolio_value_eur: float = 0.0

    for asset in portfolio.get("assets", []):
        yahoo_ticker: str = asset["yahoo_ticker"]
        quotation = get_quotation(yahoo_ticker)
        
        if not quotation:
            logger.warning(f"Skipping {yahoo_ticker} from calculation.")
            continue

        native_price: float = quotation["price"]
        native_currency: str = quotation["currency"]
        quantity: float = asset["quantity"]
        value_native: float = native_price * quantity
        
        value_eur: float = value_native
        if native_currency == "USD":
            value_eur = value_native / usd_to_eur_rate
        
        assets_snapshot.append({
            "name": asset["name"],
            "isin": asset["isin"],
            "yahoo_ticker": yahoo_ticker,
            "native_price": native_price,
            "native_currency": native_currency,
            "value_eur": round(value_eur, 2)
        })
        total_portfolio_value_eur += value_eur

    return {
        "timestamp": datetime.now().isoformat(),
        "total_value_eur": round(total_portfolio_value_eur, 2),
        "assets_snapshot": assets_snapshot
    }


def display_snapshot(snapshot_data: Dict[str, Any]) -> None:
    """
    Prints a formatted summary of a snapshot to the console.
    """
    logger.section("Displaying Snapshot")
    logger.info(f"Timestamp: {snapshot_data['timestamp']}")
    logger.info(f"Total Portfolio Value: {snapshot_data['total_value_eur']:.2f} EUR")
    
    for asset in snapshot_data['assets_snapshot']:
        logger.print(
            f"  - {asset['name']}: {asset['value_eur']:.2f} EUR"
        )


def save_snapshot(snapshot_data: Dict[str, Any]) -> None:
    """
    Appends a snapshot to the history file.
    """
    logger.section("Saving Snapshot")
    try:
        with open(HISTORY_FILE, 'r') as f:
            history: List[Dict[str, Any]] = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []

    history.append(snapshot_data)

    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

    logger.success(f"Snapshot successfully saved to {HISTORY_FILE}")
