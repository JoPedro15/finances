"""
Repository protocols and JSON storage implementations for portfolio and history data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from src.core.exceptions import StorageReadError, StorageWriteError
from src.core.models import Asset, PortfolioSnapshot


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
