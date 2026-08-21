"""CLI command for synchronizing stock fundamental history into SQLite database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.core.models import Asset, StockDetails
from src.core.providers import StockProvider
from src.core.repositories import SqliteDecisionRepository
from src.infra.database.connection import DEFAULT_DB_PATH, get_db_context
from src.utils.logger.logger import logger


def sync_stock_fundamentals(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Fetches fundamental data for stock assets and persists snapshots to SQLite.

    Args:
        db_path: Path to the SQLite database file.
    """
    db_path_obj: Path = Path(db_path)
    if not db_path_obj.exists():
        logger.error(f"Database file not found at '{db_path_obj}'. Aborting sync.")
        sys.exit(1)

    decision_repo: SqliteDecisionRepository = SqliteDecisionRepository(
        db_path=db_path_obj
    )
    stock_provider: StockProvider = StockProvider()

    try:
        with get_db_context(str(db_path_obj)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, isin, name, yahoo_ticker, quantity, "
                "average_buy_price, asset_type FROM assets "
                "WHERE UPPER(asset_type) = 'STOCK'"
            )
            stocks: list[tuple[int, Asset]] = [
                (
                    int(row["id"]),
                    Asset(
                        name=str(row["name"]),
                        isin=str(row["isin"] or ""),
                        yahoo_ticker=str(row["yahoo_ticker"]),
                        quantity=float(row["quantity"]),
                        average_buy_price=float(row["average_buy_price"]),
                        asset_type=str(row["asset_type"]),
                    ),
                )
                for row in cursor.fetchall()
            ]
    except Exception as e:
        logger.error(f"Failed to fetch stock assets from database: {e}")
        sys.exit(1)

    if not stocks:
        logger.info("No stock assets found in database. Nothing to sync.")
        return

    logger.info(f"Starting fundamental sync for {len(stocks)} stock assets...")

    for asset_id, asset in stocks:
        try:
            logger.info(
                f"Fetching details for ticker '{asset.yahoo_ticker}' "
                f"(asset_id={asset_id})..."
            )
            details: StockDetails | None = stock_provider.get_details(asset)
            if details is None:
                logger.warning(
                    f"No fundamental details returned for ticker "
                    f"'{asset.yahoo_ticker}'."
                )
                continue

            decision_repo.save_stock_fundamentals(asset_id=asset_id, details=details)
        except Exception as e:
            logger.error(
                f"Failed to sync fundamentals for ticker "
                f"'{asset.yahoo_ticker}': {e}"
            )


def main() -> None:
    """Main CLI entry point for fundamentals management."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Stock fundamentals management and history synchronization."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser(
        "sync", help="Synchronize stock fundamentals into database."
    )
    sync_parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database file.",
    )

    args: argparse.Namespace = parser.parse_args()

    if args.command == "sync":
        sync_stock_fundamentals(db_path=args.db_path)


if __name__ == "__main__":
    main()
