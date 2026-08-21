"""Portfolio opportunity_evaluation engine orchestrating asset scoring strategies
and enforcing exposure constraints using Pandas."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.config import settings
from src.core.exposure import ExposureEngine
from src.core.models import PortfolioSnapshot
from src.core.opportunity_evaluation.base import AssetScore, AssetType, ScoringStrategy
from src.core.opportunity_evaluation.etf_strategy import EtfScoringStrategy
from src.core.opportunity_evaluation.stock_strategy import StockScoringStrategy
from src.utils.logger.logger import logger

_REQUIRED_ASSET_KEYS: tuple[str, ...] = (
    "symbol",
    "current_price",
    "peak_price",
    "target_allocation_pct",
    "current_allocation_pct",
)


class PortfolioOpportunityEngine:
    """Opportunity evaluation engine that delegates calculations to asset-specific
    strategies and applies exposure constraints."""

    def __init__(
        self,
        strategies: dict[AssetType, ScoringStrategy] | None = None,
        exposure_engine: ExposureEngine | None = None,
    ) -> None:
        """Initializes the engine with strategy mappings
        and exposure engine for policy checks.

        Args:
            strategies: Optional custom strategy mapping for dependency injection.
            exposure_engine: Optional exposure engine for
            look-through allocation checks.
        """
        self._strategies: dict[AssetType, ScoringStrategy] = (
            strategies
            if strategies is not None
            else {
                AssetType.ETF: EtfScoringStrategy(),
                AssetType.STOCK: StockScoringStrategy(),
            }
        )
        self._exposure_engine: ExposureEngine = exposure_engine or ExposureEngine()

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

    def _resolve_company_exposure(
        self,
        symbol: str,
        asset_name: str | None,
        company_exposures: dict[str, float],
    ) -> float:
        """Resolves company exposure robustly by matching ticker symbol,
        asset name, or partial substrings.

        Args:
            symbol: Ticker symbol of the asset.
            asset_name: Optional descriptive name of the asset.
            company_exposures: Dictionary mapping consolidated
            entity names to exposure percentages.

        Returns:
            Matched exposure percentage or 0.0 if not found.
        """
        if not company_exposures:
            return 0.0

        # Direct lookups
        if symbol in company_exposures:
            return company_exposures[symbol]

        if asset_name and asset_name in company_exposures:
            return company_exposures[asset_name]

        # Case-insensitive and substring fallback matching
        symbol_lower: str = symbol.lower()
        name_lower: str = asset_name.lower() if asset_name else ""

        for key, exposure in company_exposures.items():
            key_lower: str = key.lower()
            if (
                symbol_lower in key_lower
                or key_lower in symbol_lower
                or (name_lower and (name_lower in key_lower or key_lower in name_lower))
            ):
                return exposure

        return 0.0

    def rank_assets(
        self,
        assets_data: list[dict[str, Any]],
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> list[AssetScore]:
        """Calculates scores for all assets using DataFrame processing,
        evaluates exposure limits, and ranks them.

        Args:
            assets_data: List of enriched asset payload dictionaries.
            portfolio_snapshot: Optional portfolio snapshot
            for look-through exposure validation.

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

        # Calculate sector, country, and company look-through exposures
        # if snapshot is provided
        sector_percentages: dict[str, float] = {}
        country_percentages: dict[str, float] = {}
        company_exposures: dict[str, float] = {}

        if portfolio_snapshot and portfolio_snapshot.total_value_eur > 0.0:
            company_exposures = self._exposure_engine.calculate_company_exposure(
                portfolio_snapshot
            )
            (
                sector_percentages,
                country_percentages,
            ) = self._exposure_engine.calculate_consolidated_exposure(
                portfolio_snapshot
            )

        max_company_limit: float = settings.max_company_allocation_pct

        # Convert input list to a pandas DataFrame for batch processing
        df: pd.DataFrame = pd.DataFrame(assets_data)
        scores: list[AssetScore] = []

        for _, row in df.iterrows():
            raw_type: Any = row.get("asset_type")
            symbol_str: str = str(row["symbol"])
            asset_name_str: str | None = row.get("name") or row.get("description")

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

            # Evaluate sector and country exposure penalty factor
            sector_str: str | None = (
                str(row["sector"]) if pd.notna(row.get("sector")) else None
            )
            country_str: str | None = (
                str(row["country"]) if pd.notna(row.get("country")) else None
            )

            penalty_factor: float = self._exposure_engine.calculate_penalty_factor(
                sector=sector_str,
                country=country_str,
                sector_percentages=sector_percentages,
                country_percentages=country_percentages,
            )

            if penalty_factor < 1.0:
                logger.warning(
                    f"Asset '{symbol_str}' penalized in ranking: "
                    f"Consolidated sector/country exposure limits breached "
                    f"(penalty factor: {penalty_factor:.2f})."
                )
                score = AssetScore(
                    symbol=score.symbol,
                    asset_type=score.asset_type,
                    dip_score=score.dip_score,
                    cost_score=score.cost_score,
                    allocation_score=score.allocation_score,
                    total_score=max(0.0, round(score.total_score * penalty_factor, 3)),
                )

            # Evaluate company policy limits using robust resolution helper
            current_company_exposure: float = self._resolve_company_exposure(
                symbol=symbol_str,
                asset_name=asset_name_str,
                company_exposures=company_exposures,
            )

            if current_company_exposure > max_company_limit:
                exposure_penalty: float = 0.5
                logger.warning(
                    f"Asset '{symbol_str}' penalized in ranking: "
                    f"Consolidated company exposure "
                    f"({current_company_exposure:.1f}%) exceeds "
                    f"policy limit ({max_company_limit:.1f}%)."
                )
                score = AssetScore(
                    symbol=score.symbol,
                    asset_type=score.asset_type,
                    dip_score=score.dip_score,
                    cost_score=score.cost_score,
                    allocation_score=score.allocation_score,
                    total_score=max(
                        0.0, round(score.total_score - exposure_penalty, 3)
                    ),
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
