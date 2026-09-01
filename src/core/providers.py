"""Data provider abstractions and implementations for stocks and ETFs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

import yfinance as yf  # type: ignore[import-untyped]

from src.core.currency_exchange import get_exchange_rate
from src.core.models import (
    Asset,
    CountryExposure,
    ETFDetails,
    Quotation,
    SectorExposure,
    StockDetails,
)
from src.core.repositories import ETFCacheRepository, JsonETFCacheRepository
from src.infra.justetf.client import JustETFClient
from src.utils.logger.logger import logger


class AssetDataProvider(Protocol):
    """Protocol defining operations for fetching asset price and metadata."""

    def get_price(self, asset: Asset) -> Quotation | None: ...

    def get_details(
        self, asset: Asset, force_refresh: bool = False
    ) -> ETFDetails | StockDetails | None: ...


class StockProvider:
    """Data provider for standard equity/stock assets using yfinance."""

    def get_price(self, asset: Asset) -> Quotation | None:
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

    def get_details(
        self, asset: Asset, force_refresh: bool = False
    ) -> StockDetails | None:
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

            def _parse_pct(key: str) -> float | None:
                val: Any = info.get(key)
                if val is None:
                    return None
                try:
                    return round(float(val) * 100.0, 4)
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
                price_to_book=_parse_float("priceToBook"),
                peg_ratio=_parse_float("pegRatio"),
                beta=_parse_float("beta"),
                profit_margins_pct=_parse_pct("profitMargins"),
                revenue_growth_pct=_parse_pct("revenueGrowth"),
                earnings_growth_pct=_parse_pct("earningsGrowth"),
                total_debt_to_equity=_parse_float("debtToEquity"),
                target_mean_price=_parse_float("targetMeanPrice"),
                recommendation_key=_parse_str("recommendationKey"),
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
        return self._stock_provider.get_price(asset)

    def _apply_benchmark_fallback(
        self, asset: Asset, details: ETFDetails
    ) -> ETFDetails:
        """Applies benchmark profile fallback when breakdowns are missing."""
        name_upper: str = asset.name.upper()
        country_breakdown: list[CountryExposure] = (
            list(details.country_breakdown) if details.country_breakdown else []
        )
        sector_breakdown: list[SectorExposure] = (
            list(details.sector_breakdown) if details.sector_breakdown else []
        )

        # Fallback 1: Benchmark S&P 500 detection
        if "S&P 500" in name_upper or "SP500" in name_upper:
            if not country_breakdown:
                country_breakdown = [
                    CountryExposure(country_name="United States", weight_pct=100.0)
                ]
            if not sector_breakdown:
                sector_breakdown = [
                    SectorExposure(sector_name="Technology", weight_pct=31.5),
                    SectorExposure(sector_name="Finance", weight_pct=13.0),
                    SectorExposure(sector_name="Healthcare", weight_pct=11.5),
                    SectorExposure(sector_name="Consumer Cyclicals", weight_pct=10.0),
                    SectorExposure(sector_name="Communication", weight_pct=9.0),
                    SectorExposure(sector_name="Industrials", weight_pct=8.5),
                    SectorExposure(sector_name="Other", weight_pct=16.5),
                ]

        # Fallback 2: Benchmark MSCI World detection
        elif "MSCI WORLD" in name_upper:
            if not country_breakdown:
                country_breakdown = [
                    CountryExposure(country_name="United States", weight_pct=70.0),
                    CountryExposure(country_name="Japan", weight_pct=6.0),
                    CountryExposure(country_name="United Kingdom", weight_pct=4.0),
                    CountryExposure(country_name="Other", weight_pct=20.0),
                ]
            if not sector_breakdown:
                sector_breakdown = [
                    SectorExposure(sector_name="Technology", weight_pct=25.0),
                    SectorExposure(sector_name="Finance", weight_pct=15.0),
                    SectorExposure(sector_name="Healthcare", weight_pct=12.0),
                    SectorExposure(sector_name="Industrials", weight_pct=11.0),
                    SectorExposure(sector_name="Other", weight_pct=37.0),
                ]

        return ETFDetails(
            holdings=details.holdings,
            sector_breakdown=sector_breakdown,
            country_breakdown=country_breakdown,
            ter_pct=details.ter_pct,
        )

    def get_details(
        self, asset: Asset, force_refresh: bool = False
    ) -> ETFDetails | None:
        """Retrieves ETF composition, verifying breakdown validity before caching."""
        if not asset.isin:
            logger.error(f"No ISIN provided for ETF asset {asset.name}.")
            return None

        if not force_refresh:
            cached_details: ETFDetails | None = self.cache_repo.get_etf_details(
                asset.isin
            )
            if cached_details is not None:
                if (
                    cached_details.sector_breakdown
                    or cached_details.country_breakdown
                ):
                    return cached_details

        try:
            details: ETFDetails = self.justetf_client.get_etf_details(asset.isin)
            details = self._apply_benchmark_fallback(asset, details)

            if details.sector_breakdown or details.country_breakdown:
                self.cache_repo.save_etf_details(asset.isin, details)
            return details
        except Exception as e:
            logger.warning(
                f"Failed to fetch ETF details for {asset.name} ({asset.isin}): {e}"
            )
            fallback_details: ETFDetails = self._apply_benchmark_fallback(
                asset,
                ETFDetails(
                    holdings=[],
                    sector_breakdown=[],
                    country_breakdown=[],
                    ter_pct=None,
                ),
            )
            if (
                fallback_details.sector_breakdown
                or fallback_details.country_breakdown
            ):
                return fallback_details
            return None