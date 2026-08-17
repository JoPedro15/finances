"""
This file contains functions for obtaining financial market data.
"""

import sys
from datetime import datetime
from typing import Any

import yfinance as yf  # type: ignore[import-untyped]

from src.core.exceptions import ExchangeRateFetchError, QuotationFetchError
from src.core.models import Quotation
from src.utils.logger.logger import logger


def get_quotation(ticker: str) -> Quotation | None:
    """Gets the latest quotation for a stock.

    Args:
        ticker (str): The stock ticker symbol (e.g., "AAPL").

    Returns:
        A Quotation model instance on success, or None on failure.
    """
    try:
        stock: yf.Ticker = yf.Ticker(ticker)
        info: dict[str, Any] = stock.info

        price: float | None = info.get("regularMarketPrice")

        if not price:
            hist = stock.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        if price:
            currency: str = str(info.get("currency", "N/A"))
            return Quotation(
                price=price,
                currency=currency,
                timestamp=datetime.now(),
            )

        raise QuotationFetchError(
            f"Could not retrieve quotation for ticker '{ticker}'."
        )

    except Exception as e:
        err = QuotationFetchError(f"Error contacting API for ticker '{ticker}': {e}")
        logger.error(str(err), exception=e)
        return None


def get_exchange_rate(from_currency: str, to_currency: str = "EUR") -> float | None:
    """Gets the current exchange rate to convert from one currency to another."""
    from_curr: str = from_currency.upper()
    to_curr: str = to_currency.upper()

    if from_curr == to_curr:
        return 1.0

    try:
        pair_symbol: str = f"{from_curr}{to_curr}=X"
        pair_ticker: yf.Ticker = yf.Ticker(pair_symbol)
        hist = pair_ticker.history(period="1d")

        if not hist.empty:
            rate: float = float(hist["Close"].iloc[-1])
            return rate

        raise ExchangeRateFetchError(
            f"Could not retrieve exchange rate for symbol '{pair_symbol}'."
        )
    except Exception as e:
        err = ExchangeRateFetchError(
            f"Error retrieving exchange rate for {from_curr}/{to_curr}: {e}"
        )
        logger.error(str(err), exception=e)
        return None


def get_usd_to_eur_rate() -> float | None:
    """Gets the current USD to EUR conversion rate."""
    return get_exchange_rate("USD", "EUR")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Ticker not provided.")
        logger.info("Usage: python3 utils/get_quotation.py <TICKER>")
        sys.exit(1)

    ticker_to_test: str = sys.argv[1].upper()
    logger.section(f"Getting quotation for: {ticker_to_test}")
    get_quotation(ticker_to_test)
