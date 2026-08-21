"""
Database schema definition and initialization DDL statements.
"""

from __future__ import annotations

import sqlite3

CREATE_ASSETS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isin TEXT UNIQUE,
    name TEXT NOT NULL,
    yahoo_ticker TEXT NOT NULL,
    quantity REAL NOT NULL,
    average_buy_price REAL NOT NULL,
    asset_type TEXT NOT NULL CHECK (UPPER(asset_type) IN ('STOCK', 'ETF')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_SNAPSHOTS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL UNIQUE,
    total_value_eur REAL NOT NULL
);
"""

CREATE_ASSET_SNAPSHOTS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS asset_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    native_price REAL NOT NULL,
    native_currency TEXT NOT NULL,
    value_eur REAL NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots (id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE
);
"""

CREATE_STOCK_FUNDAMENTALS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS stock_fundamental_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    market_cap REAL,
    pe_ratio REAL,
    forward_pe REAL,
    dividend_yield_pct REAL,
    fifty_two_week_high REAL,
    fifty_two_week_low REAL,
    sector TEXT,
    industry TEXT,
    FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE
);
"""

CREATE_ETF_FUNDAMENTALS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS etf_fundamental_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    ter_pct REAL,
    holdings_json TEXT,
    sector_breakdown_json TEXT,
    country_breakdown_json TEXT,
    FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE
);
"""

CREATE_DECISIONS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL UNIQUE,
    total_value_eur REAL NOT NULL,
    has_ai INTEGER NOT NULL
);
"""

CREATE_DECISION_ASSET_METRICS_TABLE_SQL: str = """
CREATE TABLE IF NOT EXISTS decision_asset_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    rank INTEGER NOT NULL,
    price_eur REAL NOT NULL,
    current_allocation_pct REAL NOT NULL,
    target_allocation_pct REAL NOT NULL,
    dip_score REAL NOT NULL,
    cost_score REAL NOT NULL,
    gap_score REAL NOT NULL,
    quant_score REAL NOT NULL,
    ai_action TEXT,
    ai_urgency TEXT,
    ai_confidence_pct REAL,
    forward_pe REAL,
    trailing_pe REAL,
    peg_ratio REAL,
    price_to_book REAL,
    dividend_yield_pct REAL,
    ter REAL,
    FOREIGN KEY (decision_id) REFERENCES decisions (id) ON DELETE CASCADE
);
"""


def initialize_database(conn: sqlite3.Connection) -> None:
    """Executes DDL statements to create all required database tables."""
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(CREATE_ASSETS_TABLE_SQL)
    cursor.execute(CREATE_SNAPSHOTS_TABLE_SQL)
    cursor.execute(CREATE_ASSET_SNAPSHOTS_TABLE_SQL)
    cursor.execute(CREATE_STOCK_FUNDAMENTALS_TABLE_SQL)
    cursor.execute(CREATE_ETF_FUNDAMENTALS_TABLE_SQL)
    cursor.execute(CREATE_DECISIONS_TABLE_SQL)
    cursor.execute(CREATE_DECISION_ASSET_METRICS_TABLE_SQL)
    conn.commit()
