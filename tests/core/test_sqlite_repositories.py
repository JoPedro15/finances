"""
Unit tests for JSON to SQLite data migration script in src/migrate_json_to_sqlite.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.repositories import SqliteHistoryRepository, SqlitePortfolioRepository
from src.migrate_json_to_sqlite import migrate_json_to_sqlite


def test_migrate_json_to_sqlite_success(tmp_path: Path) -> None:
    """Validates migrating assets and snapshots from JSON files to SQLite."""
    portfolio_json = tmp_path / "portfolio.json"
    history_json = tmp_path / "history.json"
    sqlite_db = tmp_path / "test_finances.db"

    portfolio_data = {
        "assets": [
            {
                "name": "Apple Inc.",
                "isin": "US0378331005",
                "yahoo_ticker": "AAPL",
                "quantity": 10.0,
                "averageBuyPrice": 150.0,
                "type": "stock",
            }
        ]
    }
    history_data = [
        {
            "timestamp": "2026-08-17T12:00:00",
            "total_value_eur": 1800.0,
            "assets_snapshot": [
                {
                    "name": "Apple Inc.",
                    "isin": "US0378331005",
                    "yahoo_ticker": "AAPL",
                    "native_price": 200.0,
                    "native_currency": "USD",
                    "value_eur": 1800.0,
                }
            ],
        }
    ]

    with open(portfolio_json, "w", encoding="utf-8") as f:
        json.dump(portfolio_data, f)

    with open(history_json, "w", encoding="utf-8") as f:
        json.dump(history_data, f)

    migrate_json_to_sqlite(
        portfolio_json=portfolio_json,
        history_json=history_json,
        sqlite_db=sqlite_db,
    )

    p_repo = SqlitePortfolioRepository(sqlite_db)
    h_repo = SqliteHistoryRepository(sqlite_db)

    assets = p_repo.load_assets()
    history = h_repo.load_history()

    assert len(assets) == 1
    assert assets[0].yahoo_ticker == "AAPL"
    assert len(history) == 1
    assert history[0].timestamp == "2026-08-17T12:00:00"


def test_migrate_json_to_sqlite_empty_files(tmp_path: Path) -> None:
    """Validates migration handles missing or empty JSON files gracefully."""
    portfolio_json = tmp_path / "missing_portfolio.json"
    history_json = tmp_path / "missing_history.json"
    sqlite_db = tmp_path / "test_finances.db"

    migrate_json_to_sqlite(
        portfolio_json=portfolio_json,
        history_json=history_json,
        sqlite_db=sqlite_db,
    )

    p_repo = SqlitePortfolioRepository(sqlite_db)
    h_repo = SqliteHistoryRepository(sqlite_db)

    assert len(p_repo.load_assets()) == 0
    assert len(h_repo.load_history()) == 0
