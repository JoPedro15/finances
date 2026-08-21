"""Unit tests for stock and ETF fundamental repository and CLI sync logic."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.fundamentals import (
    sync_etf_fundamentals,
    sync_portfolio_fundamentals,
    sync_stock_fundamentals,
)
from src.core.models import (
    Asset,
    CountryExposure,
    ETFDetails,
    Holding,
    SectorExposure,
    StockDetails,
)
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
            ) VALUES
            (1, 'US0378331005', 'Apple Inc.', 'AAPL', 10.0, 150.0, 'STOCK'),
            (2, 'IE00BK5BQT36', 'Vanguard All-World', 'VWCE.DE', 5.0, 100.0, 'ETF');
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
            "SELECT asset_id, market_cap, sector "
            "FROM stock_fundamental_history WHERE asset_id = 1"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["asset_id"] == 1
        assert row["market_cap"] == 2_500_000_000_000.0
        assert row["sector"] == "Technology"


def test_save_etf_fundamentals_success(temp_db_path: Path) -> None:
    """Tests persisting ETF fundamental details into SQLite database."""
    repo: SqliteDecisionRepository = SqliteDecisionRepository(db_path=temp_db_path)
    details: ETFDetails = ETFDetails(
        ter_pct=0.22,
        holdings=[
            Holding(
                name="Microsoft Corp",
                isin="US5949181045",
                ticker="MSFT",
                weight_pct=4.5,
            )
        ],
        sector_breakdown=[
            SectorExposure(
                sector_name="Technology",
                weight_pct=25.0,
            )
        ],
        country_breakdown=[
            CountryExposure(
                country_name="United States",
                weight_pct=60.0,
            )
        ],
    )

    repo.save_etf_fundamentals(asset_id=2, details=details)

    with get_db_context(str(temp_db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT asset_id, ter_pct, holdings_json "
            "FROM etf_fundamental_history WHERE asset_id = 2"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["asset_id"] == 2
        assert row["ter_pct"] == 0.22
        holdings = json.loads(row["holdings_json"])
        assert len(holdings) == 1
        assert holdings[0]["name"] == "Microsoft Corp"


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


@patch("src.cli.fundamentals.ETFProvider")
def test_sync_etf_fundamentals_cli(
    mock_provider_cls: MagicMock, temp_db_path: Path
) -> None:
    """Tests the sync_etf_fundamentals CLI execution workflow."""
    mock_provider: MagicMock = MagicMock()
    mock_provider_cls.return_value = mock_provider
    mock_provider.get_details.return_value = ETFDetails(
        ter_pct=0.22,
        holdings=[],
        sector_breakdown=[],
        country_breakdown=[],
    )

    sync_etf_fundamentals(db_path=temp_db_path)

    mock_provider.get_details.assert_called_once()
    call_arg: Asset = mock_provider.get_details.call_args[0][0]
    assert call_arg.isin == "IE00BK5BQT36"


@patch("src.cli.fundamentals.ETFProvider")
@patch("src.cli.fundamentals.StockProvider")
def test_sync_portfolio_fundamentals_cli(
    mock_stock_cls: MagicMock,
    mock_etf_cls: MagicMock,
    temp_db_path: Path,
) -> None:
    """Tests full portfolio fundamentals sync (stocks and ETFs)."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_stock_cls.return_value = mock_stock_provider
    mock_stock_provider.get_details.return_value = StockDetails(
        market_cap=1.0,
        pe_ratio=1.0,
        forward_pe=1.0,
        dividend_yield_pct=0.0,
        fifty_two_week_high=1.0,
        fifty_two_week_low=1.0,
        sector="Tech",
        industry="Tech",
    )

    mock_etf_provider: MagicMock = MagicMock()
    mock_etf_cls.return_value = mock_etf_provider
    mock_etf_provider.get_details.return_value = ETFDetails(
        ter_pct=0.2,
        holdings=[],
        sector_breakdown=[],
        country_breakdown=[],
    )

    sync_portfolio_fundamentals(db_path=temp_db_path)

    mock_stock_provider.get_details.assert_called_once()
    mock_etf_provider.get_details.assert_called_once()
