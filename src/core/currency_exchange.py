"""Utility module for fetching real-time currency exchange rates using yfinance."""

from __future__ import annotations

import sys
from typing import Any

import yfinance as yf  # type: ignore[import-untyped]

from src.core.exceptions import ExchangeRateFetchError
from src.utils.logger.logger import logger


def get_exchange_rate(from_currency: str, to_currency: str = "EUR") -> float | None:
    """Gets the current exchange rate to convert from one currency to another."""
    from_curr: str = from_currency.upper()
    to_curr: str = to_currency.upper()

    if from_curr == to_curr:
        return 1.0

    try:
        pair_symbol: str = f"{from_curr}{to_curr}=X"
        pair_ticker: yf.Ticker = yf.Ticker(pair_symbol)
        hist: Any = pair_ticker.history(period="1d")

        if not hist.empty:
            rate: float = float(hist["Close"].iloc[-1])
            return rate

        raise ExchangeRateFetchError(
            f"Could not retrieve exchange rate for symbol '{pair_symbol}'."
        )
    except Exception as e:
        err: ExchangeRateFetchError = ExchangeRateFetchError(
            f"Error retrieving exchange rate for {from_curr}/{to_curr}: {e}"
        )
        logger.error(str(err), exception=e)
        return None


def get_usd_to_eur_rate() -> float | None:
    """Gets the current USD to EUR conversion rate."""
    return get_exchange_rate("USD", "EUR")


def main() -> None:
    """CLI execution entry point for currency exchange lookup."""
    if len(sys.argv) < 3:
        logger.error("Currencies not provided.")
        logger.info(
            "Usage: python3 -m src.core.currency_exchange <FROM_CURRENCY> <TO_CURRENCY>"
        )
        sys.exit(1)

    from_c: str = sys.argv[1].upper()
    to_c: str = sys.argv[2].upper()
    rate_val: float | None = get_exchange_rate(from_c, to_c)
    logger.info(f"Exchange rate {from_c}/{to_c}: {rate_val}")


if __name__ == "__main__":
    main()
