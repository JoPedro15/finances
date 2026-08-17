"""
Unit tests for data providers in src/core/providers.py.
"""

from unittest.mock import MagicMock, patch

from src.core.models import Asset, ETFDetails, Quotation, StockDetails
from src.core.providers import ETFProvider, StockProvider


@patch("src.core.providers.get_quotation")
def test_stock_provider_get_price(mock_get_quote: MagicMock) -> None:
    """Validates StockProvider returns price quotation via get_quotation."""
    mock_get_quote.return_value = Quotation(price=150.0, currency="USD")
    asset: Asset = Asset(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=10.0,
        average_buy_price=120.0,
    )

    provider: StockProvider = StockProvider()
    quote: Quotation | None = provider.get_price(asset)

    assert quote is not None
    assert quote.price == 150.0
    assert quote.currency == "USD"
    mock_get_quote.assert_called_once_with("AAPL")


@patch("src.core.providers.yf.Ticker")
def test_stock_provider_get_details_success(
    mock_ticker_cls: MagicMock,
) -> None:
    """Validates StockProvider parses yfinance info dictionary correctly."""
    mock_ticker_inst: MagicMock = MagicMock()
    mock_ticker_inst.info = {
        "marketCap": 3000000000000.0,
        "trailingPE": 32.5,
        "forwardPE": 28.0,
        "dividendYield": 0.0055,
        "fiftyTwoWeekHigh": 235.0,
        "fiftyTwoWeekLow": 165.0,
        "sector": "Technology",
        "industry": "Consumer Electronics",
    }
    mock_ticker_cls.return_value = mock_ticker_inst

    provider: StockProvider = StockProvider()
    asset: Asset = Asset(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=10.0,
        average_buy_price=120.0,
    )

    details: StockDetails | None = provider.get_details(asset)

    assert details is not None
    assert details.market_cap == 3000000000000.0
    assert details.pe_ratio == 32.5
    assert details.forward_pe == 28.0
    assert details.dividend_yield_pct == 0.55
    assert details.fifty_two_week_high == 235.0
    assert details.fifty_two_week_low == 165.0
    assert details.sector == "Technology"
    assert details.industry == "Consumer Electronics"


def test_stock_provider_get_details_missing_ticker() -> None:
    """Validates StockProvider returns None when yahoo_ticker is missing."""
    provider: StockProvider = StockProvider()
    asset: Asset = Asset(
        name="No Ticker",
        isin="US0000000000",
        yahoo_ticker="",
        quantity=1.0,
        average_buy_price=10.0,
    )

    assert provider.get_details(asset) is None


@patch("src.core.providers.yf.Ticker")
def test_stock_provider_get_details_handles_exception(
    mock_ticker_cls: MagicMock,
) -> None:
    """Validates StockProvider handles network or parsing exceptions gracefully."""
    mock_ticker_cls.side_effect = Exception("Network error")

    provider: StockProvider = StockProvider()
    asset: Asset = Asset(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=10.0,
        average_buy_price=120.0,
    )

    assert provider.get_details(asset) is None


@patch("src.core.providers.get_quotation")
def test_etf_provider_uses_cache_hit(mock_get_quote: MagicMock) -> None:
    """Validates ETFProvider uses cached ETF composition when present."""
    mock_get_quote.return_value = Quotation(price=100.0, currency="EUR")
    mock_cache: MagicMock = MagicMock()
    sample_details: ETFDetails = ETFDetails(
        holdings=[], sector_breakdown=[], country_breakdown=[], ter_pct=0.20
    )
    mock_cache.get_etf_details.return_value = sample_details

    mock_client: MagicMock = MagicMock()

    provider: ETFProvider = ETFProvider(
        justetf_client=mock_client, cache_repo=mock_cache
    )
    asset: Asset = Asset(
        name="Core MSCI World",
        isin="IE00B4L5Y983",
        yahoo_ticker="EUNL.DE",
        quantity=5.0,
        average_buy_price=80.0,
    )

    quote: Quotation | None = provider.get_price(asset)
    details: ETFDetails | None = provider.get_details(asset)

    assert quote is not None
    assert quote.price == 100.0
    assert details == sample_details
    mock_cache.get_etf_details.assert_called_once_with("IE00B4L5Y983")
    mock_client.get_etf_details.assert_not_called()


def test_etf_provider_cache_miss_fetches_and_saves() -> None:
    """Validates ETFProvider fetches from scraper and caches on cache miss."""
    mock_cache: MagicMock = MagicMock()
    mock_cache.get_etf_details.return_value = None

    sample_details: ETFDetails = ETFDetails(
        holdings=[], sector_breakdown=[], country_breakdown=[], ter_pct=0.20
    )
    mock_client: MagicMock = MagicMock()
    mock_client.get_etf_details.return_value = sample_details

    provider: ETFProvider = ETFProvider(
        justetf_client=mock_client, cache_repo=mock_cache
    )
    asset: Asset = Asset(
        name="Core MSCI World",
        isin="IE00B4L5Y983",
        yahoo_ticker="EUNL.DE",
        quantity=5.0,
        average_buy_price=80.0,
    )

    details: ETFDetails | None = provider.get_details(asset)

    assert details == sample_details
    mock_client.get_etf_details.assert_called_once_with("IE00B4L5Y983")
    mock_cache.save_etf_details.assert_called_once_with("IE00B4L5Y983", sample_details)
