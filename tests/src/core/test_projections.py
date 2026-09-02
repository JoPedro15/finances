"""
Unit tests for the projection calculation engine.
"""

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
