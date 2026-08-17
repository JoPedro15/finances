"""
Unit tests for SQLite schema initialization in src/infra/database/schema.py.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.infra.database.connection import get_connection
from src.infra.database.schema import initialize_database


def test_initialize_database_creates_all_tables() -> None:
    """Validates initialize_database creates all required relational tables."""
    conn: sqlite3.Connection = get_connection(":memory:")
    initialize_database(conn)

    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%';"
    )
    tables: set[str] = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected_tables: set[str] = {
        "assets",
        "snapshots",
        "asset_snapshots",
        "stock_fundamental_history",
    }
    assert expected_tables.issubset(tables)


def test_initialize_database_idempotency() -> None:
    """Validates calling initialize_database multiple times does not fail."""
    conn: sqlite3.Connection = get_connection(":memory:")
    initialize_database(conn)
    initialize_database(conn)

    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
    row: tuple[int] | None = cursor.fetchone()
    count: int = row[0] if row else 0
    conn.close()

    assert count >= 4


def test_assets_table_check_constraint() -> None:
    """Validates asset_type check constraint in assets table."""
    conn: sqlite3.Connection = get_connection(":memory:")
    initialize_database(conn)

    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO assets (name, yahoo_ticker, quantity, "
        "average_buy_price, asset_type) "
        "VALUES ('Valid Stock', 'AAPL', 1.0, 100.0, 'stock');"
    )

    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            "INSERT INTO assets (name, yahoo_ticker, quantity, "
            "average_buy_price, asset_type) "
            "VALUES ('Invalid Asset', 'BAD', 1.0, 100.0, 'invalid_type');"
        )

    conn.close()


def test_foreign_key_cascade_delete() -> None:
    """Validates cascade deletion from snapshots to asset_snapshots."""
    conn: sqlite3.Connection = get_connection(":memory:")
    initialize_database(conn)

    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO assets (name, yahoo_ticker, quantity, "
        "average_buy_price, asset_type) "
        "VALUES ('Apple', 'AAPL', 1.0, 100.0, 'stock');"
    )
    asset_id: int = cursor.lastrowid or 0

    cursor.execute(
        "INSERT INTO snapshots (timestamp, total_value_eur) "
        "VALUES ('2026-08-17T12:00:00', 100.0);"
    )
    snapshot_id: int = cursor.lastrowid or 0

    cursor.execute(
        "INSERT INTO asset_snapshots (snapshot_id, asset_id, native_price, "
        "native_currency, value_eur) VALUES (?, ?, 100.0, 'USD', 90.0);",
        (snapshot_id, asset_id),
    )

    cursor.execute(
        "SELECT COUNT(*) FROM asset_snapshots WHERE snapshot_id = ?;",
        (snapshot_id,),
    )
    row: tuple[int] | None = cursor.fetchone()
    assert (row[0] if row else 0) == 1

    cursor.execute("DELETE FROM snapshots WHERE id = ?;", (snapshot_id,))

    cursor.execute(
        "SELECT COUNT(*) FROM asset_snapshots WHERE snapshot_id = ?;",
        (snapshot_id,),
    )
    row_after: tuple[int] | None = cursor.fetchone()
    assert (row_after[0] if row_after else 0) == 0

    conn.close()
