"""
Unit tests for ETF cache repository in src/core/repositories.py.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.core.exceptions import StorageWriteError
from src.core.models import CountryExposure, ETFDetails, Holding, SectorExposure
from src.core.repositories import JsonETFCacheRepository


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


def test_get_etf_details_missing_file(tmp_path: Path) -> None:
    cache_file = tmp_path / "etf_cache.json"
    repo = JsonETFCacheRepository(file_path=cache_file)

    assert repo.get_etf_details("IE00B4L5Y983") is None


def test_save_and_get_etf_details_success(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    cache_file = tmp_path / "etf_cache.json"
    repo = JsonETFCacheRepository(file_path=cache_file, ttl_days=30)

    repo.save_etf_details("IE00B4L5Y983", sample_etf_details)
    retrieved = repo.get_etf_details("IE00B4L5Y983")

    assert retrieved is not None
    assert retrieved.ter_pct == 0.07
    assert len(retrieved.holdings) == 1
    assert retrieved.holdings[0].name == "Microsoft"


def test_get_etf_details_ttl_expired(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    cache_file = tmp_path / "etf_cache.json"
    repo = JsonETFCacheRepository(file_path=cache_file, ttl_days=30)

    old_timestamp = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    raw_data = {
        "IE00B4L5Y983": {
            "cached_at": old_timestamp,
            "details": sample_etf_details.to_dict(),
        }
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(raw_data, f)

    assert repo.get_etf_details("IE00B4L5Y983") is None


def test_get_etf_details_corrupted_json(tmp_path: Path) -> None:
    cache_file = tmp_path / "etf_cache.json"
    cache_file.write_text("{ invalid json content ...")

    repo = JsonETFCacheRepository(file_path=cache_file)
    assert repo.get_etf_details("IE00B4L5Y983") is None


def test_save_etf_details_write_error(
    tmp_path: Path, sample_etf_details: ETFDetails
) -> None:
    invalid_path = tmp_path / "non_existent_folder" / "sub" / "cache.json"
    repo = JsonETFCacheRepository(file_path=invalid_path)

    (tmp_path / "non_existent_folder").write_text("file_blocking_dir")

    with pytest.raises(StorageWriteError):
        repo.save_etf_details("IE00B4L5Y983", sample_etf_details)
