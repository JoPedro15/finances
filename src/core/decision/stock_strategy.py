"""Stock scoring strategy evaluating dips, valuation growth, range,
and target allocation."""

from src.config import DEFAULT_STOCK_CONFIG, StockStrategyConfig
from src.core.decision.base import AssetScore, AssetType, ScoringStrategy


class StockScoringStrategy(ScoringStrategy):
    """Scoring strategy for individual stocks combining quantitative metrics
    and fundamentals."""

    def __init__(self, config: StockStrategyConfig | None = None) -> None:
        """Initializes the stock strategy with configurable weights and boundaries."""
        self.config: StockStrategyConfig = config or DEFAULT_STOCK_CONFIG

    def calculate_dip_score(self, current_price: float, peak_price: float) -> float:
        """Calculates dip score with trapezoidal sweet-spot
        and falling knife protection.

        - < dip_min_pct (e.g., 5%): Low score (0.0 to 0.2).
        - dip_min_pct to dip_max_pct (e.g., 5% - 20%): Maximum score (1.0).
        - > dip_max_pct (e.g., > 20%): Penalty decay to protect against value traps.
        """
        if peak_price <= 0.0 or current_price <= 0.0:
            return 0.0

        dip_pct: float = ((peak_price - current_price) / peak_price) * 100.0

        if dip_pct < 0.0:
            return 0.0

        if dip_pct < self.config.dip_min_pct:
            return (dip_pct / self.config.dip_min_pct) * 0.2

        if self.config.dip_min_pct <= dip_pct <= self.config.dip_max_pct:
            return 1.0

        # Falling knife protection: Progressive penalty above dip_max_pct
        excess_drop: float = dip_pct - self.config.dip_max_pct
        penalty_score: float = max(0.1, 1.0 - (excess_drop / 30.0))
        return penalty_score

    def calculate_pe_score(
        self, trailing_pe: float | None, forward_pe: float | None
    ) -> float:
        """Evaluates forward vs trailing P/E with bounded proportional growth reward."""
        if (
            trailing_pe is None
            or forward_pe is None
            or trailing_pe <= 0.0
            or forward_pe <= 0.0
        ):
            return 0.5  # Neutral default for missing data

        pe_ratio: float = forward_pe / trailing_pe

        # Earnings growth (pe_ratio < 1.0): scales from 0.6 up to 1.0 cap
        # (~20% earnings growth)
        if pe_ratio < 1.0:
            growth_bonus: float = (1.0 - pe_ratio) * 2.4
            return min(1.0, 0.6 + growth_bonus)

        # Earnings stagnation/contraction (pe_ratio >= 1.0):
        # decays from 0.6 to floor 0.0
        return max(0.0, 0.6 - (pe_ratio - 1.0))

    def calculate_52w_range_score(
        self,
        current_price: float,
        low_52w: float | None,
        high_52w: float | None,
    ) -> float:
        """Evaluates current price position within the 52-week high/low range."""
        if (
            low_52w is None
            or high_52w is None
            or high_52w <= low_52w
            or current_price <= 0.0
        ):
            return 0.5  # Neutral default score

        range_span: float = high_52w - low_52w
        relative_pos: float = max(0.0, min(1.0, (current_price - low_52w) / range_span))

        if relative_pos <= 0.30:
            return 1.0  # Trading near bottom 30% of annual range

        return max(0.0, 1.0 - ((relative_pos - 0.30) / 0.70))

    def calculate_allocation_score(
        self, target_allocation_pct: float, current_allocation_pct: float
    ) -> float:
        """Calculates underweight allocation gap priority score."""
        gap_pct: float = target_allocation_pct - current_allocation_pct
        if gap_pct <= 0.0:
            return 0.0  # Overweight or on target

        return max(0.0, min(1.0, gap_pct / self.config.alloc_gap_max_pct))

    def calculate_score(
        self,
        symbol: str,
        current_price: float,
        peak_price: float,
        target_allocation_pct: float,
        current_allocation_pct: float,
        ter: float | None = None,
        trailing_pe: float | None = None,
        forward_pe: float | None = None,
        low_52w: float | None = None,
        high_52w: float | None = None,
        **kwargs: object,
    ) -> AssetScore:
        """Calculates the composite score for an individual stock using all metrics."""
        dip_score: float = self.calculate_dip_score(current_price, peak_price)
        pe_score: float = self.calculate_pe_score(trailing_pe, forward_pe)
        range_score: float = self.calculate_52w_range_score(
            current_price, low_52w, high_52w
        )
        allocation_score: float = self.calculate_allocation_score(
            target_allocation_pct, current_allocation_pct
        )

        total_score: float = (
            (dip_score * self.config.weight_dip)
            + (pe_score * self.config.weight_forward_pe)
            + (range_score * self.config.weight_52w_range)
            + (allocation_score * self.config.weight_allocation)
        )

        return AssetScore(
            symbol=symbol,
            asset_type=AssetType.STOCK,
            dip_score=round(dip_score, 4),
            cost_score=round(
                pe_score, 4
            ),  # Reuses cost_score slot for valuation/P-E score
            allocation_score=round(allocation_score, 4),
            total_score=round(total_score, 4),
        )
