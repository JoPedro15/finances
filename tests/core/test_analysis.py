"""
Unit tests for src/core/analysis.py covering portfolio performance analysis,
loss scenarios, missing/corrupted data files, and edge cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.core.analysis import analyze_overall_performance
from src.core.exceptions import StorageReadError
from src.core.models import Asset, AssetSnapshot, PortfolioSnapshot


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_gain_scenario(
    mock_logger: MagicMock,
) -> None:
    """Validates calculations and log outputs for individual
    assets and overall portfolio gain using repository mocks.
    """
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=10.0,
            average_buy_price=100.0,
        ),
        Asset(
            name="Microsoft",
            isin="US5949181045",
            yahoo_ticker="MSFT",
            quantity=5.0,
            average_buy_price=100.0,
        ),
    ]

    mock_h_repo: MagicMock = MagicMock()
    mock_h_repo.load_history.return_value = [
        PortfolioSnapshot(
            timestamp="2026-08-15T20:00:00",
            total_value_eur=1800.0,
            assets_snapshot=[
                AssetSnapshot(
                    name="Apple",
                    isin="US0378331005",
                    yahoo_ticker="AAPL",
                    native_price=150.0,
                    native_currency="USD",
                    value_eur=1500.0,
                ),
                AssetSnapshot(
                    name="Microsoft",
                    isin="US5949181045",
                    yahoo_ticker="MSFT",
                    native_price=60.0,
                    native_currency="USD",
                    value_eur=300.0,
                ),
            ],
        )
    ]

    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)

    mock_logger.success.assert_any_call("Absolute Gain: +500.00 EUR")
    mock_logger.warning.assert_any_call("Absolute Loss: -200.00 EUR")
    mock_logger.info.assert_any_call("Total Acquisition Cost: 1500.00 EUR")
    mock_logger.info.assert_any_call("Latest Market Value:   1800.00 EUR")
    mock_logger.success.assert_any_call("Absolute Gain: +300.00 EUR")
    mock_logger.success.assert_any_call("Return on Investment (ROI): +20.00%")


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_loss_scenario(
    mock_logger: MagicMock,
) -> None:
    """Validates log outputs when the overall portfolio
    produces an absolute loss and negative ROI.
    """
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = [
        Asset(
            name="Tesla",
            isin="US88160R1014",
            yahoo_ticker="TSLA",
            quantity=10.0,
            average_buy_price=200.0,
        )
    ]

    mock_h_repo: MagicMock = MagicMock()
    mock_h_repo.load_history.return_value = [
        PortfolioSnapshot(
            timestamp="2026-08-15T20:00:00",
            total_value_eur=1000.0,
            assets_snapshot=[
                AssetSnapshot(
                    name="Tesla",
                    isin="US88160R1014",
                    yahoo_ticker="TSLA",
                    native_price=100.0,
                    native_currency="USD",
                    value_eur=1000.0,
                )
            ],
        )
    ]

    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)

    mock_logger.warning.assert_any_call("Absolute Loss: -1000.00 EUR")
    mock_logger.warning.assert_any_call("Return on Investment (ROI): -50.00%")


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_zero_acquisition_cost(
    mock_logger: MagicMock,
) -> None:
    """Ensures zero acquisition cost handles division by zero safely."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = []

    mock_h_repo: MagicMock = MagicMock()
    mock_h_repo.load_history.return_value = [
        PortfolioSnapshot(
            timestamp="2026-08-15T20:00:00",
            total_value_eur=0.0,
            assets_snapshot=[],
        )
    ]

    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)

    mock_logger.success.assert_any_call("Return on Investment (ROI): +0.00%")


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_missing_or_corrupted_file(
    mock_logger: MagicMock,
) -> None:
    """Tests handling of empty history lists and repository read exceptions."""
    # 1. Empty history list
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = []

    mock_h_repo: MagicMock = MagicMock()
    mock_h_repo.load_history.return_value = []

    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)
    mock_logger.warning.assert_called_with(
        "History storage is empty. Cannot perform analysis."
    )

    # 2. StorageReadError / StorageError
    mock_p_repo.load_assets.side_effect = StorageReadError(
        "Failed to read portfolio file"
    )
    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)
    mock_logger.error.assert_called()


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_mismatched_assets(
    mock_logger: MagicMock,
) -> None:
    """Confirms that assets omitted from historical snapshots are skipped cleanly."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=10.0,
            average_buy_price=100.0,
        ),
        Asset(
            name="Omitted Asset",
            isin="XX0000000000",
            yahoo_ticker="OMIT",
            quantity=5.0,
            average_buy_price=200.0,
        ),
    ]

    mock_h_repo: MagicMock = MagicMock()
    mock_h_repo.load_history.return_value = [
        PortfolioSnapshot(
            timestamp="2026-08-15T20:00:00",
            total_value_eur=1500.0,
            assets_snapshot=[
                AssetSnapshot(
                    name="Apple",
                    isin="US0378331005",
                    yahoo_ticker="AAPL",
                    native_price=150.0,
                    native_currency="USD",
                    value_eur=1500.0,
                )
            ],
        )
    ]

    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)

    mock_logger.warning.assert_any_call(
        "No recent market data found for Omitted Asset. Skipping."
    )
    mock_logger.info.assert_any_call("Total Acquisition Cost: 1000.00 EUR")
    mock_logger.info.assert_any_call("Latest Market Value:   1500.00 EUR")
    mock_logger.success.assert_any_call("Return on Investment (ROI): +50.00%")
