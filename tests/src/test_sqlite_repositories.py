"""
Unit tests for JSON to SQLite data migration script in src/migrate_json_to_sqlite.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.models import PortfolioSnapshot
from src.core.repositories import SqliteHistoryRepository, SqlitePortfolioRepository
from src.migrate_json_to_sqlite import migrate_json_to_sqlite


def test_migrate_json_to_sqlite_success(tmp_path: Path) -> None:
    """Validates migrating assets and snapshots from JSON
    files to SQLite."""
    portfolio_json: Path = tmp_path / "portfolio.json"
    history_json: Path = tmp_path / "history.json"
    sqlite_db: Path = tmp_path / "test_finances.db"

    portfolio_data: dict[str, list[dict[str, object]]] = {
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
    history_data: list[dict[str, object]] = [
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

    p_repo: SqlitePortfolioRepository = SqlitePortfolioRepository(sqlite_db)
    h_repo: SqliteHistoryRepository = SqliteHistoryRepository(sqlite_db)

    assets = p_repo.load_assets()
    history = h_repo.load_history()

    assert len(assets) == 1
    assert assets[0].yahoo_ticker == "AAPL"
    assert len(history) == 1
    assert history[0].timestamp == "2026-08-17T12:00:00"


def test_migrate_json_to_sqlite_empty_files(tmp_path: Path) -> None:
    """Validates migration handles missing or empty JSON
    files gracefully."""
    portfolio_json: Path = tmp_path / "missing_portfolio.json"
    history_json: Path = tmp_path / "missing_history.json"
    sqlite_db: Path = tmp_path / "test_finances.db"

    migrate_json_to_sqlite(
        portfolio_json=portfolio_json,
        history_json=history_json,
        sqlite_db=sqlite_db,
    )

    p_repo: SqlitePortfolioRepository = SqlitePortfolioRepository(sqlite_db)
    h_repo: SqliteHistoryRepository = SqliteHistoryRepository(sqlite_db)

    assert len(p_repo.load_assets()) == 0
    assert len(h_repo.load_history()) == 0


def test_migrate_json_to_sqlite_skip_existing_snapshots(tmp_path: Path) -> None:
    """Validates that existing snapshots in SQLite are skipped
    to prevent duplicate insertion."""
    portfolio_json: Path = tmp_path / "portfolio.json"
    history_json: Path = tmp_path / "history.json"
    sqlite_db: Path = tmp_path / "test_finances.db"

    portfolio_json.write_text('{"assets": []}', encoding="utf-8")

    existing_snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-17T12:00:00",
        total_value_eur=1000.0,
        assets_snapshot=[],
    )
    h_repo: SqliteHistoryRepository = SqliteHistoryRepository(sqlite_db)
    h_repo.save_snapshot(existing_snapshot)

    history_data: list[dict[str, object]] = [
        {
            "timestamp": "2026-08-17T12:00:00",
            "total_value_eur": 1000.0,
            "assets_snapshot": [],
        },
        {
            "timestamp": "2026-08-18T12:00:00",
            "total_value_eur": 1200.0,
            "assets_snapshot": [],
        },
    ]
    history_json.write_text(json.dumps(history_data), encoding="utf-8")

    migrate_json_to_sqlite(
        portfolio_json=portfolio_json,
        history_json=history_json,
        sqlite_db=sqlite_db,
    )

    history: list[PortfolioSnapshot] = h_repo.load_history()
    assert len(history) == 2
    timestamps: set[str] = {s.timestamp for s in history}
    assert timestamps == {"2026-08-17T12:00:00", "2026-08-18T12:00:00"}


def test_migrate_json_to_sqlite_handles_portfolio_exception(tmp_path: Path) -> None:
    """Validates graceful handling when portfolio JSON loading
    or saving raises an exception."""
    portfolio_json: Path = tmp_path / "corrupted_portfolio.json"
    history_json: Path = tmp_path / "history.json"
    sqlite_db: Path = tmp_path / "test_finances.db"

    portfolio_json.write_text("{invalid_json", encoding="utf-8")
    history_json.write_text("[]", encoding="utf-8")

    migrate_json_to_sqlite(
        portfolio_json=portfolio_json,
        history_json=history_json,
        sqlite_db=sqlite_db,
    )

    p_repo: SqlitePortfolioRepository = SqlitePortfolioRepository(sqlite_db)
    assert len(p_repo.load_assets()) == 0


def test_migrate_json_to_sqlite_handles_history_exception(tmp_path: Path) -> None:
    """Validates graceful handling when history JSON loading
    or saving raises an exception."""
    portfolio_json: Path = tmp_path / "portfolio.json"
    history_json: Path = tmp_path / "corrupted_history.json"
    sqlite_db: Path = tmp_path / "test_finances.db"

    portfolio_json.write_text('{"assets": []}', encoding="utf-8")
    history_json.write_text("{invalid_json", encoding="utf-8")

    migrate_json_to_sqlite(
        portfolio_json=portfolio_json,
        history_json=history_json,
        sqlite_db=sqlite_db,
    )

    h_repo: SqliteHistoryRepository = SqliteHistoryRepository(sqlite_db)
    assert len(h_repo.load_history()) == 0


@patch("src.migrate_json_to_sqlite.JsonPortfolioRepository")
@patch("src.migrate_json_to_sqlite.JsonHistoryRepository")
def test_migrate_json_to_sqlite_default_args(
    mock_json_h: MagicMock, mock_json_p: MagicMock, tmp_path: Path
) -> None:
    """Validates execution using default file paths when no
    custom arguments are provided."""
    mock_json_p.return_value.load_assets.return_value = []
    mock_json_h.return_value.load_history.return_value = []

    sqlite_db: Path = tmp_path / "default_test.db"

    migrate_json_to_sqlite(sqlite_db=sqlite_db)

    mock_json_p.assert_called_once_with(Path("data/portfolio.json"))
    mock_json_h.assert_called_once_with(Path("data/history.json"))
