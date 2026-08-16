# tests/test_dip_detector.py
# Unit tests for utils/dip_detector.py

import json
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, mock_open, patch
import pandas as pd
import pytest

from utils.dip_detector import detect_dip, load_watchlist, scan_watchlist


@pytest.fixture
def mock_stock_history_valid() -> pd.DataFrame:
    """Creates a mock pandas DataFrame simulating stock history with a ~7% dip."""
    dates: pd.DatetimeIndex = pd.date_range(start="2026-08-01", periods=5, freq="D")
    data: Dict[str, List[float]] = {
        "High": [100.0, 100.0, 95.0, 94.0, 93.0],
        "Close": [98.0, 99.0, 94.0, 93.0, 93.0],
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def mock_stock_history_small_dip() -> pd.DataFrame:
    """Creates a mock pandas DataFrame simulating a ~2% dip."""
    dates: pd.DatetimeIndex = pd.date_range(start="2026-08-01", periods=5, freq="D")
    data: Dict[str, List[float]] = {
        "High": [100.0, 100.0, 99.0, 98.0, 98.0],
        "Close": [99.0, 99.0, 98.0, 98.0, 98.0],
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def mock_stock_history_large_dip() -> pd.DataFrame:
    """Creates a mock pandas DataFrame simulating a ~15% dip."""
    dates: pd.DatetimeIndex = pd.date_range(start="2026-08-01", periods=5, freq="D")
    data: Dict[str, List[float]] = {
        "High": [100.0, 100.0, 90.0, 88.0, 85.0],
        "Close": [95.0, 90.0, 88.0, 86.0, 85.0],
    }
    return pd.DataFrame(data, index=dates)


# ==============================================================================
# 🛠️ load_watchlist Tests
# ==============================================================================


@patch("utils.dip_detector.Path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data=json.dumps(
        [
            {"name": "Apple", "isin": "US0378331005", "ticker": "AAPL"},
            {"name": "NVIDIA", "isin": "US67066G1040", "ticker": "NVDA"},
        ]
    ),
)
def test_load_watchlist_success(mock_file: MagicMock, mock_exists: MagicMock) -> None:
    """Tests loading valid watchlist JSON data."""
    result: List[Dict[str, str]] = load_watchlist("data/watchlist.json")

    assert len(result) == 2
    assert result[0]["ticker"] == "AAPL"
    assert result[0]["isin"] == "US0378331005"


@patch("utils.dip_detector.Path.exists", return_value=False)
def test_load_watchlist_file_not_found(mock_exists: MagicMock) -> None:
    """Tests handling when watchlist file does not exist."""
    result: List[Dict[str, str]] = load_watchlist("invalid/path.json")
    assert result == []


@patch("utils.dip_detector.Path.exists", return_value=True)
@patch("builtins.open", side_effect=Exception("Read error"))
def test_load_watchlist_exception(
    mock_open_func: MagicMock, mock_exists: MagicMock
) -> None:
    """Tests handling exceptions thrown during file reading."""
    result: List[Dict[str, str]] = load_watchlist("data/watchlist.json")
    assert result == []


# ==============================================================================
# 🛠️ detect_dip Tests
# ==============================================================================


@patch("utils.dip_detector.yf.Ticker")
def test_detect_dip_success(
    mock_ticker: MagicMock, mock_stock_history_valid: pd.DataFrame
) -> None:
    """Tests successful detection of a dip within the 5% - 10% target range."""
    mock_instance: MagicMock = MagicMock()
    mock_instance.history.return_value = mock_stock_history_valid
    mock_ticker.return_value = mock_instance

    result: Optional[Dict[str, Any]] = detect_dip("AAPL")

    assert result is not None
    assert result["ticker"] == "AAPL"
    assert result["current_price"] == 93.0
    assert result["peak_price"] == 100.0
    assert result["drop_pct"] == 7.0


@patch("utils.dip_detector.yf.Ticker")
def test_detect_dip_below_threshold(
    mock_ticker: MagicMock, mock_stock_history_small_dip: pd.DataFrame
) -> None:
    """Tests that a dip smaller than min_drop_pct returns None."""
    mock_instance: MagicMock = MagicMock()
    mock_instance.history.return_value = mock_stock_history_small_dip
    mock_ticker.return_value = mock_instance

    # Explicitly test against standard thresholds (5.0% to 10.0%)
    result: Optional[Dict[str, Any]] = detect_dip(
        "AAPL", min_drop_pct=5.0, max_drop_pct=10.0
    )

    assert result is None


@patch("utils.dip_detector.yf.Ticker")
def test_detect_dip_above_threshold(
    mock_ticker: MagicMock, mock_stock_history_large_dip: pd.DataFrame
) -> None:
    """Tests that a dip larger than max_drop_pct returns None."""
    mock_instance: MagicMock = MagicMock()
    mock_instance.history.return_value = mock_stock_history_large_dip
    mock_ticker.return_value = mock_instance

    # Explicitly test against standard thresholds (5.0% to 10.0%)
    result: Optional[Dict[str, Any]] = detect_dip(
        "AAPL", min_drop_pct=5.0, max_drop_pct=10.0
    )

    assert result is None


@patch("utils.dip_detector.yf.Ticker")
def test_detect_dip_empty_history(mock_ticker: MagicMock) -> None:
    """Tests handling of empty historical data."""
    mock_instance: MagicMock = MagicMock()
    mock_instance.history.return_value = pd.DataFrame()
    mock_ticker.return_value = mock_instance

    result: Optional[Dict[str, Any]] = detect_dip("UNKNOWN")

    assert result is None


@patch("utils.dip_detector.yf.Ticker")
def test_detect_dip_insufficient_history(mock_ticker: MagicMock) -> None:
    """Tests handling when history has fewer than 2 data points."""
    single_row_df: pd.DataFrame = pd.DataFrame(
        {"High": [100.0], "Close": [95.0]},
        index=pd.date_range(start="2026-08-01", periods=1),
    )
    mock_instance: MagicMock = MagicMock()
    mock_instance.history.return_value = single_row_df
    mock_ticker.return_value = mock_instance

    result: Optional[Dict[str, Any]] = detect_dip("AAPL")

    assert result is None


@patch("utils.dip_detector.yf.Ticker")
def test_detect_dip_invalid_peak_price(mock_ticker: MagicMock) -> None:
    """Tests handling when peak price is zero or negative."""
    dates: pd.DatetimeIndex = pd.date_range(start="2026-08-01", periods=2)
    invalid_df: pd.DataFrame = pd.DataFrame(
        {"High": [0.0, 0.0], "Close": [0.0, 0.0]}, index=dates
    )
    mock_instance: MagicMock = MagicMock()
    mock_instance.history.return_value = invalid_df
    mock_ticker.return_value = mock_instance

    result: Optional[Dict[str, Any]] = detect_dip("ZERO")

    assert result is None


@patch("utils.dip_detector.yf.Ticker")
def test_detect_dip_exception_handling(mock_ticker: MagicMock) -> None:
    """Tests that exceptions during yfinance API calls are handled gracefully."""
    mock_ticker.side_effect = Exception("API connection error")

    result: Optional[Dict[str, Any]] = detect_dip("FAIL")

    assert result is None


# ==============================================================================
# 🛠️ scan_watchlist Tests
# ==============================================================================


@patch("utils.dip_detector.detect_dip")
def test_scan_watchlist(mock_detect_dip: MagicMock) -> None:
    """Tests scanning watchlist items and attaching metadata to dip results."""
    mock_detect_dip.side_effect = [
        {
            "ticker": "AAPL",
            "current_price": 93.0,
            "peak_price": 100.0,
            "peak_date": "2026-08-01",
            "drop_pct": 7.0,
        },
        None,
    ]

    items: List[Dict[str, str]] = [
        {"name": "Apple", "isin": "US0378331005", "ticker": "AAPL"},
        {"name": "Microsoft", "isin": "US5949181045", "ticker": "MSFT"},
        {"name": "Empty Item"},
    ]

    results: List[Dict[str, Any]] = scan_watchlist(items)

    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
    assert results[0]["name"] == "Apple"
    assert results[0]["isin"] == "US0378331005"
    assert mock_detect_dip.call_count == 2
