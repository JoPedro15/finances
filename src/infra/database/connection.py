"""
SQLite database connection management and transactional context handling.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from src.config import DATA_DIR

DEFAULT_DB_PATH: Path = DATA_DIR / "finances.db"


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Establishes and returns a SQLite connection with foreign keys enabled."""
    target_path: Path = Path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn: sqlite3.Connection = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_context(
    db_path: Path | str = DEFAULT_DB_PATH,
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
