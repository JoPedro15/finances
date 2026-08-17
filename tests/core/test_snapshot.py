"""
Unit tests for src/core/snapshot.py covering snapshot
calculation, currency exchange rate failures,
display logic, file handling errors, and snapshot persistence.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from src.core.exceptions import StorageReadError
from src.core.models import Asset, PortfolioSnapshot
from src.core.repositories import JsonHistoryRepository
from src.core.snapshot import display_snapshot, get_snapshot, save_snapshot


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
def test_get_snapshot_multi_currency(
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Validates that global EUR total and native currency conversions
    are calculated accurately across multiple currencies via repository injection.
    """
    mock_repo = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=10.0,
            average_buy_price=100.0,
        ),
        Asset(
            name="SAP",
            isin="DE0007164600",
            yahoo_ticker="SAP.DE",
            quantity=5.0,
            average_buy_price=50.0,
        ),
    ]

    def quotation_side_effect(ticker: str) -> dict[str, Any] | None:
        if ticker == "AAPL":
            return {"price": 100.0, "currency": "USD", "timestamp": "2026-08-15"}
        if ticker == "SAP.DE":
            return {"price": 50.0, "currency": "EUR", "timestamp": "2026-08-15"}
        return None

    mock_get_quotation.side_effect = quotation_side_effect
    mock_get_exchange_rate.return_value = 0.90

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    assert snapshot.total_value_eur == 1150.00
    assert len(snapshot.assets_snapshot) == 2
    assert snapshot.assets_snapshot[0].value_eur == 900.00
    assert snapshot.assets_snapshot[1].value_eur == 250.00


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
def test_get_snapshot_currency_caching(
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Confirms that exchange_rates_cache reuses previously retrieved exchange rates
    for the same currency within a single snapshot cycle.
    """
    mock_repo = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=2.0,
            average_buy_price=100.0,
        ),
        Asset(
            name="Microsoft",
            isin="US5949181045",
            yahoo_ticker="MSFT",
            quantity=3.0,
            average_buy_price=100.0,
        ),
    ]
    mock_get_quotation.return_value = {
        "price": 100.0,
        "currency": "USD",
        "timestamp": "2026-08-15",
    }
    mock_get_exchange_rate.return_value = 0.85

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    mock_get_exchange_rate.assert_called_once_with("USD", "EUR")


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
def test_get_snapshot_missing_asset_quotation(
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Ensures that if an asset quotation fails, calculation skips that asset
    and processes remaining assets without crashing.
    """
    mock_repo = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Invalid Asset",
            isin="XX0000000000",
            yahoo_ticker="INVALID",
            quantity=10.0,
            average_buy_price=10.0,
        ),
        Asset(
            name="SAP",
            isin="DE0007164600",
            yahoo_ticker="SAP.DE",
            quantity=2.0,
            average_buy_price=50.0,
        ),
    ]

    def quotation_side_effect(ticker: str) -> dict[str, Any] | None:
        if ticker == "INVALID":
            return None
        return {"price": 100.0, "currency": "EUR", "timestamp": "2026-08-15"}

    mock_get_quotation.side_effect = quotation_side_effect

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    assert len(snapshot.assets_snapshot) == 1
    assert snapshot.assets_snapshot[0].yahoo_ticker == "SAP.DE"
    assert snapshot.total_value_eur == 200.00


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
def test_get_snapshot_exchange_rate_failure(
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Ensures that when an exchange rate retrieval
    returns None, the corresponding asset is skipped.
    """
    mock_repo = MagicMock()
    mock_repo.load_assets.return_value = [
        Asset(
            name="Foreign Stock",
            isin="JP1234567890",
            yahoo_ticker="TYO",
            quantity=100.0,
            average_buy_price=10.0,
        )
    ]
    mock_get_quotation.return_value = {
        "price": 1000.0,
        "currency": "JPY",
        "timestamp": "2026-08-15",
    }
    mock_get_exchange_rate.return_value = None

    snapshot: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)

    assert snapshot is not None
    assert len(snapshot.assets_snapshot) == 0
    assert snapshot.total_value_eur == 0.00


@patch("src.core.snapshot.logger")
def test_get_snapshot_file_read_error(mock_logger: MagicMock) -> None:
    """
    Tests handling of storage read errors.
    """
    mock_repo = MagicMock()
    mock_repo.load_assets.side_effect = StorageReadError("File not found")

    result: PortfolioSnapshot | None = get_snapshot(portfolio_repo=mock_repo)
    assert result is None
    mock_logger.error.assert_called()


@patch("src.core.snapshot.logger")
def test_display_snapshot(mock_logger: MagicMock) -> None:
    """
    Validates console output formatting for snapshot rendering.
    """
    snapshot_data: dict[str, Any] = {
        "timestamp": "2026-08-15T20:00:00",
        "total_value_eur": 1500.00,
        "assets_snapshot": [
            {
                "name": "Apple",
                "isin": "US0378331005",
                "yahoo_ticker": "AAPL",
                "native_price": 100.0,
                "native_currency": "USD",
                "value_eur": 1000.00,
            },
            {
                "name": "SAP",
                "isin": "DE0007164600",
                "yahoo_ticker": "SAP.DE",
                "native_price": 100.0,
                "native_currency": "EUR",
                "value_eur": 500.00,
            },
        ],
    }

    display_snapshot(snapshot_data)

    mock_logger.section.assert_called_once_with("Displaying Snapshot")
    mock_logger.info.assert_any_call("Timestamp: 2026-08-15T20:00:00")
    mock_logger.info.assert_any_call("Total Portfolio Value: 1500.00 EUR")
    mock_logger.print.assert_any_call("  - Apple: 1000.00 EUR")
    mock_logger.print.assert_any_call("  - SAP: 500.00 EUR")


def test_save_snapshot_with_history_repository(tmp_path: Any) -> None:
    """
    Validates saving a snapshot using a real JsonHistoryRepository
    in an isolated temporary directory.
    """
    history_file = tmp_path / "history.json"
    history_repo = JsonHistoryRepository(history_file)

    snapshot = PortfolioSnapshot(
        timestamp="2026-08-15T20:00:00",
        total_value_eur=1000.00,
        assets_snapshot=[],
    )

    save_snapshot(snapshot, history_repo=history_repo)

    assert history_file.exists()
    loaded_history = history_repo.load_history()
    assert len(loaded_history) == 1
    assert loaded_history[0].total_value_eur == 1000.00
