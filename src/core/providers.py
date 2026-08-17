"""
Data provider abstractions and implementations for stocks and ETFs.
"""

from __future__ import annotations

from typing import Protocol

from src.core.get_quotation import get_quotation
from src.core.models import Asset, ETFDetails, Quotation
from src.core.repositories import ETFCacheRepository, JsonETFCacheRepository
from src.infra.justetf.client import JustETFClient
from src.utils.logger.logger import logger


class AssetDataProvider(Protocol):
    """Protocol defining operations for fetching asset price and metadata."""

    def get_price(self, asset: Asset) -> Quotation | None:
        """Fetches the current market quotation for an asset."""
        ...

    def get_details(self, asset: Asset) -> ETFDetails | None:
        """Fetches extended details (e.g., ETF composition), if applicable."""
        ...


class StockProvider:
    """Data provider for standard equity/stock assets using yfinance."""

    def get_price(self, asset: Asset) -> Quotation | None:
        """Retrieves real-time quotation for a single stock using yfinance."""
        return get_quotation(asset.yahoo_ticker)

    def get_details(self, asset: Asset) -> ETFDetails | None:
        """Stocks do not contain ETF composition details."""
        return None


class ETFProvider:
    """Hybrid provider for ETFs combining yfinance and JustETF metadata."""

    def __init__(
        self,
        justetf_client: JustETFClient | None = None,
        cache_repo: ETFCacheRepository | None = None,
    ) -> None:
        self.justetf_client: JustETFClient = justetf_client or JustETFClient()
        self.cache_repo: ETFCacheRepository = cache_repo or JsonETFCacheRepository()

    def get_price(self, asset: Asset) -> Quotation | None:
        """Retrieves real-time ETF market quotation via yfinance."""
        return get_quotation(asset.yahoo_ticker)

    def get_details(self, asset: Asset) -> ETFDetails | None:
        """Retrieves ETF composition, checking local cache before scraping."""
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
