# utils/get_quotation.py
# This file contains functions for obtaining financial market data.

import sys
from datetime import datetime
from typing import Any, Dict, Optional
import yfinance as yf  # type: ignore[import-untyped]

# Import the custom logger instance
from .logger.logger import logger


def get_quotation(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Gets the latest quotation for a stock.

    This function retrieves the latest market price for a given stock ticker,
    logs the result to the console, and returns it as a dictionary.

    Args:
        ticker (str): The stock ticker symbol (e.g., "AAPL").

    Returns:
        A dictionary containing 'price', 'currency', and 'timestamp' on success,
        or None on failure.
    """
    try:
        stock: yf.Ticker = yf.Ticker(ticker)
        info: Dict[str, Any] = stock.info

        price: Optional[float] = info.get("regularMarketPrice")

        if not price:
            hist = stock.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        if price:
            currency: str = info.get("currency", "N/A")
            timestamp: datetime = datetime.now()

            return {"price": price, "currency": currency, "timestamp": timestamp}
        else:
            error_message: str = (
                f"Could not retrieve quotation for ticker '{ticker}'. "
                "Please check if the ticker is correct."
            )
            logger.error(error_message)
            return None

    except Exception as e:
        logger.error(f"Error contacting the API for ticker {ticker}", exception=e)
        return None


def get_exchange_rate(from_currency: str, to_currency: str = "EUR") -> Optional[float]:
    """
    Gets the current exchange rate to convert from one currency to another.

    Args:
        from_currency (str): The source currency code (e.g., "USD", "GBP").
        to_currency (str): The target currency code (default: "EUR").

    Returns:
        The multiplier rate as a float on success, or None on failure.
    """
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

        logger.error(f"Could not retrieve exchange rate for symbol '{pair_symbol}'.")
        return None
    except Exception as e:
        logger.error(
            f"Error retrieving exchange rate for {from_curr}/{to_curr}", exception=e
        )
        return None


def get_usd_to_eur_rate() -> Optional[float]:
    """
    Gets the current USD to EUR conversion rate.
    Maintained for backward compatibility.

    Returns:
        The conversion rate as a float on success, or None on failure.
    """
    return get_exchange_rate("USD", "EUR")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Ticker not provided.")
        logger.info("Usage: python3 utils/get_quotation.py <TICKER>")
        sys.exit(1)

    ticker_to_test: str = sys.argv[1].upper()
    logger.section(f"Getting quotation for: {ticker_to_test}")
    get_quotation(ticker_to_test)
