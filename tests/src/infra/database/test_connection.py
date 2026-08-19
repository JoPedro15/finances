"""Unit tests for SQLite connection and transactional context management in
src/infra/database/connection.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.infra.database.connection import get_connection, get_db_context


def test_get_connection_row_factory_and_foreign_keys(tmp_path: Path) -> None:
    """Validates get_connection sets sqlite3.Row factory and enables foreign keys."""
    db_file: Path = tmp_path / "test.db"
    conn: sqlite3.Connection = get_connection(str(db_file))

    try:
        assert conn.row_factory == sqlite3.Row
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        fk_setting: sqlite3.Row | None = cursor.fetchone()
        assert fk_setting is not None
        assert fk_setting[0] == 1
    finally:
        conn.close()


def test_get_connection_creates_parent_directory(tmp_path: Path) -> None:
    """Validates get_connection creates missing parent directories automatically."""
    nested_dir: Path = tmp_path / "nested" / "sub_dir"
    db_file: Path = nested_dir / "test.db"

    assert not nested_dir.exists()
    conn: sqlite3.Connection = get_connection(str(db_file))
    conn.close()

    assert nested_dir.exists()


def test_get_connection_default_path(tmp_path: Path) -> None:
    """Validates get_connection fallback using DEFAULT_DB_PATH when no argument
    is passed.
    """
    db_file: Path = tmp_path / "default_test.db"

    with patch("src.infra.database.connection.DEFAULT_DB_PATH", str(db_file)):
        with patch.object(get_connection, "__defaults__", (str(db_file),)):
            conn: sqlite3.Connection = get_connection()
            try:
                assert db_file.exists()
            finally:
                conn.close()


def test_get_db_context_commit_on_success(tmp_path: Path) -> None:
    """Validates get_db_context commits transactions automatically on success."""
    db_file: Path = tmp_path / "test.db"

    with get_db_context(str(db_file)) as conn:
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY);")
        conn.execute("INSERT INTO test (id) VALUES (1);")

    conn_check: sqlite3.Connection = sqlite3.connect(str(db_file))
    cursor: sqlite3.Cursor = conn_check.cursor()
    cursor.execute("SELECT COUNT(*) FROM test;")
    row: tuple[int] | None = cursor.fetchone()
    count: int = row[0] if row else 0
    conn_check.close()

    assert count == 1


def test_get_db_context_rollback_on_exception(tmp_path: Path) -> None:
    """Validates get_db_context rolls back changes when an exception is raised."""
    db_file: Path = tmp_path / "test.db"

    with get_db_context(str(db_file)) as conn:
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY);")

    with pytest.raises(RuntimeError, match="Database error simulated"):
        with get_db_context(str(db_file)) as conn:
            conn.execute("INSERT INTO test (id) VALUES (1);")
            raise RuntimeError("Database error simulated")

    conn_check: sqlite3.Connection = sqlite3.connect(str(db_file))
    cursor: sqlite3.Cursor = conn_check.cursor()
    cursor.execute("SELECT COUNT(*) FROM test;")
    row: tuple[int] | None = cursor.fetchone()
    count: int = row[0] if row else 0
    conn_check.close()

    assert count == 0
