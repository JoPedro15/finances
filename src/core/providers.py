"""Data provider abstractions and implementations for stocks and ETFs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

import yfinance as yf  # type: ignore[import-untyped]

from src.core.currency_exchange import get_exchange_rate
from src.core.models import Asset, ETFDetails, Quotation, StockDetails
from src.core.repositories import ETFCacheRepository, JsonETFCacheRepository
from src.infra.justetf.client import JustETFClient
from src.utils.logger.logger import logger


class AssetDataProvider(Protocol):
    """Protocol defining operations for fetching asset price and metadata."""

    def get_price(self, asset: Asset) -> Quotation | None:
        """Fetches the current market quotation for an asset."""
        ...

    def get_details(self, asset: Asset) -> ETFDetails | StockDetails | None:
        """Fetches extended details (ETF composition or stock fundamentals)."""
        ...


class StockProvider:
    """Data provider for standard equity/stock assets using yfinance."""

    def get_price(self, asset: Asset) -> Quotation | None:
        """Retrieves real-time quotation for a stock, converting to EUR if necessary."""
        if not asset.yahoo_ticker:
            logger.error(f"No Yahoo ticker provided for stock asset '{asset.name}'.")
            return None

        try:
            ticker: yf.Ticker = yf.Ticker(asset.yahoo_ticker)
            info: dict[str, Any] = ticker.info

            price: float | None = (
                info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("previousClose")
            )

            if not price:
                hist: Any = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])

            if price:
                currency: str = str(info.get("currency", "EUR")).upper()
                if currency != "EUR":
                    rate: float | None = get_exchange_rate(currency, "EUR")
                    if rate:
                        price = price * rate
                        currency = "EUR"

                return Quotation(
                    price=price,
                    currency=currency,
                    timestamp=datetime.now(),
                )

            logger.error(f"Could not retrieve price for ticker '{asset.yahoo_ticker}'.")
            return None

        except Exception as e:
            logger.error(f"Error fetching quotation for '{asset.yahoo_ticker}': {e}")
            return None

    def get_details(self, asset: Asset) -> StockDetails | None:
        """Retrieves fundamental metrics for a stock via yfinance."""
        if not asset.yahoo_ticker:
            logger.error(f"No Yahoo ticker provided for stock asset '{asset.name}'.")
            return None

        try:
            ticker: yf.Ticker = yf.Ticker(asset.yahoo_ticker)
            info: dict[str, Any] = ticker.info

            if not info or not isinstance(info, dict):
                logger.error(
                    f"yfinance returned empty metadata for '{asset.yahoo_ticker}'."
                )
                return None

            def _parse_float(key: str) -> float | None:
                val: Any = info.get(key)
                if val is None:
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            def _parse_str(key: str) -> str | None:
                val: Any = info.get(key)
                return str(val) if val is not None else None

            dividend_rate: float | None = _parse_float("dividendRate") or _parse_float(
                "trailingAnnualDividendRate"
            )
            current_price: float | None = (
                _parse_float("currentPrice")
                or _parse_float("previousClose")
                or _parse_float("regularMarketPrice")
            )

            dividend_yield_pct: float | None = None
            if (
                dividend_rate is not None
                and current_price is not None
                and current_price > 0
            ):
                dividend_yield_pct = round((dividend_rate / current_price) * 100.0, 4)
            else:
                raw_div: float | None = _parse_float("dividendYield")
                if raw_div is not None:
                    dividend_yield_pct = round(raw_div, 4)

            return StockDetails(
                market_cap=_parse_float("marketCap"),
                pe_ratio=_parse_float("trailingPE"),
                forward_pe=_parse_float("forwardPE"),
                dividend_yield_pct=dividend_yield_pct,
                fifty_two_week_high=_parse_float("fiftyTwoWeekHigh"),
                fifty_two_week_low=_parse_float("fiftyTwoWeekLow"),
                sector=_parse_str("sector"),
                industry=_parse_str("industry"),
            )
        except Exception as e:
            err_details: str = f"{type(e).__name__} - {e}"
            logger.error(
                f"yfinance exception while fetching '{asset.yahoo_ticker}': "
                f"{err_details}"
            )
            return None


class ETFProvider:
    """Hybrid provider for ETFs combining yfinance and JustETF metadata."""

    def __init__(
        self,
        justetf_client: JustETFClient | None = None,
        cache_repo: ETFCacheRepository | None = None,
        stock_provider: StockProvider | None = None,
    ) -> None:
        self.justetf_client: JustETFClient = justetf_client or JustETFClient()
        self.cache_repo: ETFCacheRepository = cache_repo or JsonETFCacheRepository()
        self._stock_provider: StockProvider = stock_provider or StockProvider()

    def get_price(self, asset: Asset) -> Quotation | None:
        """Retrieves real-time ETF market quotation via yfinance."""
        return self._stock_provider.get_price(asset)

    def get_details(self, asset: Asset) -> ETFDetails | None:
        """Retrieves ETF composition, checking local cache before scraping."""
        if not asset.isin:
            logger.error(f"No ISIN provided for ETF asset {asset.name}.")
            return None

        cached_details: ETFDetails | None = self.cache_repo.get_etf_details(asset.isin)
        if cached_details is not None:
            return cached_details

        try:
            details: ETFDetails = self.justetf_client.get_etf_details(asset.isin)
            self.cache_repo.save_etf_details(asset.isin, details)
            return details
        except Exception as e:
            logger.warning(
                f"Failed to fetch ETF details for {asset.name} ({asset.isin}): {e}"
            )
            return None
