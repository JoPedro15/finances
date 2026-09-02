"""
Unit tests for the projection CLI presenter.
"""

from unittest.mock import patch

from src.cli.projection_presenter import ProjectionPresenter
from src.core.models import (
    GrowthMilestone,
    GrowthProjectionResult,
    GrowthProjectionScenario,
)


def test_render_summary_calls_print():
    """Test that render_summary prints to console."""
    presenter = ProjectionPresenter()
    result = GrowthProjectionResult(
        initial_value=1000.0,
        monthly_contribution=100.0,
        scenarios=[],
        historical_cagr_pct=0.07,
    )

    with patch.object(presenter.console, "print") as mock_print:
        presenter.render_summary(result)
        mock_print.assert_called_once()
        # Check the Panel content
        panel = mock_print.call_args[0][0]
        assert "Initial Capital" in str(panel.renderable)


def test_render_milestones_table():
    """Test that render_milestones prints a table with milestones."""
    presenter = ProjectionPresenter()
    milestone = GrowthMilestone(
        year=10, total_invested=5000, compound_interest=1000, projected_value=6000
    )
    scenario = GrowthProjectionScenario(
        name="Primary",
        annual_return_pct=7.0,
        monthly_contribution=100.0,
        milestones={10: milestone},
    )
    result = GrowthProjectionResult(
        initial_value=1000.0,
        monthly_contribution=100.0,
        scenarios=[scenario],
        primary_scenario=scenario,
    )

    with patch.object(presenter.console, "print") as mock_print:
        presenter.render_milestones(result, scenario_name="Primary")
        mock_print.assert_called_once()
        # Verify the object printed is a Table
        # (by checking its title attribute if available in call)
        table = mock_print.call_args[0][0]
        assert "Growth Milestones" in str(table.title)
