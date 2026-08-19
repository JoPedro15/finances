"""Portfolio decision engine orchestrating asset scoring strategies using Pandas."""

from __future__ import annotations

from typing import Any

import pandas as pd

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
        """Calculates scores for all assets using DataFrame processing and ranks them.

        Args:
            assets_data: List of enriched asset payload dictionaries.

        Returns:
            Sorted list of AssetScore instances ordered by composite priority.

        Raises:
            ValueError: If an asset type is invalid or unsupported.
            KeyError: If mandatory fields are missing in an asset dict.
        """
        if not assets_data:
            return []

        # Validate all assets first
        for asset in assets_data:
            self._validate_required_keys(asset)

        # Convert input list to a pandas DataFrame for batch processing
        df: pd.DataFrame = pd.DataFrame(assets_data)
        scores: list[AssetScore] = []

        for _, row in df.iterrows():
            raw_type: Any = row.get("asset_type")
            symbol_str: str = str(row["symbol"])

            try:
                asset_type: AssetType = (
                    raw_type
                    if isinstance(raw_type, AssetType)
                    else AssetType(str(raw_type))
                )
            except ValueError as err:
                raise ValueError(
                    f"Unsupported or missing asset_type '{raw_type}' "
                    f"for asset '{symbol_str}'"
                ) from err

            if asset_type not in self._strategies:
                raise ValueError(
                    f"No strategy registered for asset_type '{asset_type}'"
                )

            strategy: ScoringStrategy = self._strategies[asset_type]

            score: AssetScore = strategy.calculate_score(
                symbol=symbol_str,
                current_price=float(row["current_price"]),
                peak_price=float(row["peak_price"]),
                target_allocation_pct=float(row["target_allocation_pct"]),
                current_allocation_pct=float(row["current_allocation_pct"]),
                ter=row.get("ter") if pd.notna(row.get("ter")) else None,
                trailing_pe=(
                    row.get("trailing_pe") if pd.notna(row.get("trailing_pe")) else None
                ),
                forward_pe=(
                    row.get("forward_pe") if pd.notna(row.get("forward_pe")) else None
                ),
                low_52w=row.get("low_52w") if pd.notna(row.get("low_52w")) else None,
                high_52w=row.get("high_52w") if pd.notna(row.get("high_52w")) else None,
            )
            scores.append(score)

        if not scores:
            return []

        # Convert scores back to DataFrame for vectorised sorting
        scores_df: pd.DataFrame = pd.DataFrame(
            [
                {
                    "symbol": s.symbol,
                    "asset_type": s.asset_type,
                    "dip_score": s.dip_score,
                    "cost_score": s.cost_score,
                    "allocation_score": s.allocation_score,
                    "total_score": s.total_score,
                    "_obj": s,
                }
                for s in scores
            ]
        )

        sorted_df: pd.DataFrame = scores_df.sort_values(
            by="total_score", ascending=False
        )
        return list(sorted_df["_obj"])
