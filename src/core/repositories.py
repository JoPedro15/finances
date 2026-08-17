"""
Repository protocols and JSON storage implementations for
portfolio, history, and ETF cache data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from src.config import DEFAULT_ETF_CACHE_TTL_DAYS, ETF_CACHE_FILE
from src.core.exceptions import StorageReadError, StorageWriteError
from src.core.models import Asset, ETFDetails, PortfolioSnapshot
from src.utils.logger.logger import logger


class PortfolioRepository(Protocol):
    """Protocol defining operations for reading portfolio configuration."""

    def load_assets(self) -> list[Asset]:
        """Loads all configured assets from storage."""
        ...


class HistoryRepository(Protocol):
    """Protocol defining operations for portfolio history persistence."""

    def load_history(self) -> list[PortfolioSnapshot]:
        """Loads all recorded portfolio snapshots from storage."""
        ...

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Saves a new portfolio snapshot to storage."""
        ...


class ETFCacheRepository(Protocol):
    """Protocol defining operations for caching ETF metadata."""

    def get_etf_details(self, isin: str) -> ETFDetails | None:
        """Retrieves cached ETF details for a given ISIN if available and valid."""
        ...

    def save_etf_details(self, isin: str, details: ETFDetails) -> None:
        """Saves or updates ETF details in the cache."""
        ...


class JsonPortfolioRepository:
    """JSON file-based implementation of PortfolioRepository."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path: Path = Path(file_path)

    def load_assets(self) -> list[Asset]:
        """Loads assets from a local JSON portfolio file."""
        if not self.file_path.exists():
            raise StorageReadError(f"Portfolio file not found at '{self.file_path}'.")

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return [Asset.from_dict(item) for item in data.get("assets", [])]
        except (json.JSONDecodeError, OSError) as e:
            raise StorageReadError(
                f"Failed to read portfolio from '{self.file_path}': {e}"
            ) from e


class JsonHistoryRepository:
    """JSON file-based implementation of HistoryRepository."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path: Path = Path(file_path)

    def load_history(self) -> list[PortfolioSnapshot]:
        """Loads history snapshots from a local JSON file."""
        if not self.file_path.exists():
            return []

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data: list[dict[str, Any]] = json.load(f)
                return [PortfolioSnapshot.from_dict(item) for item in data]
        except (json.JSONDecodeError, OSError) as e:
            raise StorageReadError(
                f"Failed to read history from '{self.file_path}': {e}"
            ) from e

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        """Appends a snapshot to the local JSON history file."""
        history: list[PortfolioSnapshot] = self.load_history()
        history.append(snapshot)

        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                raw_data: list[dict[str, Any]] = [s.to_dict() for s in history]
                json.dump(raw_data, f, indent=2)
        except OSError as e:
            raise StorageWriteError(
                f"Failed to write history to '{self.file_path}': {e}"
            ) from e


class JsonETFCacheRepository:
    """JSON file-based implementation of ETFCacheRepository with TTL validation."""

    def __init__(
        self,
        file_path: str | Path = ETF_CACHE_FILE,
        ttl_days: int = DEFAULT_ETF_CACHE_TTL_DAYS,
    ) -> None:
        self.file_path: Path = Path(file_path)
        self.ttl_days: int = ttl_days

    def get_etf_details(self, isin: str) -> ETFDetails | None:
        """Retrieves cached ETF details for an ISIN if unexpired and valid."""
        if not self.file_path.exists():
            return None

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                f"Corrupted or unreadable ETF cache file at '{self.file_path}': {e}"
            )
            return None

        entry: dict[str, Any] | None = data.get(isin)
        if not entry or not isinstance(entry, dict):
            return None

        cached_at_str: str | None = entry.get("cached_at")
        raw_details: dict[str, Any] | None = entry.get("details")

        if not cached_at_str or raw_details is None:
            return None

        try:
            cached_at = datetime.fromisoformat(cached_at_str)
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=UTC)

            now = datetime.now(UTC)
            age_days = (now - cached_at).total_seconds() / 86400.0

            if age_days > self.ttl_days:
                logger.info(
                    f"Cache entry for ISIN {isin} expired ({age_days:.1f} days old)."
                )
                return None

            return ETFDetails.from_dict(raw_details)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse cached ETF details for ISIN {isin}: {e}")
            return None

    def save_etf_details(self, isin: str, details: ETFDetails) -> None:
        """Persists ETF details into the JSON cache file with current timestamp."""
        cache_data: dict[str, Any] = {}

        if self.file_path.exists():
            try:
                with open(self.file_path, encoding="utf-8") as f:
                    cache_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                cache_data = {}

        cache_data[isin] = {
            "cached_at": datetime.now(UTC).isoformat(),
            "details": details.to_dict(),
        }

        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
        except OSError as e:
            raise StorageWriteError(
                f"Failed to write ETF cache to '{self.file_path}': {e}"
            ) from e
