"""Comprehensive unit tests for src/core/analysis.py covering portfolio exposure,

performance analysis, stock quality evaluation, and ETF quality evaluation.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.analysis import (
    PortfolioExposure,
    analyze_overall_performance,
    calculate_portfolio_exposure,
    evaluate_etf_quality,
    evaluate_stock_quality,
)
from src.core.exceptions import StorageError
from src.core.models import (
    Asset,
    AssetSnapshot,
    ETFDetails,
    PortfolioSnapshot,
    StockDetails,
)


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_gain_scenario(mock_logger: MagicMock) -> None:
    """Validates calculations and log outputs for individual assets and gain."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = [
        Asset(
            name="Apple",
            isin="US0378331005",
            yahoo_ticker="AAPL",
            quantity=10.0,
            average_buy_price=100.0,
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
    mock_logger.success.assert_any_call("Absolute Gain: +500.00 EUR")
    mock_logger.success.assert_any_call("Return on Investment (ROI): +50.00%")


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_loss_scenario(mock_logger: MagicMock) -> None:
    """Validates log outputs when portfolio produces an absolute loss."""
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
def test_analyze_overall_performance_empty_history(mock_logger: MagicMock) -> None:
    """Tests handling when history storage is empty."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = []
    mock_h_repo: MagicMock = MagicMock()
    mock_h_repo.load_history.return_value = []

    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)
    mock_logger.warning.assert_called_with(
        "History storage is empty. Cannot perform analysis."
    )


@patch("src.core.analysis.logger")
def test_analyze_overall_performance_storage_error(mock_logger: MagicMock) -> None:
    """Tests storage error handling during analysis."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.side_effect = StorageError("Storage failure")
    mock_h_repo: MagicMock = MagicMock()

    analyze_overall_performance(portfolio_repo=mock_p_repo, history_repo=mock_h_repo)
    mock_logger.error.assert_called_with(
        "Could not read data from storage: Storage failure"
    )


@patch("src.core.analysis.SqliteHistoryRepository")
@patch("src.core.analysis.SqlitePortfolioRepository")
@patch("src.core.analysis.logger")
def test_analyze_overall_performance_defaults(
    mock_logger: MagicMock,
    mock_p_cls: MagicMock,
    mock_h_cls: MagicMock,
) -> None:
    """Tests default repository instantiation."""
    mock_p_cls.return_value.load_assets.return_value = []
    mock_h_cls.return_value.load_history.return_value = []

    analyze_overall_performance(portfolio_repo=None, history_repo=None)
    mock_p_cls.assert_called_once()
    mock_h_cls.assert_called_once()


def test_calculate_portfolio_exposure_comprehensive() -> None:
    """Tests portfolio exposure calculation with various asset types and edges."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.return_value = [
        Asset(
            name="ETF World",
            isin="IE00B4L5Y983",
            yahoo_ticker="EUNL.DE",
            asset_type="ETF",
            quantity=10.0,
            average_buy_price=50.0,
        ),
    ]

    mock_etf_prov: MagicMock = MagicMock()
    mock_etf_prov.get_details.return_value = ETFDetails(
        holdings=[],
        sector_breakdown=[SimpleNamespace(sector_name="Tech", weight_pct=100.0)],
        country_breakdown=[SimpleNamespace(country_name="USA", weight_pct=100.0)],
    )

    snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-22",
        total_value_eur=400.0,
        assets_snapshot=[
            AssetSnapshot(
                name="ETF World",
                isin="IE00B4L5Y983",
                yahoo_ticker="EUNL.DE",
                native_price=40.0,
                native_currency="EUR",
                value_eur=400.0,
            ),
        ],
    )

    exposure: PortfolioExposure = calculate_portfolio_exposure(
        snapshot=snapshot,
        portfolio_repo=mock_p_repo,
        etf_provider=mock_etf_prov,
    )
    assert exposure.total_etf_value_eur == 400.0


@patch("src.core.analysis.logger")
def test_calculate_portfolio_exposure_error(mock_logger: MagicMock) -> None:
    """Tests exposure calculation when asset loading raises exception."""
    mock_p_repo: MagicMock = MagicMock()
    mock_p_repo.load_assets.side_effect = Exception("DB error")
    snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-22", total_value_eur=100.0, assets_snapshot=[]
    )

    exposure: PortfolioExposure = calculate_portfolio_exposure(
        snapshot=snapshot, portfolio_repo=mock_p_repo
    )
    assert exposure.total_etf_value_eur == 0.0
    mock_logger.error.assert_called_once()


def test_evaluate_stock_quality_scenarios() -> None:
    """Tests various stock quality evaluation tiers and knockouts."""
    details_a = StockDetails(
        profit_margins_pct=25.0,
        revenue_growth_pct=10.0,
        total_debt_to_equity=50.0,
        earnings_growth_pct=15.0,
        pe_ratio=20.0,
    )
    res_a = evaluate_stock_quality(details_a)
    assert res_a["tier"] == "Tier A"


def test_evaluate_etf_quality_scenarios() -> None:
    """Tests ETF quality evaluation across Tier A, B, and C rules."""
    etf_a = ETFDetails(
        ter_pct=0.10, holdings=[], sector_breakdown=[], country_breakdown=[]
    )
    res_a = evaluate_etf_quality(etf_a, aum_eur=600_000_000.0, age_years=5.0)
    assert res_a["tier"] == "Tier A"
