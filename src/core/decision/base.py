"""Base interfaces and data structures for asset scoring strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AssetType(StrEnum):
    """Supported financial asset classifications."""

    ETF = "ETF"
    STOCK = "STOCK"


@dataclass(frozen=True)
class AssetScore:
    """Calculated composite priority score container for a single asset."""

    symbol: str
    asset_type: AssetType
    dip_score: float
    cost_score: float
    allocation_score: float
    total_score: float


class ScoringStrategy(ABC):
    """Abstract base strategy for calculating asset priority scores."""

    @abstractmethod
    def calculate_score(
        self,
        symbol: str,
        current_price: float,
        peak_price: float,
        target_allocation_pct: float,
        current_allocation_pct: float,
        ter: float | None = None,
        **kwargs: Any,
    ) -> AssetScore:
        """Calculates the normalized composite score for an asset."""
        pass
