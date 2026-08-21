"""Unit tests for strategies, configuration, and portfolio
opportunity_evaluation engine.
"""

from unittest.mock import MagicMock

import pytest

from src.config import EtfStrategyConfig, StockStrategyConfig
from src.core.models import PortfolioSnapshot
from src.core.opportunity_evaluation.base import AssetScore
from src.core.opportunity_evaluation.engine import PortfolioOpportunityEngine
from src.core.opportunity_evaluation.etf_strategy import EtfScoringStrategy
from src.core.opportunity_evaluation.stock_strategy import StockScoringStrategy


def test_stock_config_invalid_weights() -> None:
    """Verifies StockStrategyConfig raises ValueError when weights != 1.0."""
    with pytest.raises(ValueError, match="Stock strategy weights must sum to 1.0"):
        StockStrategyConfig(
            weight_dip=0.40,
            weight_forward_pe=0.40,
            weight_52w_range=0.30,
            weight_allocation=0.30,
        )


def test_etf_config_invalid_weights() -> None:
    """Verifies EtfStrategyConfig raises ValueError when weights != 1.0."""
    with pytest.raises(ValueError, match="ETF strategy weights must sum to 1.0"):
        EtfStrategyConfig(
            weight_dip=0.50,
            weight_ter=0.50,
            weight_allocation=0.50,
        )


def test_stock_dip_score_edge_cases() -> None:
    """Tests stock dip calculation across edge cases."""
    strategy = StockScoringStrategy()

    assert strategy.calculate_dip_score(current_price=0.0, peak_price=100.0) == 0.0
    assert strategy.calculate_dip_score(current_price=100.0, peak_price=0.0) == 0.0
    assert strategy.calculate_dip_score(current_price=105.0, peak_price=100.0) == 0.0
    assert strategy.calculate_dip_score(
        current_price=97.0, peak_price=100.0
    ) == pytest.approx(0.12, abs=1e-4)
    assert strategy.calculate_dip_score(current_price=90.0, peak_price=100.0) == 1.0

    penalty_score = strategy.calculate_dip_score(current_price=50.0, peak_price=100.0)
    assert penalty_score < 1.0
    assert penalty_score >= 0.1


def test_stock_pe_score_growth_stagnation_and_missing() -> None:
    """Tests P/E score calculation for missing metadata and growth."""
    strategy = StockScoringStrategy()

    assert strategy.calculate_pe_score(trailing_pe=None, forward_pe=20.0) == 0.5
    assert strategy.calculate_pe_score(trailing_pe=20.0, forward_pe=0.0) == 0.5
    assert strategy.calculate_pe_score(trailing_pe=25.0, forward_pe=25.0) == 0.6

    growth_score = strategy.calculate_pe_score(trailing_pe=25.0, forward_pe=20.0)
    assert growth_score > 0.6

    contraction_score = strategy.calculate_pe_score(trailing_pe=20.0, forward_pe=25.0)
    assert contraction_score < 0.6


def test_stock_52w_range_score() -> None:
    """Tests 52-week position evaluation."""
    strategy = StockScoringStrategy()

    assert (
        strategy.calculate_52w_range_score(
            current_price=10.0, low_52w=None, high_52w=20.0
        )
        == 0.5
    )
    assert (
        strategy.calculate_52w_range_score(
            current_price=10.0, low_52w=20.0, high_52w=10.0
        )
        == 0.5
    )
    assert (
        strategy.calculate_52w_range_score(
            current_price=110.0, low_52w=100.0, high_52w=200.0
        )
        == 1.0
    )


def test_etf_ter_score_boundaries() -> None:
    """Tests ETF TER cost efficiency logic."""
    strategy = EtfScoringStrategy()

    assert strategy.calculate_ter_score(ter=None) == 0.5
    assert strategy.calculate_ter_score(ter=-0.05) == 0.5
    assert strategy.calculate_ter_score(ter=0.07) == 1.0
    assert strategy.calculate_ter_score(ter=0.55) == 0.0

    mid_score = strategy.calculate_ter_score(ter=0.30)
    assert 0.0 < mid_score < 1.0


def test_etf_allocation_score() -> None:
    """Tests underweight allocation gap priority calculation."""
    strategy = EtfScoringStrategy()

    assert (
        strategy.calculate_allocation_score(
            target_allocation_pct=20.0, current_allocation_pct=25.0
        )
        == 0.0
    )
    assert (
        strategy.calculate_allocation_score(
            target_allocation_pct=30.0, current_allocation_pct=20.0
        )
        == 1.0
    )


def test_engine_ranks_assets_correctly() -> None:
    """Verifies opportunity_evaluation engine scores and ranks assets correctly."""
    engine = PortfolioOpportunityEngine()

    assets_data = [
        {
            "symbol": "LOW_PRIORITY",
            "asset_type": "ETF",
            "current_price": 100.0,
            "peak_price": 100.0,
            "target_allocation_pct": 10.0,
            "current_allocation_pct": 10.0,
            "ter": 0.60,
        },
        {
            "symbol": "HIGH_PRIORITY",
            "asset_type": "ETF",
            "current_price": 93.0,
            "peak_price": 100.0,
            "target_allocation_pct": 20.0,
            "current_allocation_pct": 10.0,
            "ter": 0.07,
        },
    ]

    scores: list[AssetScore] = engine.rank_assets(assets_data)

    assert len(scores) == 2
    assert scores[0].symbol == "HIGH_PRIORITY"
    assert scores[1].symbol == "LOW_PRIORITY"


def test_engine_rank_assets_empty_list() -> None:
    """Verifies opportunity_evaluation engine handles empty asset lists gracefully."""
    engine = PortfolioOpportunityEngine()
    assert engine.rank_assets([]) == []


def test_engine_raises_error_on_invalid_asset_type() -> None:
    """Verifies engine raises ValueError on unknown asset_type."""
    engine = PortfolioOpportunityEngine()
    invalid_asset = [
        {
            "symbol": "CRYPTO",
            "asset_type": "BITCOIN",
            "current_price": 50000.0,
            "peak_price": 60000.0,
            "target_allocation_pct": 5.0,
            "current_allocation_pct": 0.0,
        }
    ]

    with pytest.raises(ValueError, match="Unsupported or missing asset_type 'BITCOIN'"):
        engine.rank_assets(invalid_asset)


def test_engine_raises_error_on_unregistered_strategy() -> None:
    """Verifies engine raises ValueError when no strategy is registered."""
    engine = PortfolioOpportunityEngine(strategies={})
    asset = [
        {
            "symbol": "AAPL",
            "asset_type": "STOCK",
            "current_price": 150.0,
            "peak_price": 150.0,
            "target_allocation_pct": 10.0,
            "current_allocation_pct": 10.0,
        }
    ]

    with pytest.raises(ValueError, match="No strategy registered for asset_type"):
        engine.rank_assets(asset)


def test_engine_validates_required_keys() -> None:
    """Verifies engine raises KeyError when required fields are missing."""
    engine = PortfolioOpportunityEngine()
    incomplete_asset = [{"symbol": "AAPL"}]

    with pytest.raises(KeyError, match="missing required fields"):
        engine.rank_assets(incomplete_asset)


def test_engine_resolves_company_exposure_fallbacks() -> None:
    """Verifies robust company exposure resolution via symbol and substrings."""
    mock_exposure = MagicMock()
    mock_exposure.calculate_company_exposure.return_value = {"Apple Inc.": 20.0}
    mock_exposure.calculate_consolidated_exposure.return_value = ({}, {})
    mock_exposure.calculate_penalty_factor.return_value = 1.0

    engine = PortfolioOpportunityEngine(exposure_engine=mock_exposure)
    assets_data = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "asset_type": "STOCK",
            "current_price": 150.0,
            "peak_price": 150.0,
            "target_allocation_pct": 10.0,
            "current_allocation_pct": 10.0,
        }
    ]
    snapshot = PortfolioSnapshot(
        timestamp="2026-08-21", total_value_eur=1000.0, assets_snapshot=[]
    )

    scores = engine.rank_assets(assets_data, portfolio_snapshot=snapshot)
    assert len(scores) == 1


def test_resolve_company_exposure_matching_variations() -> None:
    """Verifies _resolve_company_exposure lookup strategies directly."""
    engine = PortfolioOpportunityEngine()
    exposures = {
        "MSFT": 12.0,
        "Microsoft Corporation": 18.0,
        "Alphabet Inc.": 10.0,
    }

    # Direct ticker lookup
    assert engine._resolve_company_exposure("MSFT", None, exposures) == 12.0

    # Direct asset name lookup
    assert (
        engine._resolve_company_exposure("UNKNOWN", "Alphabet Inc.", exposures) == 10.0
    )

    # Substring / partial lookup
    assert engine._resolve_company_exposure("GOOGL", "Alphabet", exposures) == 10.0

    # No match
    assert engine._resolve_company_exposure("AMZN", "Amazon.com", exposures) == 0.0

    # Empty exposures
    assert engine._resolve_company_exposure("MSFT", "Microsoft", {}) == 0.0


def test_engine_applies_sector_country_penalty() -> None:
    """Verifies sector/country exposure penalty adjusts total_score."""
    mock_exposure = MagicMock()
    mock_exposure.calculate_company_exposure.return_value = {}
    mock_exposure.calculate_consolidated_exposure.return_value = (
        {"Technology": 55.0},
        {"United States": 65.0},
    )
    mock_exposure.calculate_penalty_factor.return_value = 0.80

    engine = PortfolioOpportunityEngine(exposure_engine=mock_exposure)
    assets_data = [
        {
            "symbol": "AAPL",
            "asset_type": "STOCK",
            "current_price": 150.0,
            "peak_price": 150.0,
            "target_allocation_pct": 10.0,
            "current_allocation_pct": 5.0,
            "sector": "Technology",
            "country": "United States",
        }
    ]
    snapshot = PortfolioSnapshot(
        timestamp="2026-08-21", total_value_eur=1000.0, assets_snapshot=[]
    )

    unpenalized_engine = PortfolioOpportunityEngine()
    unpenalized_scores = unpenalized_engine.rank_assets(assets_data)
    penalized_scores = engine.rank_assets(assets_data, portfolio_snapshot=snapshot)

    assert len(penalized_scores) == 1
    assert penalized_scores[0].total_score < unpenalized_scores[0].total_score
