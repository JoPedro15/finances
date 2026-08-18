"""Unit tests for src/core/analysis.py covering portfolio performance analysis,
exposure calculations, loss scenarios, missing/corrupted data files, and edge cases.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.analysis import (
    PortfolioExposure,
    analyze_overall_performance,
    calculate_portfolio_exposure,
)
from src.core.exceptions import StorageReadError
from src.core.models import (
    Asset,
    AssetSnapshot,
    ETFDetails,
    PortfolioSnapshot,
)


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


def test_calculate_portfolio_exposure_normalized_to_100_percent() -> None:
    """Verifies that calculate_portfolio_exposure sums up to 100% even
    when some ETFs lack full breakdown details.
    """
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = [
        Asset(
            name="Core MSCI World",
            isin="IE00B4L5Y983",
            yahoo_ticker="EUNL.DE",
            asset_type="etf",
            quantity=10.0,
            average_buy_price=90.0,
        ),
        Asset(
            name="Leveraged ETF without breakdown",
            isin="LU0411078552",
            yahoo_ticker="DBPG.DE",
            asset_type="etf",
            quantity=5.0,
            average_buy_price=170.0,
        ),
        Asset(
            name="Apple Stock",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            asset_type="stock",
            quantity=1.0,
            average_buy_price=180.0,
        ),
    ]

    mock_provider: MagicMock = MagicMock()
    mock_provider.get_details.side_effect = lambda asset: (
        ETFDetails(
            holdings=[],
            sector_breakdown=[
                SimpleNamespace(sector_name="Technology", weight_pct=30.0),
                SimpleNamespace(sector_name="Finance", weight_pct=20.0),
                SimpleNamespace(sector_name="Other", weight_pct=50.0),
            ],
            country_breakdown=[
                SimpleNamespace(country_name="United States", weight_pct=70.0),
                SimpleNamespace(country_name="Japan", weight_pct=30.0),
            ],
        )
        if asset.isin == "IE00B4L5Y983"
        else ETFDetails(
            holdings=[],
            sector_breakdown=[],
            country_breakdown=[],
        )
    )

    snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-18T20:00:00",
        total_value_eur=2000.0,
        assets_snapshot=[
            AssetSnapshot(
                name="Core MSCI World",
                isin="IE00B4L5Y983",
                yahoo_ticker="EUNL.DE",
                native_price=100.0,
                native_currency="EUR",
                value_eur=1000.0,
            ),
            AssetSnapshot(
                name="Leveraged ETF without breakdown",
                isin="LU0411078552",
                yahoo_ticker="DBPG.DE",
                native_price=170.0,
                native_currency="EUR",
                value_eur=850.0,
            ),
            AssetSnapshot(
                name="Apple Stock",
                isin="US0378331005",
                yahoo_ticker="AAPL",
                native_price=150.0,
                native_currency="USD",
                value_eur=150.0,
            ),
        ],
    )

    exposure: PortfolioExposure = calculate_portfolio_exposure(
        snapshot=snapshot,
        portfolio_repo=mock_p_repo,
        etf_provider=mock_provider,
    )

    assert exposure.total_etf_value_eur == 1850.0
    assert sum(exposure.sector_exposure.values()) == 100.0
    assert sum(exposure.country_exposure.values()) == 100.0
    assert exposure.sector_exposure["Technology"] == 30.0
    assert exposure.country_exposure["United States"] == 70.0


@patch("src.core.analysis.logger")
def test_calculate_portfolio_exposure_exception_handling(
    mock_logger: MagicMock,
) -> None:
    """Verifies that repository errors return an empty PortfolioExposure."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.side_effect = Exception("Database error")

    snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-18T20:00:00",
        total_value_eur=0.0,
        assets_snapshot=[],
    )

    exposure: PortfolioExposure = calculate_portfolio_exposure(
        snapshot=snapshot, portfolio_repo=mock_p_repo
    )

    assert exposure.total_etf_value_eur == 0.0
    assert exposure.sector_exposure == {}
    assert exposure.country_exposure == {}
    mock_logger.error.assert_called_once()
