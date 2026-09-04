"""
Unit tests for the projection calculation engine.
"""

from unittest.mock import MagicMock

from src.core.projections import ProjectionEngine


def test_calculate_future_value_zero_growth():
    """Test future value with 0% growth."""
    engine = ProjectionEngine()
    # 1000 initial + (100 * 12 * 10 years) = 13000
    fv = engine.calculate_future_value(1000.0, 100.0, 0.0, 10)
    assert fv == 13000.0


def test_calculate_future_value_with_growth():
    """Test future value with 7% growth (approximate check)."""
    engine = ProjectionEngine()
    fv = engine.calculate_future_value(1000.0, 100.0, 0.07, 10)
    # Expected approx 19072 based on previous CLI run
    assert 19070 < fv < 19075


def test_generate_scenario_milestones():
    """Test that scenario generation includes correct milestones."""
    engine = ProjectionEngine()
    scenario = engine.generate_scenario("Test", 1000.0, 100.0, 0.07, horizons=[10, 20])

    assert scenario.name == "Test"
    assert 10 in scenario.milestones
    assert 20 in scenario.milestones
    assert 30 not in scenario.milestones
    assert scenario.milestones[10].year == 10
    assert scenario.milestones[10].projected_value > 1000


def test_calculate_future_value_edge_cases():
    """Test edge cases for projection calculations."""
    engine = ProjectionEngine()

    # Zero years
    assert engine.calculate_future_value(1000.0, 100.0, 0.07, 0) == 1000.0

    # Negative years (should treat as 0 or handle gracefully)
    assert engine.calculate_future_value(1000.0, 100.0, 0.07, -1) == 1000.0


def test_generate_scenario_progression_length():
    """Test that progression list has correct length."""
    engine = ProjectionEngine()
    scenario = engine.generate_scenario("Test", 1000.0, 100.0, 0.07, horizons=[5])
    # Years 0, 1, 2, 3, 4, 5
    assert len(scenario.progression) == 6


def test_generate_scenario_default_horizons() -> None:
    """Test that default horizons (10, 20, 30) are used when none provided."""
    engine = ProjectionEngine()
    scenario = engine.generate_scenario("Default", 1000.0, 100.0, 0.07)
    assert 10 in scenario.milestones
    assert 20 in scenario.milestones
    assert 30 in scenario.milestones


def test_calculate_historical_cagr_insufficient_history() -> None:
    """Returns 0.0 when fewer than 2 valid history entries exist."""
    engine = ProjectionEngine()
    mock_extractor = MagicMock()
    mock_extractor.fetch_portfolio_history.return_value = []
    assert engine.calculate_historical_cagr(mock_extractor) == 0.0


def test_calculate_historical_cagr_single_entry() -> None:
    """Returns 0.0 with only one valid snapshot."""
    engine = ProjectionEngine()
    snap = MagicMock()
    snap.total_value_eur = 1000.0
    snap.snapshot_date = "2025-01-01"
    mock_extractor = MagicMock()
    mock_extractor.fetch_portfolio_history.return_value = [snap]
    assert engine.calculate_historical_cagr(mock_extractor) == 0.0


def test_calculate_historical_cagr_less_than_one_hour() -> None:
    """Returns 0.0 when duration is less than 1 hour."""
    engine = ProjectionEngine()
    snap_a = MagicMock()
    snap_a.total_value_eur = 1000.0
    snap_a.snapshot_date = "2025-01-01T10:00:00"
    snap_b = MagicMock()
    snap_b.total_value_eur = 1100.0
    snap_b.snapshot_date = "2025-01-01T10:30:00"
    mock_extractor = MagicMock()
    mock_extractor.fetch_portfolio_history.return_value = [snap_a, snap_b]
    assert engine.calculate_historical_cagr(mock_extractor) == 0.0


def test_calculate_historical_cagr_less_than_one_year() -> None:
    """Returns absolute return for sub-annual periods."""
    engine = ProjectionEngine()
    snap_a = MagicMock()
    snap_a.total_value_eur = 1000.0
    snap_a.snapshot_date = "2025-01-01"
    snap_b = MagicMock()
    snap_b.total_value_eur = 1100.0
    snap_b.snapshot_date = "2025-07-01"
    mock_extractor = MagicMock()
    mock_extractor.fetch_portfolio_history.return_value = [snap_a, snap_b]
    result = engine.calculate_historical_cagr(mock_extractor)
    assert abs(result - 0.1) < 0.01


def test_calculate_historical_cagr_multi_year() -> None:
    """Returns annualised CAGR for multi-year periods."""
    engine = ProjectionEngine()
    snap_a = MagicMock()
    snap_a.total_value_eur = 1000.0
    snap_a.snapshot_date = "2022-01-01"
    snap_b = MagicMock()
    snap_b.total_value_eur = 1331.0
    snap_b.snapshot_date = "2025-01-01"
    mock_extractor = MagicMock()
    mock_extractor.fetch_portfolio_history.return_value = [snap_a, snap_b]
    result = engine.calculate_historical_cagr(mock_extractor)
    # (1331/1000)^(1/3) - 1 ≈ 0.10
    assert abs(result - 0.10) < 0.02
