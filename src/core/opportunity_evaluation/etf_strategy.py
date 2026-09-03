"""ETF scoring strategy evaluating price drops, total expense
ratios (TER), and allocation gaps."""

from src.config import DEFAULT_ETF_CONFIG, EtfStrategyConfig
from src.core.opportunity_evaluation.base import AssetScore, AssetType, ScoringStrategy


class EtfScoringStrategy(ScoringStrategy):
    """Scoring strategy for ETFs combining technical discount,
    cost efficiency (TER), and allocation priority."""

    def __init__(self, config: EtfStrategyConfig | None = None) -> None:
        """Initializes the ETF strategy with configurable weights and boundaries."""
        self.config: EtfStrategyConfig = config or DEFAULT_ETF_CONFIG

    def calculate_dip_score(self, current_price: float, peak_price: float) -> float:
        """Calculates dip score with trapezoidal sweet-spot and
        falling knife protection."""
        if peak_price <= 0.0 or current_price <= 0.0:
            return 0.0

        dip_pct: float = ((peak_price - current_price) / peak_price) * 100.0

        if dip_pct < 0.0:
            return 0.0

        if dip_pct < self.config.dip_min_pct:
            return (dip_pct / self.config.dip_min_pct) * 0.2

        if self.config.dip_min_pct <= dip_pct <= self.config.dip_max_pct:
            return 1.0

        # Penalty decay above dip_max_pct
        excess_drop: float = dip_pct - self.config.dip_max_pct
        penalty_score: float = max(0.1, 1.0 - (excess_drop / 20.0))
        return penalty_score

    def calculate_ter_score(self, ter: float | None) -> float:
        """Evaluates ETF Total Expense Ratio (TER) cost efficiency."""
        if ter is None or ter < 0.0:
            return 0.5  # Neutral default for missing metadata

        if ter <= self.config.ter_low_pct:
            return 1.0  # Ultra low-cost index ETF

        if ter >= self.config.ter_high_pct:
            return 0.0  # High-cost ETF

        # Linear decay between ter_low_pct and ter_high_pct
        ter_span: float = self.config.ter_high_pct - self.config.ter_low_pct
        return round(1.0 - ((ter - self.config.ter_low_pct) / ter_span), 4)

    def calculate_allocation_score(
        self, target_allocation_pct: float, current_allocation_pct: float
    ) -> float:
        """Calculates underweight allocation gap priority score using relative gap.

        Measures the percentage of the target that is still missing.
        Example: Target 10%, Current 5% -> 50% missing (0.5 score).
        Example: Target 2%, Current 0% -> 100% missing (1.0 score).
        """
        if target_allocation_pct <= 0.0:
            return 0.0

        gap_pct: float = target_allocation_pct - current_allocation_pct
        if gap_pct <= 0.0:
            return 0.0  # Overweight or on target

        return max(0.0, min(1.0, gap_pct / target_allocation_pct))

    def calculate_score(
        self,
        symbol: str,
        current_price: float,
        peak_price: float,
        target_allocation_pct: float,
        current_allocation_pct: float,
        ter: float | None = None,
        **kwargs: object,
    ) -> AssetScore:
        """Calculates the composite score for an ETF asset."""
        dip_score: float = self.calculate_dip_score(current_price, peak_price)
        ter_score: float = self.calculate_ter_score(ter)
        allocation_score: float = self.calculate_allocation_score(
            target_allocation_pct, current_allocation_pct
        )

        total_score: float = (
            (dip_score * self.config.weight_dip)
            + (ter_score * self.config.weight_ter)
            + (allocation_score * self.config.weight_allocation)
        )

        return AssetScore(
            symbol=symbol,
            asset_type=AssetType.ETF,
            dip_score=round(dip_score, 4),
            cost_score=round(ter_score, 4),
            allocation_score=round(allocation_score, 4),
            total_score=round(total_score, 4),
        )
