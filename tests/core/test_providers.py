"""
Unit tests for data providers in src/core/providers.py.
"""

from unittest.mock import MagicMock, patch

from src.core.models import Asset, ETFDetails, Quotation
from src.core.providers import ETFProvider, StockProvider


@patch("src.core.providers.get_quotation")
def test_stock_provider_get_price(mock_get_quote: MagicMock) -> None:
    mock_get_quote.return_value = Quotation(price=150.0, currency="USD")
    asset: Asset = Asset(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=10,
        average_buy_price=120.0,
    )

    provider: StockProvider = StockProvider()
    quote: Quotation | None = provider.get_price(asset)

    assert quote is not None
    assert quote.price == 150.0
    assert quote.currency == "USD"
    assert provider.get_details(asset) is None
    mock_get_quote.assert_called_once_with("AAPL")


@patch("src.core.providers.get_quotation")
def test_etf_provider_uses_cache_hit(mock_get_quote: MagicMock) -> None:
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
        quantity=5,
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
        quantity=5,
        average_buy_price=80.0,
    )

    details: ETFDetails | None = provider.get_details(asset)

    assert details == sample_details
    mock_client.get_etf_details.assert_called_once_with("IE00B4L5Y983")
    mock_cache.save_etf_details.assert_called_once_with("IE00B4L5Y983", sample_details)
