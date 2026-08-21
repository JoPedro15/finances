"""Unit tests for stock fundamental repository persistence and CLI sync logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.fundamentals import sync_stock_fundamentals
from src.core.models import Asset, StockDetails
from src.core.repositories import SqliteDecisionRepository
from src.infra.database.connection import get_db_context
from src.infra.database.schema import initialize_database


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Fixture providing an initialized temporary SQLite database path."""
    db_file: Path = tmp_path / "test_finances.db"
    with get_db_context(str(db_file)) as conn:
        initialize_database(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO assets (
                id, isin, name, yahoo_ticker, quantity,
                average_buy_price, asset_type
            ) VALUES (1, 'US0378331005', 'Apple Inc.', 'AAPL', 10.0, 150.0, 'STOCK');
            """)
        conn.commit()
    return db_file


def test_save_stock_fundamentals_success(temp_db_path: Path) -> None:
    """Tests persisting stock fundamental details into SQLite database."""
    repo: SqliteDecisionRepository = SqliteDecisionRepository(db_path=temp_db_path)
    details: StockDetails = StockDetails(
        market_cap=2_500_000_000_000.0,
        pe_ratio=30.5,
        forward_pe=28.0,
        dividend_yield_pct=0.5,
        fifty_two_week_high=200.0,
        fifty_two_week_low=150.0,
        sector="Technology",
        industry="Consumer Electronics",
    )

    repo.save_stock_fundamentals(asset_id=1, details=details)

    with get_db_context(str(temp_db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT asset_id, market_cap, sector FROM stock_fundamental_history "
            "WHERE asset_id = 1"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["asset_id"] == 1
        assert row["market_cap"] == 2_500_000_000_000.0
        assert row["sector"] == "Technology"


@patch("src.cli.fundamentals.StockProvider")
def test_sync_stock_fundamentals_cli(
    mock_provider_cls: MagicMock, temp_db_path: Path
) -> None:
    """Tests the sync_stock_fundamentals CLI execution workflow."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.get_details.return_value = StockDetails(
        market_cap=2_500_000_000_000.0,
        pe_ratio=30.5,
        forward_pe=28.0,
        dividend_yield_pct=0.5,
        fifty_two_week_high=200.0,
        fifty_two_week_low=150.0,
        sector="Technology",
        industry="Consumer Electronics",
    )

    sync_stock_fundamentals(db_path=temp_db_path)

    mock_provider.get_details.assert_called_once()
    call_arg: Asset = mock_provider.get_details.call_args[0][0]
    assert call_arg.yahoo_ticker == "AAPL"
