"""
Unit tests for src/core/analysis.py covering portfolio performance analysis,
loss scenarios, missing/corrupted data files, and edge cases.
"""

import json
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

from src.core.analysis import analyze_overall_performance


@patch("src.core.analysis.logger")
@patch("builtins.open")
def test_analyze_overall_performance_gain_scenario(
    mock_file: MagicMock, mock_logger: MagicMock
) -> None:
    """
    Validates calculations and log outputs for individual
    assets and overall portfolio gain.
    """
    portfolio_data: dict[str, Any] = {
        "assets": [
            {
                "name": "Apple",
                "isin": "US0378331005",
                "quantity": 10.0,
                "averageBuyPrice": 100.0,
            },
            {
                "name": "Microsoft",
                "isin": "US5949181045",
                "quantity": 5.0,
                "averageBuyPrice": 100.0,
            },
        ]
    }
    history_data: list[dict[str, Any]] = [
        {
            "assets_snapshot": [
                {"isin": "US0378331005", "value_eur": 1500.0},
                {"isin": "US5949181045", "value_eur": 300.0},
            ]
        }
    ]

    mock_file.side_effect = [
        mock_open(read_data=json.dumps(portfolio_data))(),
        mock_open(read_data=json.dumps(history_data))(),
    ]

    analyze_overall_performance()

    mock_logger.success.assert_any_call("Absolute Gain: +500.00 EUR")
    mock_logger.warning.assert_any_call("Absolute Loss: -200.00 EUR")
    mock_logger.info.assert_any_call("Total Acquisition Cost: 1500.00 EUR")
    mock_logger.info.assert_any_call("Latest Market Value:   1800.00 EUR")
    mock_logger.success.assert_any_call("Absolute Gain: +300.00 EUR")
    mock_logger.success.assert_any_call("Return on Investment (ROI): +20.00%")


@patch("src.core.analysis.logger")
@patch("builtins.open")
def test_analyze_overall_performance_loss_scenario(
    mock_file: MagicMock, mock_logger: MagicMock
) -> None:
    """
    Validates log outputs when the overall portfolio
    produces an absolute loss and negative ROI.
    """
    portfolio_data: dict[str, Any] = {
        "assets": [
            {
                "name": "Tesla",
                "isin": "US88160R1014",
                "quantity": 10.0,
                "averageBuyPrice": 200.0,
            }
        ]
    }
    history_data: list[dict[str, Any]] = [
        {
            "assets_snapshot": [
                {"isin": "US88160R1014", "value_eur": 1000.0},
            ]
        }
    ]

    mock_file.side_effect = [
        mock_open(read_data=json.dumps(portfolio_data))(),
        mock_open(read_data=json.dumps(history_data))(),
    ]

    analyze_overall_performance()

    mock_logger.warning.assert_any_call("Absolute Loss: -1000.00 EUR")
    mock_logger.warning.assert_any_call("Return on Investment (ROI): -50.00%")


@patch("src.core.analysis.logger")
@patch("builtins.open")
def test_analyze_overall_performance_zero_acquisition_cost(
    mock_file: MagicMock, mock_logger: MagicMock
) -> None:
    """
    Ensures zero acquisition cost handles division by zero safely and reports 0.00% ROI.
    """
    portfolio_data: dict[str, Any] = {"assets": []}
    history_data: list[dict[str, Any]] = [{"assets_snapshot": []}]

    mock_file.side_effect = [
        mock_open(read_data=json.dumps(portfolio_data))(),
        mock_open(read_data=json.dumps(history_data))(),
    ]

    analyze_overall_performance()

    mock_logger.success.assert_any_call("Return on Investment (ROI): +0.00%")


@patch("src.core.analysis.logger")
@patch("builtins.open")
def test_analyze_overall_performance_missing_or_corrupted_file(
    mock_file: MagicMock, mock_logger: MagicMock
) -> None:
    """
    Tests handling of missing history files, empty history
    lists, and JSON decode errors.
    """
    # 1. Empty history list
    portfolio_data: dict[str, Any] = {"assets": []}
    history_data: list[dict[str, Any]] = []

    mock_file.side_effect = [
        mock_open(read_data=json.dumps(portfolio_data))(),
        mock_open(read_data=json.dumps(history_data))(),
    ]

    analyze_overall_performance()
    mock_logger.warning.assert_called_with(
        "History file is empty. Cannot perform analysis."
    )

    # 2. FileNotFoundError
    mock_file.side_effect = FileNotFoundError("File not found")
    analyze_overall_performance()
    mock_logger.error.assert_called()

    # 3. JSONDecodeError
    mock_file.side_effect = [
        mock_open(read_data="{invalid_json")(),
        mock_open(read_data="[]")(),
    ]
    analyze_overall_performance()
    mock_logger.error.assert_called()


@patch("src.core.analysis.logger")
@patch("builtins.open")
def test_analyze_overall_performance_mismatched_assets(
    mock_file: MagicMock, mock_logger: MagicMock
) -> None:
    """
    Confirms that assets omitted from historical snapshots are skipped cleanly.
    """
    portfolio_data: dict[str, Any] = {
        "assets": [
            {
                "name": "Apple",
                "isin": "US0378331005",
                "quantity": 10.0,
                "averageBuyPrice": 100.0,
            },
            {
                "name": "Omitted Asset",
                "isin": "XX0000000000",
                "quantity": 5.0,
                "averageBuyPrice": 200.0,
            },
        ]
    }
    history_data: list[dict[str, Any]] = [
        {
            "assets_snapshot": [
                {"isin": "US0378331005", "value_eur": 1500.0},
            ]
        }
    ]

    mock_file.side_effect = [
        mock_open(read_data=json.dumps(portfolio_data))(),
        mock_open(read_data=json.dumps(history_data))(),
    ]

    analyze_overall_performance()

    mock_logger.warning.assert_any_call(
        "No recent market data found for Omitted Asset. Skipping."
    )
    mock_logger.info.assert_any_call("Total Acquisition Cost: 1000.00 EUR")
    mock_logger.info.assert_any_call("Latest Market Value:   1500.00 EUR")
    mock_logger.success.assert_any_call("Return on Investment (ROI): +50.00%")
