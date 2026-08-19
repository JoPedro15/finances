"""Unit tests for src/cli/recommend.py covering JSON parsing, live
allocation calculations, target asset enrichment, CLI execution orchestration,
and main module entry point.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.cli.recommend import (
    calculate_current_allocations,
    enrich_target_asset,
    load_json_data,
    run_decision_cli,
)
from src.core.models import ETFDetails, Quotation, StockDetails


def test_load_json_data_missing_file(tmp_path: Path) -> None:
    """Validates load_json_data returns an empty list when file does not exist."""
    missing_file: Path = tmp_path / "missing.json"
    assert load_json_data(missing_file) == []


def test_load_json_data_list_format(tmp_path: Path) -> None:
    """Validates load_json_data parses a JSON array of dictionaries."""
    file_path: Path = tmp_path / "list.json"
    file_path.write_text('[{"symbol": "AAPL"}, "invalid", 123]', encoding="utf-8")
    result: list[dict[str, Any]] = load_json_data(file_path)
    assert len(result) == 1
    assert result[0] == {"symbol": "AAPL"}


def test_load_json_data_dict_format(tmp_path: Path) -> None:
    """Validates load_json_data parses a JSON object with 'assets' key."""
    file_path: Path = tmp_path / "dict.json"
    file_path.write_text('{"assets": [{"symbol": "MSFT"}]}', encoding="utf-8")
    result: list[dict[str, Any]] = load_json_data(file_path)
    assert len(result) == 1
    assert result[0] == {"symbol": "MSFT"}


def test_load_json_data_invalid_structure(tmp_path: Path) -> None:
    """Validates load_json_data returns an empty list for unexpected JSON roots."""
    file_path: Path = tmp_path / "invalid_root.json"
    file_path.write_text('"just a string"', encoding="utf-8")
    assert load_json_data(file_path) == []


def test_calculate_current_allocations_success() -> None:
    """Validates calculate_current_allocations computes portfolio % allocations."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_stock_provider.get_price.side_effect = [
        Quotation(price=100.0, currency="EUR"),
        Quotation(price=200.0, currency="EUR"),
    ]

    portfolio_items: list[dict[str, Any]] = [
        {"yahoo_ticker": "AAPL", "quantity": 2.0, "isin": "US0378331005"},
        {"symbol": "MSFT", "quantity": 4.0, "isin": "US5949181045"},
        {"symbol": "", "quantity": 10.0},
        {"symbol": "GOOGL", "quantity": 0.0},
    ]

    alloc_map: dict[str, float]
    total_val: float
    alloc_map, total_val = calculate_current_allocations(
        portfolio_items, mock_stock_provider
    )

    assert total_val == 1000.0
    assert alloc_map["AAPL"] == 20.0
    assert alloc_map["MSFT"] == 80.0


def test_calculate_current_allocations_zero_total_value() -> None:
    """Validates calculate_current_allocations returns empty map when value is 0."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_stock_provider.get_price.return_value = None

    portfolio_items: list[dict[str, Any]] = [{"yahoo_ticker": "AAPL", "quantity": 2.0}]

    alloc_map: dict[str, float]
    total_val: float
    alloc_map, total_val = calculate_current_allocations(
        portfolio_items, mock_stock_provider
    )

    assert total_val == 0.0
    assert alloc_map == {}


def test_enrich_target_asset_stock_success() -> None:
    """Validates enrich_target_asset enriches stock wishlist items with market data."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    mock_stock_provider.get_price.return_value = Quotation(price=150.0, currency="USD")
    mock_stock_provider.get_details.return_value = StockDetails(
        sector="Tech",
        industry="Hardware",
        market_cap=2e12,
        pe_ratio=25.0,
        forward_pe=20.0,
        dividend_yield_pct=0.5,
        fifty_two_week_high=200.0,
        fifty_two_week_low=120.0,
    )

    target: dict[str, Any] = {
        "yahoo_ticker": "AAPL",
        "type": "STOCK",
        "target_allocation_pct": 10.0,
    }

    enriched: dict[str, Any] = enrich_target_asset(
        target,
        current_alloc_pct=5.0,
        stock_provider=mock_stock_provider,
        etf_provider=mock_etf_provider,
    )

    assert enriched["symbol"] == "AAPL"
    assert enriched["asset_type"] == "STOCK"
    assert enriched["current_price"] == 150.0
    assert enriched["peak_price"] == 200.0
    assert enriched["low_52w"] == 120.0
    assert enriched["trailing_pe"] == 25.0
    assert enriched["forward_pe"] == 20.0
    assert enriched["current_allocation_pct"] == 5.0


def test_enrich_target_asset_stock_no_52w_high_fallback() -> None:
    """Validates peak_price falls back to current_price if 52w high is missing."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    mock_stock_provider.get_price.return_value = Quotation(price=100.0, currency="EUR")
    mock_stock_provider.get_details.return_value = StockDetails(
        sector=None,
        industry=None,
        market_cap=None,
        pe_ratio=None,
        forward_pe=None,
        dividend_yield_pct=None,
        fifty_two_week_high=None,
        fifty_two_week_low=None,
    )

    target: dict[str, Any] = {"symbol": "XYZ", "asset_type": "STOCK"}
    enriched: dict[str, Any] = enrich_target_asset(
        target, 0.0, mock_stock_provider, mock_etf_provider
    )

    assert enriched["peak_price"] == 100.0


def test_enrich_target_asset_etf_with_direct_ter() -> None:
    """Validates enrich_target_asset extracts TER directly from ETF details."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    mock_stock_provider.get_price.return_value = Quotation(price=90.0, currency="EUR")
    mock_stock_provider.get_details.return_value = None
    mock_etf_provider.get_details.return_value = ETFDetails(
        holdings=[], sector_breakdown=[], country_breakdown=[], ter_pct=0.15
    )

    target: dict[str, Any] = {"symbol": "EUNL.DE", "asset_type": "ETF"}

    enriched: dict[str, Any] = enrich_target_asset(
        target, 0.0, mock_stock_provider, mock_etf_provider
    )

    assert enriched["ter"] == 0.15


def test_enrich_target_asset_etf_with_ter_fallback() -> None:
    """Validates enrich_target_asset falls back to target dict TER when details
    TER is None.
    """
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    mock_stock_provider.get_price.return_value = Quotation(price=80.0, currency="EUR")
    mock_stock_provider.get_details.return_value = None
    mock_etf_provider.get_details.return_value = ETFDetails(
        holdings=[], sector_breakdown=[], country_breakdown=[], ter_pct=None
    )

    target: dict[str, Any] = {
        "symbol": "EUNL.DE",
        "asset_type": "ETF",
        "target_allocation_pct": 20.0,
        "ter": "0.20",
    }

    enriched: dict[str, Any] = enrich_target_asset(
        target,
        current_alloc_pct=10.0,
        stock_provider=mock_stock_provider,
        etf_provider=mock_etf_provider,
    )

    assert enriched["symbol"] == "EUNL.DE"
    assert enriched["asset_type"] == "ETF"
    assert enriched["current_price"] == 80.0
    assert enriched["ter"] == 0.20


def test_enrich_target_asset_missing_symbol_or_type_raises_error() -> None:
    """Validates enrich_target_asset raises ValueError when mandatory keys are
    missing.
    """
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    with pytest.raises(ValueError, match="Missing symbol or type"):
        enrich_target_asset(
            {"symbol": ""},
            current_alloc_pct=0.0,
            stock_provider=mock_stock_provider,
            etf_provider=mock_etf_provider,
        )


@patch("argparse.ArgumentParser.parse_args")
@patch("src.cli.recommend.load_json_data")
@patch("src.cli.recommend.calculate_current_allocations")
@patch("src.cli.recommend.enrich_target_asset")
def test_run_decision_cli_execution(
    mock_enrich: MagicMock,
    mock_calc_alloc: MagicMock,
    mock_load_json: MagicMock,
    mock_parse_args: MagicMock,
) -> None:
    """Validates run_decision_cli orchestrates execution and renders output."""
    mock_args: MagicMock = MagicMock()
    mock_args.targets_file = "data/targets.json"
    mock_args.portfolio_file = "data/portfolio.json"
    mock_parse_args.return_value = mock_args

    mock_load_json.side_effect = [
        [{"symbol": "AAPL", "asset_type": "STOCK"}],
        [{"symbol": "AAPL", "quantity": 1.0}],
    ]

    mock_calc_alloc.return_value = ({"AAPL": 100.0}, 1000.0)

    mock_enrich.return_value = {
        "symbol": "AAPL",
        "asset_type": "STOCK",
        "current_price": 150.0,
        "peak_price": 200.0,
        "current_allocation_pct": 100.0,
        "target_allocation_pct": 50.0,
    }

    with patch("builtins.print") as mock_print:
        run_decision_cli()
        assert mock_print.called


def test_main_module_execution(tmp_path: Path) -> None:
    """Validates module execution flow when invoked as __main__ script."""
    empty_file: Path = tmp_path / "empty.json"
    empty_file.write_text("[]", encoding="utf-8")

    cli_args: list[str] = [
        "recommend",
        "--targets-file",
        str(empty_file),
        "--portfolio-file",
        str(empty_file),
    ]

    with patch.object(sys, "argv", cli_args), patch.dict(sys.modules):
        sys.modules.pop("src.cli.recommend", None)
        runpy.run_module("src.cli.recommend", run_name="__main__")
