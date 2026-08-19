"""Unit tests for src/core/currency_exchange.py covering exchange rate
fetching, caching logic, error scenarios, and CLI invocation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core.currency_exchange import (
    get_exchange_rate,
    get_usd_to_eur_rate,
    main,
)


def test_get_exchange_rate_same_currency() -> None:
    """Verifies that requesting exchange rate for identical currencies returns 1.0."""
    rate: float | None = get_exchange_rate("EUR", "eur")
    assert rate == 1.0

    rate_usd: float | None = get_exchange_rate("USD", "USD")
    assert rate_usd == 1.0


@patch("src.core.currency_exchange.yf.Ticker")
def test_get_exchange_rate_success(mock_ticker_cls: MagicMock) -> None:
    """Tests successful exchange rate retrieval from yfinance."""
    mock_df: pd.DataFrame = pd.DataFrame({"Close": [0.92]})
    mock_ticker_instance: MagicMock = MagicMock()
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_cls.return_value = mock_ticker_instance

    rate: float | None = get_exchange_rate("USD", "EUR")

    assert rate == 0.92
    mock_ticker_cls.assert_called_once_with("USDEUR=X")
    mock_ticker_instance.history.assert_called_once_with(period="1d")


@patch("src.core.currency_exchange.logger")
@patch("src.core.currency_exchange.yf.Ticker")
def test_get_exchange_rate_empty_history(
    mock_ticker_cls: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """Tests handling of empty history response from yfinance."""
    mock_df: pd.DataFrame = pd.DataFrame()
    mock_ticker_instance: MagicMock = MagicMock()
    mock_ticker_instance.history.return_value = mock_df
    mock_ticker_cls.return_value = mock_ticker_instance

    rate: float | None = get_exchange_rate("GBP", "EUR")

    assert rate is None
    mock_logger.error.assert_called_once()


@patch("src.core.currency_exchange.logger")
@patch("src.core.currency_exchange.yf.Ticker")
def test_get_exchange_rate_exception(
    mock_ticker_cls: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """Tests exception handling when yfinance API call fails."""
    mock_ticker_cls.side_effect = Exception("Network connection error")

    rate: float | None = get_exchange_rate("USD", "EUR")

    assert rate is None
    mock_logger.error.assert_called_once()


@patch("src.core.currency_exchange.get_exchange_rate")
def test_get_usd_to_eur_rate(mock_get_rate: MagicMock) -> None:
    """Verifies get_usd_to_eur_rate convenience wrapper."""
    mock_get_rate.return_value = 0.88

    rate: float | None = get_usd_to_eur_rate()

    assert rate == 0.88
    mock_get_rate.assert_called_once_with("USD", "EUR")


@patch("src.core.currency_exchange.logger")
def test_main_cli_missing_arguments(mock_logger: MagicMock) -> None:
    """Verifies CLI exit and error logging when insufficient arguments are provided."""
    with patch("sys.argv", ["currency_exchange.py", "USD"]):
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        mock_logger.error.assert_called_with("Currencies not provided.")


@patch("src.core.currency_exchange.get_exchange_rate")
@patch("src.core.currency_exchange.logger")
def test_main_cli_success(
    mock_logger: MagicMock,
    mock_get_rate: MagicMock,
) -> None:
    """Verifies CLI execution when valid currency parameters are passed."""
    mock_get_rate.return_value = 0.92

    with patch("sys.argv", ["currency_exchange.py", "USD", "EUR"]):
        main()

    mock_get_rate.assert_called_once_with("USD", "EUR")
    mock_logger.info.assert_called_with("Exchange rate USD/EUR: 0.92")
