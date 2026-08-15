# This file contains functions for obtaining financial market data.

import yfinance as yf
from datetime import datetime
import sys
from typing import Dict, Any, Optional

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

        price: Optional[float] = info.get('regularMarketPrice')

        if not price:
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]

        if price:
            currency: str = info.get('currency', 'N/A')
            timestamp: datetime = datetime.now()

            return {
                "price": price,
                "currency": currency,
                "timestamp": timestamp
            }
        else:
            logger.error(f"Could not retrieve quotation for ticker '{ticker}'. Please check if the ticker is correct.")
            return None

    except Exception as e:
        logger.error(f"Error contacting the API for ticker {ticker}", exception=e)
        return None

def get_usd_to_eur_rate() -> Optional[float]:
    """
    Gets the current USD to EUR conversion rate.

    Returns:
        The conversion rate as a float on success, or None on failure.
    """
    try:
        eur_usd_pair: yf.Ticker = yf.Ticker("EURUSD=X")
        hist = eur_usd_pair.history(period="1d")
        if not hist.empty:
            rate: float = hist['Close'].iloc[-1]
            return rate
        return None
    except Exception as e:
        logger.error("Error retrieving currency exchange rate", exception=e)
        return None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.error("Ticker not provided.")
        logger.info("Usage: python3 utils/get_quotation.py <TICKER>")
        sys.exit(1)

    ticker_to_test: str = sys.argv[1].upper()
    logger.section(f"Getting quotation for: {ticker_to_test}")
    get_quotation(ticker_to_test)
