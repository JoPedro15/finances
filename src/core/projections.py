"""
Projection calculation engine for long-term portfolio growth.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from src.core.models import (
    GrowthMilestone,
    GrowthProjectionScenario,
)

if TYPE_CHECKING:
    from src.infra.database.finance_sql_extraction import FinanceSQLExtractor


class ProjectionEngine:
    """Calculates compound interest projections with periodic contributions."""

    @staticmethod
    def calculate_future_value(
        initial_value: float,
        monthly_contribution: float,
        annual_rate: float,
        years: int,
    ) -> float:
        """
        Calculates future value using the formula:
        FV = PV * (1 + r)^t + PMT * [((1 + r)^t - 1) / r]
        where r is the monthly rate and t is the total number of months.
        """
        if years <= 0:
            return initial_value

        months = years * 12
        monthly_rate = (1 + annual_rate) ** (1 / 12) - 1

        if monthly_rate == 0:
            return float(initial_value + (monthly_contribution * months))

        fv_principal = initial_value * ((1 + monthly_rate) ** months)
        fv_contributions = monthly_contribution * (
            ((1 + monthly_rate) ** months - 1) / monthly_rate
        )

        return float(fv_principal + fv_contributions)

    def generate_scenario(
        self,
        name: str,
        initial_value: float,
        monthly_contribution: float,
        annual_rate: float,
        horizons: list[int] | None = None,
        inflation_rate: float = 0.02,
    ) -> GrowthProjectionScenario:
        """Generates a complete projection scenario for given horizons."""
        if horizons is None:
            horizons = [10, 20, 30]

        progression: list[GrowthMilestone] = []
        milestones: dict[int, GrowthMilestone] = {}

        # Generate yearly progression
        max_horizon = max(horizons)
        for year in range(max_horizon + 1):
            projected_val = self.calculate_future_value(
                initial_value, monthly_contribution, annual_rate, year
            )
            total_invested = initial_value + (monthly_contribution * 12 * year)
            compound_interest = projected_val - total_invested

            # Discount for inflation: Real Value = Nominal / (1 + i)^t
            inflation_adjusted = projected_val / ((1 + inflation_rate) ** year)

            milestone = GrowthMilestone(
                year=year,
                total_invested=total_invested,
                compound_interest=compound_interest,
                projected_value=projected_val,
                inflation_adjusted_value=inflation_adjusted,
            )
            progression.append(milestone)

            if year in horizons:
                milestones[year] = milestone

        return GrowthProjectionScenario(
            name=name,
            annual_return_pct=annual_rate * 100,
            monthly_contribution=monthly_contribution,
            progression=progression,
            milestones=milestones,
        )

    def calculate_historical_cagr(self, extractor: FinanceSQLExtractor) -> float:
        """Estimates historical CAGR from database snapshots."""
        history = extractor.fetch_portfolio_history()

        # Filter out snapshots with zero value to avoid division by zero
        valid_history = [h for h in history if h.total_value_eur > 0]

        if len(valid_history) < 2:
            return 0.0

        start_val = valid_history[0].total_value_eur
        end_val = valid_history[-1].total_value_eur

        try:
            # Parse dates to calculate real duration in years (as a fraction)
            start_date = datetime.fromisoformat(
                valid_history[0].snapshot_date.replace(" ", "T")
            )
            end_date = datetime.fromisoformat(
                valid_history[-1].snapshot_date.replace(" ", "T")
            )

            duration_seconds = (end_date - start_date).total_seconds()
            # If duration is less than 1 hour, return 0
            if duration_seconds < 3600:
                return 0.0

            years = duration_seconds / (365.25 * 24 * 3600)

            if years < 1.0:
                # 1. Períodos < 1 ano: Retorno Absoluto (não anualizado)
                return float((end_val / start_val) - 1)

            # 2. Períodos >= 1 ano: CAGR (Média Geométrica)
            return float(pow(end_val / start_val, 1 / years) - 1)
        except (ValueError, ZeroDivisionError, OverflowError):
            return 0.0
