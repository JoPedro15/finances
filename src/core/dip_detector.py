"""
This file contains utilities for detecting stock price dips from recent peaks.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

from src.config import DEFAULT_DIP_CONFIG
from src.core.exceptions import InvalidWatchlistError, QuotationFetchError
from src.utils.logger.logger import logger


def load_watchlist(
    file_path: str = "data/watchlist.json",
) -> list[dict[str, str]]:
    """Loads the watchlist configuration from a JSON file."""
    path: Path = Path(file_path)
    if not path.exists():
        err = InvalidWatchlistError(f"Watchlist file not found at '{file_path}'.")
        logger.error(str(err))
        return []

    try:
        with open(path, encoding="utf-8") as file:
            data: list[dict[str, str]] = json.load(file)
            return data
    except Exception as e:
        err = InvalidWatchlistError(f"Error loading watchlist from '{file_path}': {e}")
        logger.error(str(err), exception=e)
        return []


def detect_dip(
    ticker: str,
    min_drop_pct: float = DEFAULT_DIP_CONFIG.min_drop_pct,
    max_drop_pct: float = DEFAULT_DIP_CONFIG.max_drop_pct,
    lookback_days: int = DEFAULT_DIP_CONFIG.lookback_days,
) -> dict[str, Any] | None:
    """Detects if a stock has experienced a dip between
    min_drop_pct and max_drop_pct."""
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
        err = QuotationFetchError(f"Error analyzing dip for ticker {ticker}: {e}")
        logger.error(str(err), exception=e)
        return None


def scan_watchlist(
    items: list[dict[str, str]],
    min_drop_pct: float = DEFAULT_DIP_CONFIG.min_drop_pct,
    max_drop_pct: float = DEFAULT_DIP_CONFIG.max_drop_pct,
    lookback_days: int = DEFAULT_DIP_CONFIG.lookback_days,
    max_workers: int = 5,
) -> list[dict[str, Any]]:
    """Scans watchlist items concurrently preserving item order."""
    valid_items: list[dict[str, str]] = [item for item in items if item.get("ticker")]
    results: list[dict[str, Any]] = []

    if not valid_items:
        return results

    def process_item(item: dict[str, str]) -> dict[str, Any] | None:
        ticker: str = item.get("ticker", "")
        name: str = item.get("name", ticker)
        logger.info(f"Scanning asset: {name} ({ticker})")
        dip_data: dict[str, Any] | None = detect_dip(
            ticker=ticker,
            min_drop_pct=min_drop_pct,
            max_drop_pct=max_drop_pct,
            lookback_days=lookback_days,
        )
        if dip_data:
            dip_data["name"] = name
            isin: str = item.get("isin", "")
            if isin:
                dip_data["isin"] = isin
            return dip_data
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for res in executor.map(process_item, valid_items):
            if res:
                results.append(res)

    return results


if __name__ == "__main__":
    watchlist_items: list[dict[str, str]] = []

    if len(sys.argv) > 1:
        watchlist_items = [
            {"ticker": arg.upper(), "name": arg.upper()} for arg in sys.argv[1:]
        ]
    else:
        logger.info("No tickers passed in CLI, loading data/watchlist.json...")
        watchlist_items = load_watchlist()

    logger.section("Scanning watchlist for price dips...")
    matches: list[dict[str, Any]] = scan_watchlist(watchlist_items)

    if matches:
        logger.info(f"Found {len(matches)} dip opportunities:")
        for match in matches:
            logger.info(f" -> {match}")
    else:
        logger.info("No tickers met the dip criteria.")
