"""
SQLite database connection management and transactional context handling.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

DEFAULT_DB_PATH: str = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../..", "data", "finances.db")
)


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Establishes and returns a SQLite connection with foreign keys enabled."""
    db_dir: str = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_dir, exist_ok=True)

    conn: sqlite3.Connection = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_context(
    db_path: str = DEFAULT_DB_PATH,
) -> Generator[sqlite3.Connection]:
    """Context manager providing transactional SQLite connection handling."""
    conn: sqlite3.Connection = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
