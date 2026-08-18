"""
Unit tests for portfolio snapshot logic in src/core/snapshot.py.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import Asset, PortfolioSnapshot, Quotation
from src.core.snapshot import get_snapshot


@pytest.fixture(autouse=True)
def mock_provider_details() -> Generator[None]:
    """Mocks provider details to prevent unmocked yfinance SQLite cache
    initialization.
    """
    with (
        patch("src.core.providers.StockProvider.get_details", return_value=None),
        patch("src.core.providers.ETFProvider.get_details", return_value=None),
    ):
        yield


@pytest.fixture
def sample_assets() -> list[Asset]:
    return [
        Asset(
            name="Apple Inc.",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=10,
            average_buy_price=150.0,
        ),
        Asset(
            name="iShares MSCI World",
            isin="IE00B4L5Y983",
            yahoo_ticker="EUNL.DE",
            quantity=5,
            average_buy_price=80.0,
        ),
    ]


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.providers.StockProvider.get_price")
def test_get_snapshot_multi_currency(
    mock_get_price: MagicMock,
    mock_get_fx: MagicMock,
    sample_assets: list[Asset],
) -> None:
    def price_side_effect(asset: Asset) -> Quotation | None:
        if asset.yahoo_ticker == "AAPL":
            return Quotation(price=180.0, currency="USD")
        if asset.yahoo_ticker == "EUNL.DE":
            return Quotation(price=85.0, currency="EUR")
        return None

    mock_get_price.side_effect = price_side_effect
    mock_get_fx.return_value = 0.90  # 1 USD = 0.90 EUR

    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = sample_assets

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    assert len(snapshot.assets_snapshot) == 2
    # AAPL: 10 * 180 USD * 0.90 = 1620.00 EUR
    # EUNL: 5 * 85 EUR * 1.0 = 425.00 EUR
    # Total: 2045.00 EUR
    assert snapshot.total_value_eur == 2045.00


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.providers.StockProvider.get_price")
def test_get_snapshot_currency_caching(
    mock_get_price: MagicMock,
    mock_get_fx: MagicMock,
    sample_assets: list[Asset],
) -> None:
    mock_get_price.return_value = Quotation(price=100.0, currency="USD")
    mock_get_fx.return_value = 0.85

    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = sample_assets

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    mock_get_fx.assert_called_once_with("USD", "EUR")


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.providers.StockProvider.get_price")
def test_get_snapshot_missing_asset_quotation(
    mock_get_price: MagicMock,
    mock_get_fx: MagicMock,
    sample_assets: list[Asset],
) -> None:
    mock_get_price.side_effect = [None, Quotation(price=80.0, currency="EUR")]

    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = sample_assets

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    assert len(snapshot.assets_snapshot) == 1
    assert snapshot.assets_snapshot[0].yahoo_ticker == "EUNL.DE"


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.providers.StockProvider.get_price")
def test_get_snapshot_exchange_rate_failure(
    mock_get_price: MagicMock,
    mock_get_fx: MagicMock,
    sample_assets: list[Asset],
) -> None:
    mock_get_price.return_value = Quotation(price=100.0, currency="USD")
    mock_get_fx.return_value = None

    mock_repo: MagicMock = MagicMock()
    mock_repo.load_assets.return_value = sample_assets

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    assert len(snapshot.assets_snapshot) == 0
    assert snapshot.total_value_eur == 0.0
