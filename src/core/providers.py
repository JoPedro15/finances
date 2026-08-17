"""
Data provider abstractions and implementations for stocks and ETFs.
"""

from __future__ import annotations

from typing import Any, Protocol

import yfinance as yf  # type: ignore[import-untyped]

from src.core.get_quotation import get_quotation
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
        """Retrieves real-time quotation for a single stock using yfinance."""
        return get_quotation(asset.yahoo_ticker)

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

            raw_div: Any = info.get("dividendYield")
            dividend_yield_pct: float | None = None
            if raw_div is not None:
                try:
                    val_float: float = float(raw_div)
                    dividend_yield_pct = (
                        round(val_float * 100.0, 4) if val_float < 1.0 else val_float
                    )
                except (ValueError, TypeError):
                    dividend_yield_pct = None

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
    ) -> None:
        self.justetf_client: JustETFClient = justetf_client or JustETFClient()
        self.cache_repo: ETFCacheRepository = cache_repo or JsonETFCacheRepository()

    def get_price(self, asset: Asset) -> Quotation | None:
        """Retrieves real-time ETF market quotation via yfinance."""
        return get_quotation(asset.yahoo_ticker)

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
