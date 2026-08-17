"""
Utility script to migrate existing JSON dataset files into the SQLite database.
"""

from __future__ import annotations

from pathlib import Path

from src.core.models import Asset, PortfolioSnapshot
from src.core.repositories import (
    JsonHistoryRepository,
    JsonPortfolioRepository,
    SqliteHistoryRepository,
    SqlitePortfolioRepository,
)
from src.infra.database.connection import DEFAULT_DB_PATH
from src.utils.logger.logger import logger


def migrate_json_to_sqlite(
    portfolio_json: str | Path = "data/portfolio.json",
    history_json: str | Path = "data/history.json",
    sqlite_db: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Migrates assets and historical snapshots from JSON to SQLite."""
    logger.section("Starting JSON to SQLite Data Migration")

    json_p_repo: JsonPortfolioRepository = JsonPortfolioRepository(portfolio_json)
    json_h_repo: JsonHistoryRepository = JsonHistoryRepository(history_json)

    sql_p_repo: SqlitePortfolioRepository = SqlitePortfolioRepository(sqlite_db)
    sql_h_repo: SqliteHistoryRepository = SqliteHistoryRepository(sqlite_db)

    # 1. Migrate Portfolio Assets
    try:
        assets: list[Asset] = json_p_repo.load_assets()
        if assets:
            sql_p_repo.save_assets(assets)
            logger.success(f"Migrated {len(assets)} portfolio assets to SQLite.")
        else:
            logger.warning(f"No assets found in '{portfolio_json}'.")
    except Exception as e:
        logger.error(f"Failed to migrate portfolio assets: {e}")

    # 2. Migrate History Snapshots
    try:
        history: list[PortfolioSnapshot] = json_h_repo.load_history()
        if history:
            existing_snapshots: list[PortfolioSnapshot] = sql_h_repo.load_history()
            existing_timestamps: set[str] = {s.timestamp for s in existing_snapshots}

            migrated_count: int = 0
            for snapshot in history:
                if snapshot.timestamp not in existing_timestamps:
                    sql_h_repo.save_snapshot(snapshot)
                    migrated_count += 1

            logger.success(f"Migrated {migrated_count} historical snapshots to SQLite.")
        else:
            logger.warning(f"No history snapshots found in '{history_json}'.")
    except Exception as e:
        logger.error(f"Failed to migrate history snapshots: {e}")

    logger.section("Migration Completed")


if __name__ == "__main__":
    migrate_json_to_sqlite()
