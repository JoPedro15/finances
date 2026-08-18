"""Portfolio decision engine orchestrating asset scoring strategies."""

from __future__ import annotations

from typing import Any

from src.core.decision.base import AssetScore, AssetType, ScoringStrategy
from src.core.decision.etf_strategy import EtfScoringStrategy
from src.core.decision.stock_strategy import StockScoringStrategy

_REQUIRED_ASSET_KEYS: tuple[str, ...] = (
    "symbol",
    "current_price",
    "peak_price",
    "target_allocation_pct",
    "current_allocation_pct",
)


class PortfolioDecisionEngine:
    """Decision engine that delegates calculations to asset-specific strategies."""

    def __init__(
        self, strategies: dict[AssetType, ScoringStrategy] | None = None
    ) -> None:
        """Initializes the engine with strategy mappings for supported asset types.

        Args:
            strategies: Optional custom strategy mapping for dependency injection.
        """
        self._strategies: dict[AssetType, ScoringStrategy] = strategies or {
            AssetType.ETF: EtfScoringStrategy(),
            AssetType.STOCK: StockScoringStrategy(),
        }

    def _validate_required_keys(self, asset: dict[str, Any]) -> None:
        """Validates that all mandatory fields exist in the asset payload.

        Args:
            asset: Raw asset data dictionary.

        Raises:
            KeyError: If any required field is missing.
        """
        symbol: str = str(asset.get("symbol", "UNKNOWN"))
        missing_keys: list[str] = [
            key for key in _REQUIRED_ASSET_KEYS if key not in asset
        ]
        if missing_keys:
            raise KeyError(
                f"Asset '{symbol}' is missing required fields: {missing_keys}"
            )

    def rank_assets(self, assets_data: list[dict[str, Any]]) -> list[AssetScore]:
        """Calculates scores for all assets and ranks them in descending order.

        Args:
            assets_data: List of enriched asset payload dictionaries.

        Returns:
            Sorted list of AssetScore instances ordered by composite priority.

        Raises:
            ValueError: If an asset type is invalid or unsupported.
            KeyError: If mandatory fields are missing in an asset dict.
        """
        scores: list[AssetScore] = []

        for asset in assets_data:
            self._validate_required_keys(asset)

            raw_type: Any = asset.get("asset_type")
            try:
                asset_type: AssetType = (
                    raw_type
                    if isinstance(raw_type, AssetType)
                    else AssetType(str(raw_type))
                )
            except ValueError as err:
                symbol: str = str(asset["symbol"])
                raise ValueError(
                    f"Unsupported or missing asset_type '{raw_type}' "
                    f"for asset '{symbol}'"
                ) from err

            if asset_type not in self._strategies:
                raise ValueError(
                    f"No strategy registered for asset_type '{asset_type}'"
                )

            strategy: ScoringStrategy = self._strategies[asset_type]

            score: AssetScore = strategy.calculate_score(
                symbol=str(asset["symbol"]),
                current_price=float(asset["current_price"]),
                peak_price=float(asset["peak_price"]),
                target_allocation_pct=float(asset["target_allocation_pct"]),
                current_allocation_pct=float(asset["current_allocation_pct"]),
                ter=asset.get("ter"),
                trailing_pe=asset.get("trailing_pe"),
                forward_pe=asset.get("forward_pe"),
                low_52w=asset.get("low_52w"),
                high_52w=asset.get("high_52w"),
            )
            scores.append(score)

        return sorted(scores, key=lambda x: x.total_score, reverse=True)
