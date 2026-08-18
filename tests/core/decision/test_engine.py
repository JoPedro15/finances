"""Unit tests for stock/ETF strategies, configuration validation,
and portfolio decision engine."""

import pytest

from src.config import EtfStrategyConfig, StockStrategyConfig
from src.core.decision.base import AssetScore
from src.core.decision.engine import PortfolioDecisionEngine
from src.core.decision.etf_strategy import EtfScoringStrategy
from src.core.decision.stock_strategy import StockScoringStrategy

# ==============================================================================
# CONFIGURATION VALIDATION TESTS
# ==============================================================================


def test_stock_config_invalid_weights() -> None:
    """Verifies that StockStrategyConfig raises ValueError when weights
    do not sum to 1.0."""
    with pytest.raises(ValueError, match="Stock strategy weights must sum to 1.0"):
        StockStrategyConfig(
            weight_dip=0.40,
            weight_forward_pe=0.40,
            weight_52w_range=0.30,
            weight_allocation=0.30,
        )


def test_etf_config_invalid_weights() -> None:
    """Verifies that EtfStrategyConfig raises ValueError when weights
    do not sum to 1.0."""
    with pytest.raises(ValueError, match="ETF strategy weights must sum to 1.0"):
        EtfStrategyConfig(
            weight_dip=0.50,
            weight_ter=0.50,
            weight_allocation=0.50,
        )


# ==============================================================================
# STOCK STRATEGY TESTS
# ==============================================================================


def test_stock_dip_score_edge_cases() -> None:
    """Tests stock dip calculation across invalid prices, minor drops,
    sweet-spots, and falling knives."""
    strategy = StockScoringStrategy()

    # Invalid price or peak
    assert strategy.calculate_dip_score(current_price=0.0, peak_price=100.0) == 0.0
    assert strategy.calculate_dip_score(current_price=100.0, peak_price=0.0) == 0.0
    assert strategy.calculate_dip_score(current_price=105.0, peak_price=100.0) == 0.0

    # Minor drop (< dip_min_pct = 5%)
    assert strategy.calculate_dip_score(
        current_price=97.0, peak_price=100.0
    ) == pytest.approx(0.12, abs=1e-4)

    # Sweet-spot drop (5% <= dip <= 20%)
    assert strategy.calculate_dip_score(current_price=90.0, peak_price=100.0) == 1.0

    # Falling knife penalty (> 20% drop)
    penalty_score = strategy.calculate_dip_score(current_price=50.0, peak_price=100.0)
    assert penalty_score < 1.0
    assert penalty_score >= 0.1


def test_stock_pe_score_growth_stagnation_and_missing() -> None:
    """Tests P/E score calculation for missing metadata, earnings growth,
    and stagnation."""
    strategy = StockScoringStrategy()

    # Missing data fallback
    assert strategy.calculate_pe_score(trailing_pe=None, forward_pe=20.0) == 0.5
    assert strategy.calculate_pe_score(trailing_pe=20.0, forward_pe=0.0) == 0.5

    # Stagnation (Forward P/E == Trailing P/E)
    assert strategy.calculate_pe_score(trailing_pe=25.0, forward_pe=25.0) == 0.6

    # Earnings growth (Forward P/E < Trailing P/E)
    growth_score = strategy.calculate_pe_score(trailing_pe=25.0, forward_pe=20.0)
    assert growth_score > 0.6
    assert growth_score <= 1.0

    # Earnings contraction (Forward P/E > Trailing P/E)
    contraction_score = strategy.calculate_pe_score(trailing_pe=20.0, forward_pe=25.0)
    assert contraction_score < 0.6


def test_stock_52w_range_score() -> None:
    """Tests 52-week position evaluation."""
    strategy = StockScoringStrategy()

    # Missing or invalid range
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

    # Bottom 30% of range
    assert (
        strategy.calculate_52w_range_score(
            current_price=110.0, low_52w=100.0, high_52w=200.0
        )
        == 1.0
    )


# ==============================================================================
# ETF STRATEGY TESTS
# ==============================================================================


def test_etf_ter_score_boundaries() -> None:
    """Tests ETF TER cost efficiency logic."""
    strategy = EtfScoringStrategy()

    # Missing or invalid metadata fallback
    assert strategy.calculate_ter_score(ter=None) == 0.5
    assert strategy.calculate_ter_score(ter=-0.05) == 0.5

    # Ultra low-cost (TER <= 0.10%)
    assert strategy.calculate_ter_score(ter=0.07) == 1.0

    # High-cost (TER >= 0.50%)
    assert strategy.calculate_ter_score(ter=0.55) == 0.0

    # Linear decay in-between
    mid_score = strategy.calculate_ter_score(ter=0.30)
    assert 0.0 < mid_score < 1.0


def test_etf_allocation_score() -> None:
    """Tests underweight allocation gap priority calculation."""
    strategy = EtfScoringStrategy()

    # Overweight or on target
    assert (
        strategy.calculate_allocation_score(
            target_allocation_pct=20.0, current_allocation_pct=25.0
        )
        == 0.0
    )

    # Underweight gap (10%+ reaches max score 1.0)
    assert (
        strategy.calculate_allocation_score(
            target_allocation_pct=30.0, current_allocation_pct=20.0
        )
        == 1.0
    )
    assert (
        strategy.calculate_allocation_score(
            target_allocation_pct=30.0, current_allocation_pct=25.0
        )
        == 0.5
    )


# ==============================================================================
# PORTFOLIO DECISION ENGINE TESTS
# ==============================================================================


def test_engine_ranks_assets_correctly() -> None:
    """Verifies that the decision engine scores and ranks assets
    in descending order."""
    engine = PortfolioDecisionEngine()

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
    assert scores[0].total_score > scores[1].total_score


def test_engine_raises_error_on_invalid_asset_type() -> None:
    """Verifies that engine raises ValueError when encountering
    an unknown asset_type."""
    engine = PortfolioDecisionEngine()

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
