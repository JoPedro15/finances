"""
Unit tests for src/core/snapshot.py covering snapshot
calculation, currency exchange rate failures,
display logic, file handling errors, and snapshot persistence.
"""

import json
from pathlib import Path
from typing import Any, TextIO
from unittest.mock import MagicMock, mock_open, patch

from src.core.snapshot import display_snapshot, get_snapshot, save_snapshot


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
@patch("builtins.open")
def test_get_snapshot_multi_currency(
    mock_file: MagicMock,
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Validates that the global EUR total and native currency conversions
    are calculated accurately across multiple currencies.
    """
    portfolio_data: dict[str, Any] = {
        "assets": [
            {
                "name": "Apple",
                "isin": "US0378331005",
                "yahoo_ticker": "AAPL",
                "quantity": 10.0,
            },
            {
                "name": "SAP",
                "isin": "DE0007164600",
                "yahoo_ticker": "SAP.DE",
                "quantity": 5.0,
            },
        ]
    }
    mock_file.return_value = mock_open(read_data=json.dumps(portfolio_data))()

    def quotation_side_effect(ticker: str) -> dict[str, Any] | None:
        if ticker == "AAPL":
            return {"price": 100.0, "currency": "USD", "timestamp": "2026-08-15"}
        if ticker == "SAP.DE":
            return {"price": 50.0, "currency": "EUR", "timestamp": "2026-08-15"}
        return None

    mock_get_quotation.side_effect = quotation_side_effect
    mock_get_exchange_rate.return_value = 0.90

    snapshot: dict[str, Any] | None = get_snapshot()

    assert snapshot is not None
    assert snapshot["total_value_eur"] == 1150.00
    assert len(snapshot["assets_snapshot"]) == 2
    assert snapshot["assets_snapshot"][0]["value_eur"] == 900.00
    assert snapshot["assets_snapshot"][1]["value_eur"] == 250.00


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
@patch("builtins.open")
def test_get_snapshot_currency_caching(
    mock_file: MagicMock,
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Confirms that exchange_rates_cache reuses previously retrieved exchange rates
    for the same currency within a single snapshot cycle.
    """
    portfolio_data: dict[str, Any] = {
        "assets": [
            {
                "name": "Apple",
                "isin": "US0378331005",
                "yahoo_ticker": "AAPL",
                "quantity": 2.0,
            },
            {
                "name": "Microsoft",
                "isin": "US5949181045",
                "yahoo_ticker": "MSFT",
                "quantity": 3.0,
            },
        ]
    }
    mock_file.return_value = mock_open(read_data=json.dumps(portfolio_data))()
    mock_get_quotation.return_value = {
        "price": 100.0,
        "currency": "USD",
        "timestamp": "2026-08-15",
    }
    mock_get_exchange_rate.return_value = 0.85

    snapshot: dict[str, Any] | None = get_snapshot()

    assert snapshot is not None
    mock_get_exchange_rate.assert_called_once_with("USD", "EUR")


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
@patch("builtins.open")
def test_get_snapshot_missing_asset_quotation(
    mock_file: MagicMock,
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Ensures that if an asset quotation fails, calculation skips that asset
    and processes remaining assets without crashing.
    """
    portfolio_data: dict[str, Any] = {
        "assets": [
            {
                "name": "Invalid Asset",
                "isin": "XX0000000000",
                "yahoo_ticker": "INVALID",
                "quantity": 10.0,
            },
            {
                "name": "SAP",
                "isin": "DE0007164600",
                "yahoo_ticker": "SAP.DE",
                "quantity": 2.0,
            },
        ]
    }
    mock_file.return_value = mock_open(read_data=json.dumps(portfolio_data))()

    def quotation_side_effect(ticker: str) -> dict[str, Any] | None:
        if ticker == "INVALID":
            return None
        return {"price": 100.0, "currency": "EUR", "timestamp": "2026-08-15"}

    mock_get_quotation.side_effect = quotation_side_effect

    snapshot: dict[str, Any] | None = get_snapshot()

    assert snapshot is not None
    assert len(snapshot["assets_snapshot"]) == 1
    assert snapshot["assets_snapshot"][0]["yahoo_ticker"] == "SAP.DE"
    assert snapshot["total_value_eur"] == 200.00


@patch("src.core.snapshot.get_exchange_rate")
@patch("src.core.snapshot.get_quotation")
@patch("builtins.open")
def test_get_snapshot_exchange_rate_failure(
    mock_file: MagicMock,
    mock_get_quotation: MagicMock,
    mock_get_exchange_rate: MagicMock,
) -> None:
    """
    Ensures that when an exchange rate retrieval
    returns None, the corresponding asset is skipped.
    """
    portfolio_data: dict[str, Any] = {
        "assets": [
            {
                "name": "Foreign Stock",
                "isin": "JP1234567890",
                "yahoo_ticker": "TYO",
                "quantity": 100.0,
            }
        ]
    }
    mock_file.return_value = mock_open(read_data=json.dumps(portfolio_data))()
    mock_get_quotation.return_value = {
        "price": 1000.0,
        "currency": "JPY",
        "timestamp": "2026-08-15",
    }
    mock_get_exchange_rate.return_value = None

    snapshot: dict[str, Any] | None = get_snapshot()

    assert snapshot is not None
    assert len(snapshot["assets_snapshot"]) == 0
    assert snapshot["total_value_eur"] == 0.00


@patch("src.core.snapshot.logger")
@patch("builtins.open")
def test_get_snapshot_file_read_error(
    mock_file: MagicMock, mock_logger: MagicMock
) -> None:
    """
    Tests handling of missing portfolio file or invalid JSON content.
    """
    mock_file.side_effect = FileNotFoundError("File not found")

    result_not_found: dict[str, Any] | None = get_snapshot()
    assert result_not_found is None

    mock_file.side_effect = [mock_open(read_data="{invalid_json")()]
    result_invalid_json: dict[str, Any] | None = get_snapshot()
    assert result_invalid_json is None


@patch("src.core.snapshot.logger")
def test_display_snapshot(mock_logger: MagicMock) -> None:
    """
    Validates console output formatting for snapshot rendering.
    """
    snapshot_data: dict[str, Any] = {
        "timestamp": "2026-08-15T20:00:00",
        "total_value_eur": 1500.00,
        "assets_snapshot": [
            {"name": "Apple", "value_eur": 1000.00},
            {"name": "SAP", "value_eur": 500.00},
        ],
    }

    display_snapshot(snapshot_data)

    mock_logger.section.assert_called_once_with("Displaying Snapshot")
    mock_logger.info.assert_any_call("Timestamp: 2026-08-15T20:00:00")
    mock_logger.info.assert_any_call("Total Portfolio Value: 1500.00 EUR")
    mock_logger.print.assert_any_call("  - Apple: 1000.00 EUR")
    mock_logger.print.assert_any_call("  - SAP: 500.00 EUR")


def test_save_snapshot_new_and_existing_history(tmp_path: Path) -> None:
    """
    Validates saving snapshot to a new history file
    as well as appending to an existing history file.
    """
    history_file_path: Path = tmp_path / "history.json"
    first_snapshot: dict[str, Any] = {
        "timestamp": "2026-08-15T20:00:00",
        "total_value_eur": 1000.00,
        "assets_snapshot": [],
    }
    second_snapshot: dict[str, Any] = {
        "timestamp": "2026-08-15T21:00:00",
        "total_value_eur": 1200.00,
        "assets_snapshot": [],
    }

    with patch("src.core.snapshot.HISTORY_FILE", str(history_file_path)):
        save_snapshot(first_snapshot)
        assert history_file_path.exists()

        save_snapshot(second_snapshot)

        f: TextIO
        with open(history_file_path) as f:
            history_content: list[dict[str, Any]] = json.load(f)

        assert len(history_content) == 2
        assert history_content[0]["total_value_eur"] == 1000.00
        assert history_content[1]["total_value_eur"] == 1200.00
