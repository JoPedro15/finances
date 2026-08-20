"""
Utility script to migrate existing JSON dataset files into the SQLite database.
"""

from __future__ import annotations

from dataclasses import replace
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

    p_json_path: Path = Path(portfolio_json)
    h_json_path: Path = Path(history_json)

    json_p_repo: JsonPortfolioRepository = JsonPortfolioRepository(p_json_path)
    json_h_repo: JsonHistoryRepository = JsonHistoryRepository(h_json_path)

    sql_p_repo: SqlitePortfolioRepository = SqlitePortfolioRepository(sqlite_db)
    sql_h_repo: SqliteHistoryRepository = SqliteHistoryRepository(sqlite_db)

    # 1. Migrate Portfolio Assets
    try:
        assets: list[Asset] = json_p_repo.load_assets()
        if assets:
            normalized_assets: list[Asset] = [
                (
                    replace(asset, asset_type=asset.asset_type.lower())
                    if asset.asset_type
                    else asset
                )
                for asset in assets
            ]
            sql_p_repo.save_assets(normalized_assets)
            logger.success(f"Migrated {len(assets)} portfolio assets to SQLite.")
        else:
            logger.warning(f"No assets found in '{p_json_path}'.")
    except Exception as e:
        logger.error(f"Failed to migrate portfolio assets: {e}")

    # 2. Migrate History Snapshots (Optional legacy check)
    try:
        if h_json_path.exists():
            history: list[PortfolioSnapshot] = json_h_repo.load_history()
            if history:
                existing_snapshots: list[PortfolioSnapshot] = sql_h_repo.load_history()
                existing_timestamps: set[str] = {
                    s.timestamp for s in existing_snapshots
                }

                migrated_count: int = 0
                for snapshot in history:
                    if snapshot.timestamp not in existing_timestamps:
                        sql_h_repo.save_snapshot(snapshot)
                        migrated_count += 1

                logger.success(
                    f"Migrated {migrated_count} historical snapshots to SQLite."
                )
        else:
            logger.info(
                f"Legacy history file '{h_json_path}' not found. "
                f"Skipping history migration."
            )
    except Exception as e:
        logger.error(f"Failed to migrate history snapshots: {e}")

    logger.section("Migration Completed")


if __name__ == "__main__":
    migrate_json_to_sqlite()
