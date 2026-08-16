"""
Unit tests for src/core/get_quotation.py covering success paths, fallback mechanisms,
and error handling.
"""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd

from src.core.get_quotation import get_exchange_rate, get_quotation, get_usd_to_eur_rate


@patch("src.core.get_quotation.yf.Ticker")
def test_get_quotation_success_primary(mock_ticker_class: MagicMock) -> None:
    """
    Tests successful retrieval of stock quotation when
    regularMarketPrice is present in info.
    """
    mock_ticker_instance: MagicMock = MagicMock()
    mock_ticker_instance.info = {
        "regularMarketPrice": 150.50,
        "currency": "USD",
    }
    mock_ticker_class.return_value = mock_ticker_instance

    result: dict[str, Any] | None = get_quotation("AAPL")

    assert result is not None
    assert result["price"] == 150.50
    assert result["currency"] == "USD"
    assert isinstance(result["timestamp"], datetime)
    mock_ticker_class.assert_called_once_with("AAPL")


@patch("src.core.get_quotation.yf.Ticker")
def test_get_quotation_fallback_to_history(mock_ticker_class: MagicMock) -> None:
    """
    Tests fallback mechanism to stock.history when
    regularMarketPrice is missing in info.
    """
    mock_ticker_instance: MagicMock = MagicMock()
    mock_ticker_instance.info = {"currency": "EUR"}
    mock_df: pd.DataFrame = pd.DataFrame({"Close": [120.25]})
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_class.return_value = mock_ticker_instance

    result: dict[str, Any] | None = get_quotation("SAP")

    assert result is not None
    assert result["price"] == 120.25
    assert result["currency"] == "EUR"
    mock_ticker_instance.history.assert_called_once_with(period="1d")


@patch("src.core.get_quotation.yf.Ticker")
def test_get_quotation_no_price_found(mock_ticker_class: MagicMock) -> None:
    """
    Tests that get_quotation logs error and returns None when no price is available.
    """
    mock_ticker_instance: MagicMock = MagicMock()
    mock_ticker_instance.info = {}
    mock_df: pd.DataFrame = pd.DataFrame()
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_class.return_value = mock_ticker_instance

    result: dict[str, Any] | None = get_quotation("UNKNOWN")

    assert result is None


@patch("src.core.get_quotation.yf.Ticker")
def test_get_quotation_exception_handling(mock_ticker_class: MagicMock) -> None:
    """
    Tests handling of API/network exceptions during stock retrieval.
    """
    mock_ticker_class.side_effect = Exception("API connection failure")

    result: dict[str, Any] | None = get_quotation("INVALID")

    assert result is None


@patch("src.core.get_quotation.yf.Ticker")
def test_get_exchange_rate_same_currency(mock_ticker_class: MagicMock) -> None:
    """
    Validates that requesting rate for identical currencies
    returns 1.0 without API call.
    """
    rate: float | None = get_exchange_rate("EUR", "EUR")

    assert rate == 1.0
    mock_ticker_class.assert_not_called()


@patch("src.core.get_quotation.yf.Ticker")
def test_get_exchange_rate_success(mock_ticker_class: MagicMock) -> None:
    """
    Tests successful retrieval of exchange rate between two distinct currencies.
    """
    mock_ticker_instance: MagicMock = MagicMock()
    mock_df: pd.DataFrame = pd.DataFrame({"Close": [0.92]})
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_class.return_value = mock_ticker_instance

    rate: float | None = get_exchange_rate("USD", "EUR")

    assert rate == 0.92
    mock_ticker_class.assert_called_once_with("USDEUR=X")


@patch("src.core.get_quotation.yf.Ticker")
def test_get_exchange_rate_empty_history(mock_ticker_class: MagicMock) -> None:
    """
    Tests that get_exchange_rate returns None when market data is empty.
    """
    mock_ticker_instance: MagicMock = MagicMock()
    mock_df: pd.DataFrame = pd.DataFrame()
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_class.return_value = mock_ticker_instance

    rate: float | None = get_exchange_rate("USD", "XYZ")

    assert rate is None


@patch("src.core.get_quotation.yf.Ticker")
def test_get_exchange_rate_exception_handling(mock_ticker_class: MagicMock) -> None:
    """
    Tests exception handling in get_exchange_rate.
    """
    mock_ticker_class.side_effect = Exception("Network timeout")

    rate: float | None = get_exchange_rate("USD", "EUR")

    assert rate is None


@patch("src.core.get_quotation.yf.Ticker")
def test_get_usd_to_eur_rate_success(mock_ticker_class: MagicMock) -> None:
    """
    Tests successful execution of legacy function get_usd_to_eur_rate.
    """
    mock_ticker_instance: MagicMock = MagicMock()
    mock_df: pd.DataFrame = pd.DataFrame({"Close": [0.92]})
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_class.return_value = mock_ticker_instance

    rate: float | None = get_usd_to_eur_rate()

    assert rate == 0.92
    mock_ticker_class.assert_called_once_with("USDEUR=X")


@patch("src.core.get_quotation.yf.Ticker")
def test_get_usd_to_eur_rate_empty_history(mock_ticker_class: MagicMock) -> None:
    """
    Tests get_usd_to_eur_rate returning None on empty response.
    """
    mock_ticker_instance: MagicMock = MagicMock()
    mock_df: pd.DataFrame = pd.DataFrame()
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_class.return_value = mock_ticker_instance

    rate: float | None = get_usd_to_eur_rate()

    assert rate is None


@patch("src.core.get_quotation.yf.Ticker")
def test_get_usd_to_eur_rate_exception_handling(mock_ticker_class: MagicMock) -> None:
    """
    Tests exception handling in get_usd_to_eur_rate.
    """
    mock_ticker_class.side_effect = Exception("API failure")

    rate: float | None = get_usd_to_eur_rate()

    assert rate is None
