# utils/dip_detector.py
# This file contains utilities for detecting stock price dips from recent peaks.

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pandas as pd  # type: ignore[import-untyped]
import yfinance as yf  # type: ignore[import-untyped]

# Import the custom logger instance
from .logger.logger import logger


def load_watchlist(
    file_path: str = "data/watchlist.json",
) -> List[Dict[str, str]]:
    """
    Loads the watchlist configuration from a JSON file.

    Args:
        file_path (str): Path to the watchlist JSON file.

    Returns:
        List of dictionaries containing asset metadata (name, isin, ticker).
    """
    path: Path = Path(file_path)
    if not path.exists():
        logger.error(f"Watchlist file not found at '{file_path}'.")
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            data: List[Dict[str, str]] = json.load(file)
            return data
    except Exception as e:
        logger.error(f"Error loading watchlist from '{file_path}'", exception=e)
        return []


def detect_dip(
    ticker: str,
    min_drop_pct: float = 5.0,
    max_drop_pct: float = 10.0,
    lookback_days: int = 30,
) -> Optional[Dict[str, Any]]:
    """
    Detects if a stock has experienced a dip between min_drop_pct and max_drop_pct
    relative to its highest price (peak) in the specified lookback window.

    Args:
        ticker (str): Stock ticker symbol (e.g., "AAPL").
        min_drop_pct (float): Minimum drop percentage threshold (default: 5.0).
        max_drop_pct (float): Maximum drop percentage threshold (default: 10.0).
        lookback_days (int): Number of days to look back for peak price (default: 30).

    Returns:
        A dictionary containing dip details if within range, or None otherwise.
    """
    try:
        stock: yf.Ticker = yf.Ticker(ticker)
        history: pd.DataFrame = stock.history(period=f"{lookback_days}d")

        if history.empty or len(history) < 2:
            logger.error(f"Insufficient historical data for ticker '{ticker}'.")
            return None

        peak_price: float = float(history["High"].max())
        current_price: float = float(history["Close"].iloc[-1])

        if peak_price <= 0:
            return None

        drop_pct: float = ((peak_price - current_price) / peak_price) * 100.0

        if min_drop_pct <= drop_pct <= max_drop_pct:
            peak_idx: Any = history["High"].idxmax()
            peak_date: str = pd.to_datetime(peak_idx).strftime("%Y-%m-%d")

            return {
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "peak_price": round(peak_price, 2),
                "peak_date": peak_date,
                "drop_pct": round(drop_pct, 2),
            }

        return None

    except Exception as e:
        logger.error(f"Error analyzing dip for ticker {ticker}", exception=e)
        return None


def scan_watchlist(
    items: List[Dict[str, str]],
    min_drop_pct: float = 5.0,
    max_drop_pct: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Scans a list of watchlist items and returns candidates currently in the dip range.

    Args:
        items (List[Dict[str, str]]): List of dictionaries containing asset details.
        min_drop_pct (float): Minimum drop percentage threshold.
        max_drop_pct (float): Maximum drop percentage threshold.

    Returns:
        A list of dictionaries containing dip details for matching tickers.
    """
    results: List[Dict[str, Any]] = []

    for item in items:
        ticker: str = item.get("ticker", "")
        name: str = item.get("name", ticker)
        if not ticker:
            continue

        logger.info(f"Scanning asset: {name} ({ticker})")
        dip_data: Optional[Dict[str, Any]] = detect_dip(
            ticker=ticker,
            min_drop_pct=min_drop_pct,
            max_drop_pct=max_drop_pct,
        )
        if dip_data:
            dip_data["name"] = name
            isin: str = item.get("isin", "")
            if isin:
                dip_data["isin"] = isin
            results.append(dip_data)

    return results


if __name__ == "__main__":
    watchlist_items: List[Dict[str, str]] = []

    if len(sys.argv) > 1:
        watchlist_items = [
            {"ticker": arg.upper(), "name": arg.upper()} for arg in sys.argv[1:]
        ]
    else:
        logger.info("No tickers passed in CLI, loading data/watchlist.json...")
        watchlist_items = load_watchlist()

    logger.section("Scanning watchlist for price dips...")
    matches: List[Dict[str, Any]] = scan_watchlist(watchlist_items)

    if matches:
        logger.info(f"Found {len(matches)} dip opportunities:")
        for match in matches:
            logger.info(f" -> {match}")
    else:
        logger.info("No tickers met the dip criteria.")
