"""Unit tests for repositories in src/core/repositories.py covering JSON and SQLite
persistence implementations, error handling, TTL caching, transactional rollbacks,
missing files, and corrupted data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import StorageReadError, StorageWriteError
from src.core.models import (
    Asset,
    AssetSnapshot,
    CountryExposure,
    ETFDetails,
    Holding,
    PortfolioSnapshot,
    SectorExposure,
)
from src.core.repositories import (
    JsonETFCacheRepository,
    JsonHistoryRepository,
    JsonPortfolioRepository,
    SqliteHistoryRepository,
    SqlitePortfolioRepository,
)


@pytest.fixture
def sample_asset() -> Asset:
    return Asset(
        name="Apple Inc.",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=10.0,
        average_buy_price=150.0,
        asset_type="stock",
    )


@pytest.fixture
def sample_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp="2026-08-17T12:00:00",
        total_value_eur=1800.0,
        assets_snapshot=[
            AssetSnapshot(
                name="Apple Inc.",
                isin="US0378331005",
                yahoo_ticker="AAPL",
                native_price=200.0,
                native_currency="USD",
                value_eur=1800.0,
            )
        ],
    )


@pytest.fixture
def sample_etf_details() -> ETFDetails:
    return ETFDetails(
        holdings=[
            Holding(
                name="Microsoft", isin="US5949181045", ticker="MSFT", weight_pct=8.0
            )
        ],
        sector_breakdown=[SectorExposure(sector_name="Technology", weight_pct=30.0)],
        country_breakdown=[
            CountryExposure(country_name="United States", weight_pct=65.0)
        ],
        ter_pct=0.07,
    )


# ==============================================================================
# SqlitePortfolioRepository Tests
# ==============================================================================


def test_sqlite_portfolio_repo_non_existent_db(tmp_path: Path) -> None:
    """Verifies load_assets returns empty list when DB file does not exist."""
    db_path: Path = tmp_path / "non_existent.db"
    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(db_path=db_path)

    assert repo.load_assets() == []


def test_sqlite_portfolio_repo_save_and_load_assets(
    tmp_path: Path, sample_asset: Asset
) -> None:
    """Verifies saving and loading assets, handling conflicts and empty ISINs."""
    db_path: Path = tmp_path / "finances_test.db"
    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(db_path=db_path)

    asset_no_isin: Asset = Asset(
        name="Custom Stock",
        isin="",
        yahoo_ticker="CUST",
        quantity=5.0,
        average_buy_price=50.0,
    )

    repo.save_assets([sample_asset, asset_no_isin])
    loaded: list[Asset] = repo.load_assets()

    assert len(loaded) == 2
    assert loaded[0].yahoo_ticker == "AAPL"
    assert loaded[1].isin == ""

    updated_asset: Asset = Asset(
        name="Apple Inc. Updated",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=15.0,
        average_buy_price=160.0,
    )
    repo.save_assets([updated_asset])
    reloaded: list[Asset] = repo.load_assets()

    assert len(reloaded) == 2
    aapl: Asset = next(a for a in reloaded if a.isin == "US0378331005")
    assert aapl.quantity == 15.0
    assert aapl.name == "Apple Inc. Updated"


@patch("src.core.repositories.get_db_context")
def test_sqlite_portfolio_repo_load_exception(
    mock_db_context: MagicMock, tmp_path: Path
) -> None:
    """Verifies StorageReadError is raised when DB access fails during load_assets."""
    db_path: Path = tmp_path / "finances_test.db"
    db_path.touch()
    mock_db_context.side_effect = Exception("Database connection error")

    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(db_path=db_path)

    with pytest.raises(StorageReadError):
        repo.load_assets()


@patch("src.core.repositories.get_db_context")
def test_sqlite_portfolio_repo_save_exception(
    mock_db_context: MagicMock, tmp_path: Path, sample_asset: Asset
) -> None:
    """Verifies StorageWriteError is raised when DB access fails during save_assets."""
    db_path: Path = tmp_path / "finances_test.db"
    mock_db_context.side_effect = Exception("Disk write error")

    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(db_path=db_path)

    with pytest.raises(StorageWriteError):
        repo.save_assets([sample_asset])


@patch("src.core.repositories.get_db_context")
def test_sqlite_portfolio_repo_context_rollback_error(
    mock_db_context: MagicMock, tmp_path: Path
) -> None:
    """Validates StorageWriteError handling during transactional rollback failures."""
    db_path: Path = tmp_path / "finances.db"
    mock_context: MagicMock = MagicMock()
    mock_context.__enter__.side_effect = Exception("Transaction deadlock")
    mock_db_context.return_value = mock_context

    repo: SqlitePortfolioRepository = SqlitePortfolioRepository(db_path=db_path)

    with pytest.raises(StorageWriteError):
        repo.save_assets([])


# ==============================================================================
# SqliteHistoryRepository Tests
# ==============================================================================


def test_sqlite_history_repo_non_existent_db(tmp_path: Path) -> None:
    """Verifies load_history returns empty list when DB file does not exist."""
    db_path: Path = tmp_path / "non_existent.db"
    repo: SqliteHistoryRepository = SqliteHistoryRepository(db_path=db_path)

    assert repo.load_history() == []


def test_sqlite_history_repo_save_and_load_history(
    tmp_path: Path, sample_snapshot: PortfolioSnapshot
) -> None:
    """Verifies saving and loading portfolio snapshots in SQLite database."""
    db_path: Path = tmp_path / "finances_test.db"
    repo: SqliteHistoryRepository = SqliteHistoryRepository(db_path=db_path)

    repo.save_snapshot(sample_snapshot)
    history: list[PortfolioSnapshot] = repo.load_history()

    assert len(history) == 1
    assert history[0].timestamp == sample_snapshot.timestamp
    assert history[0].total_value_eur == 1800.0
    assert len(history[0].assets_snapshot) == 1
    assert history[0].assets_snapshot[0].yahoo_ticker == "AAPL"

    snapshot2: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-17T13:00:00",
        total_value_eur=1900.0,
        assets_snapshot=sample_snapshot.assets_snapshot,
    )
    repo.save_snapshot(snapshot2)
    history2: list[PortfolioSnapshot] = repo.load_history()

    assert len(history2) == 2


@patch("src.core.repositories.get_db_context")
def test_sqlite_history_repo_load_exception(
    mock_db_context: MagicMock, tmp_path: Path
) -> None:
    """Verifies StorageReadError is raised when DB load fails."""
    db_path: Path = tmp_path / "finances_test.db"
    db_path.touch()
    mock_db_context.side_effect = Exception("Read failure")

    repo: SqliteHistoryRepository = SqliteHistoryRepository(db_path=db_path)

    with pytest.raises(StorageReadError):
        repo.load_history()


@patch("src.core.repositories.get_db_context")
def test_sqlite_history_repo_save_exception(
    mock_db_context: MagicMock, tmp_path: Path, sample_snapshot: PortfolioSnapshot
) -> None:
    """Verifies StorageWriteError is raised when DB save fails."""
    db_path: Path = tmp_path / "finances_test.db"
    mock_db_context.side_effect = Exception("Write failure")

    repo: SqliteHistoryRepository = SqliteHistoryRepository(db_path=db_path)

    with pytest.raises(StorageWriteError):
        repo.save_snapshot(sample_snapshot)


@patch("src.core.repositories.get_db_context")
def test_sqlite_history_repo_rollback_error(
    mock_db_context: MagicMock, tmp_path: Path
) -> None:
    """Validates StorageReadError handling during history retrieval database errors."""
    db_path: Path = tmp_path / "finances.db"
    db_path.touch()
    mock_context: MagicMock = MagicMock()
    mock_context.__enter__.side_effect = Exception("Database locked")
    mock_db_context.return_value = mock_context

    repo: SqliteHistoryRepository = SqliteHistoryRepository(db_path=db_path)

    with pytest.raises(StorageReadError):
        repo.load_history()


# ==============================================================================
# JsonPortfolioRepository Tests
# ==============================================================================


def test_json_portfolio_repo_missing_file(tmp_path: Path) -> None:
    """Verifies JsonPortfolioRepository raises StorageReadError when file is missing."""
    file_path: Path = tmp_path / "portfolio.json"
    repo: JsonPortfolioRepository = JsonPortfolioRepository(file_path=file_path)

    with pytest.raises(StorageReadError):
        repo.load_assets()


def test_json_portfolio_repo_corrupted_json(tmp_path: Path) -> None:
    """Verifies JsonPortfolioRepository raises StorageReadError on invalid JSON."""
    file_path: Path = tmp_path / "portfolio.json"
    file_path.write_text("{ corrupted json ...", encoding="utf-8")

    repo: JsonPortfolioRepository = JsonPortfolioRepository(file_path=file_path)

    with pytest.raises(StorageReadError):
        repo.load_assets()


def test_json_portfolio_repo_success(tmp_path: Path) -> None:
    """Verifies JsonPortfolioRepository correctly loads assets from valid JSON."""
    file_path: Path = tmp_path / "portfolio.json"
    data: dict[str, list[dict[str, object]]] = {
        "assets": [
            {
                "name": "Apple",
                "isin": "US0378331005",
                "yahoo_ticker": "AAPL",
                "quantity": 10.0,
                "averageBuyPrice": 150.0,
            }
        ]
    }
    file_path.write_text(json.dumps(data), encoding="utf-8")

    repo: JsonPortfolioRepository = JsonPortfolioRepository(file_path=file_path)
    assets: list[Asset] = repo.load_assets()

    assert len(assets) == 1
    assert assets[0].name == "Apple"


# ==============================================================================
# JsonHistoryRepository Tests
# ==============================================================================


def test_json_history_repo_missing_file(tmp_path: Path) -> None:
    """Verifies JsonHistoryRepository returns empty list when file is missing."""
    file_path: Path = tmp_path / "history.json"
    repo: JsonHistoryRepository = JsonHistoryRepository(file_path=file_path)

    assert repo.load_history() == []


def test_json_history_repo_corrupted_json(tmp_path: Path) -> None:
    """Verifies JsonHistoryRepository raises StorageReadError on corrupted file."""
    file_path: Path = tmp_path / "history.json"
    file_path.write_text("{ corrupted json ...", encoding="utf-8")

    repo: JsonHistoryRepository = JsonHistoryRepository(file_path=file_path)

    with pytest.raises(StorageReadError):
        repo.load_history()


def test_json_history_repo_save_and_load_success(
    tmp_path: Path, sample_snapshot: PortfolioSnapshot
) -> None:
    """Verifies JsonHistoryRepository appends snapshots and loads them correctly."""
    file_path: Path = tmp_path / "history.json"
    repo: JsonHistoryRepository = JsonHistoryRepository(file_path=file_path)

    repo.save_snapshot(sample_snapshot)
    history: list[PortfolioSnapshot] = repo.load_history()

    assert len(history) == 1
    assert history[0].timestamp == sample_snapshot.timestamp


def test_json_history_repo_save_write_error(
    tmp_path: Path, sample_snapshot: PortfolioSnapshot
) -> None:
    """Verifies JsonHistoryRepository raises StorageWriteError when writing fails."""
    blocker: Path = tmp_path / "blocked_folder"
    blocker.write_text("file_blocking_dir")
    file_path: Path = blocker / "history.json"

    repo: JsonHistoryRepository = JsonHistoryRepository(file_path=file_path)

    with pytest.raises(StorageWriteError):
        repo.save_snapshot(sample_snapshot)


# ==============================================================================
# JsonETFCacheRepository Tests
# ==============================================================================


def test_get_etf_details_missing_file(tmp_path: Path) -> None:
    """Verifies get_etf_details returns None when cache file does not exist."""
    cache_file: Path = tmp_path / "etf_cache.json"
    repo: JsonETFCacheRepository = JsonETFCacheRepository(file_path=cache_file)

    assert repo.get_etf_details("IE00B4L5Y983") is None


def test_save_and_get_etf_details_success(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    """Verifies saving and retrieving valid unexpired ETF details in cache."""
    cache_file: Path = tmp_path / "etf_cache.json"
    repo: JsonETFCacheRepository = JsonETFCacheRepository(
        file_path=cache_file, ttl_days=30
    )

    repo.save_etf_details("IE00B4L5Y983", sample_etf_details)
    retrieved: ETFDetails | None = repo.get_etf_details("IE00B4L5Y983")

    assert retrieved is not None
    assert retrieved.ter_pct == 0.07
    assert len(retrieved.holdings) == 1
    assert retrieved.holdings[0].name == "Microsoft"


def test_get_etf_details_ttl_expired(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    """Verifies get_etf_details returns None when cached entry exceeds TTL."""
    cache_file: Path = tmp_path / "etf_cache.json"
    repo: JsonETFCacheRepository = JsonETFCacheRepository(
        file_path=cache_file, ttl_days=30
    )

    old_timestamp: str = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    raw_data: dict[str, dict[str, object]] = {
        "IE00B4L5Y983": {
            "cached_at": old_timestamp,
            "details": sample_etf_details.to_dict(),
        }
    }
    cache_file.write_text(json.dumps(raw_data), encoding="utf-8")

    assert repo.get_etf_details("IE00B4L5Y983") is None


def test_get_etf_details_naive_timestamp(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    """Verifies naive ISO timestamps (without tz offset) are handled correctly."""
    cache_file: Path = tmp_path / "etf_cache.json"
    repo: JsonETFCacheRepository = JsonETFCacheRepository(
        file_path=cache_file, ttl_days=30
    )

    naive_ts: str = datetime.now().isoformat()
    raw_data: dict[str, dict[str, object]] = {
        "IE00B4L5Y983": {
            "cached_at": naive_ts,
            "details": sample_etf_details.to_dict(),
        }
    }
    cache_file.write_text(json.dumps(raw_data), encoding="utf-8")

    assert repo.get_etf_details("IE00B4L5Y983") is not None


def test_get_etf_details_malformed_entries(tmp_path: Path) -> None:
    """Verifies get_etf_details returns None for invalid or missing fields."""
    cache_file: Path = tmp_path / "etf_cache.json"
    raw_data: dict[str, object] = {
        "NOT_A_DICT": "invalid",
        "MISSING_FIELDS": {"cached_at": datetime.now(UTC).isoformat()},
        "INVALID_DETAILS": {
            "cached_at": datetime.now(UTC).isoformat(),
            "details": "not_a_dict_details",
        },
    }
    cache_file.write_text(json.dumps(raw_data), encoding="utf-8")

    repo: JsonETFCacheRepository = JsonETFCacheRepository(file_path=cache_file)

    assert repo.get_etf_details("NOT_A_DICT") is None
    assert repo.get_etf_details("MISSING_FIELDS") is None
    assert repo.get_etf_details("INVALID_DETAILS") is None


def test_get_etf_details_corrupted_json(tmp_path: Path) -> None:
    """Verifies get_etf_details handles corrupted JSON files gracefully."""
    cache_file: Path = tmp_path / "etf_cache.json"
    cache_file.write_text("{ invalid json content ...", encoding="utf-8")

    repo: JsonETFCacheRepository = JsonETFCacheRepository(file_path=cache_file)

    assert repo.get_etf_details("IE00B4L5Y983") is None


def test_save_etf_details_recovers_from_corrupted_existing_file(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    """Verifies save_etf_details overwrites corrupted JSON cache cleanly."""
    cache_file: Path = tmp_path / "etf_cache.json"
    cache_file.write_text("{ corrupted json ...", encoding="utf-8")

    repo: JsonETFCacheRepository = JsonETFCacheRepository(file_path=cache_file)
    repo.save_etf_details("IE00B4L5Y983", sample_etf_details)

    retrieved: ETFDetails | None = repo.get_etf_details("IE00B4L5Y983")
    assert retrieved is not None


def test_save_etf_details_write_error(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    """Verifies StorageWriteError is raised when writing ETF cache fails."""
    invalid_path: Path = tmp_path / "non_existent_folder" / "sub" / "cache.json"
    repo: JsonETFCacheRepository = JsonETFCacheRepository(file_path=invalid_path)

    (tmp_path / "non_existent_folder").write_text("file_blocking_dir")

    with pytest.raises(StorageWriteError):
        repo.save_etf_details("IE00B4L5Y983", sample_etf_details)


def test_json_etf_cache_repo_directory_creation_error(tmp_path: Path) -> None:
    """Validates StorageWriteError when cache parent directory cannot be created."""
    blocked_path: Path = tmp_path / "blocked_file"
    blocked_path.touch()

    invalid_cache_file: Path = blocked_path / "cache.json"
    repo: JsonETFCacheRepository = JsonETFCacheRepository(file_path=invalid_cache_file)

    mock_details: MagicMock = MagicMock()
    mock_details.to_dict.return_value = {}

    with pytest.raises(StorageWriteError):
        repo.save_etf_details("IE00B4L5Y983", mock_details)
