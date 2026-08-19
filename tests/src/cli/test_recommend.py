"""Unit tests for src/cli/recommend.py covering JSON parsing, live allocation
calculations, target asset enrichment, CLI execution, and UI formatters.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.recommend import (
    _format_action,
    _format_urgency,
    app,
    calculate_current_allocations,
    enrich_target_asset,
    load_json_data,
)
from src.core.exceptions import GeminiAPIError, GeminiAuthError
from src.core.models import (
    ETFDetails,
    Quotation,
    RebalanceRecommendation,
    RecommendationAction,
    StockDetails,
    UrgencyLevel,
)

runner: CliRunner = CliRunner()


def test_load_json_data_missing_file(tmp_path: Path) -> None:
    """Validates load_json_data returns an empty list when file does not exist."""
    missing_file: Path = tmp_path / "missing.json"
    assert load_json_data(missing_file) == []


def test_load_json_data_corrupted_json(tmp_path: Path) -> None:
    """Validates load_json_data handles JSON syntax errors gracefully."""
    file_path: Path = tmp_path / "corrupt.json"
    file_path.write_text("{invalid_json", encoding="utf-8")
    assert load_json_data(file_path) == []


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


def test_load_json_data_dict_invalid_assets(tmp_path: Path) -> None:
    """Validates load_json_data returns empty list when assets key is not list."""
    file_path: Path = tmp_path / "invalid_assets.json"
    file_path.write_text('{"assets": "not_a_list"}', encoding="utf-8")
    assert load_json_data(file_path) == []


def test_load_json_data_invalid_structure(tmp_path: Path) -> None:
    """Validates load_json_data returns empty list for unexpected JSON roots."""
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


def test_calculate_current_allocations_zero_price_skipped() -> None:
    """Validates calculate_current_allocations skips positions with 0 price."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_stock_provider.get_price.side_effect = [
        Quotation(price=0.0, currency="EUR"),
        Quotation(price=100.0, currency="EUR"),
    ]

    portfolio_items: list[dict[str, Any]] = [
        {"yahoo_ticker": "BAD", "quantity": 10.0},
        {"symbol": "GOOD", "quantity": 2.0},
    ]

    alloc_map: dict[str, float]
    total_val: float
    alloc_map, total_val = calculate_current_allocations(
        portfolio_items, mock_stock_provider
    )

    assert total_val == 200.0
    assert "BAD" not in alloc_map
    assert alloc_map["GOOD"] == 100.0


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


def test_enrich_target_asset_peak_price_zero_fallback() -> None:
    """Validates peak_price defaults to a floor value when prices are zero."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    mock_stock_provider.get_price.return_value = Quotation(price=0.0, currency="EUR")
    mock_stock_provider.get_details.return_value = StockDetails(
        sector=None,
        industry=None,
        market_cap=None,
        pe_ratio=None,
        forward_pe=None,
        dividend_yield_pct=None,
        fifty_two_week_high=0.0,
        fifty_two_week_low=0.0,
    )

    target: dict[str, Any] = {"symbol": "ZERO", "asset_type": "STOCK"}
    enriched: dict[str, Any] = enrich_target_asset(
        target, 0.0, mock_stock_provider, mock_etf_provider
    )

    assert enriched["peak_price"] == 0.01


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


def test_format_action_and_urgency_helpers() -> None:
    """Validates color-coded text formatting helpers for actions and urgencies."""
    assert _format_action(RecommendationAction.BUY).plain == "BUY"
    assert _format_action(RecommendationAction.SELL).plain == "SELL"
    assert _format_action(RecommendationAction.HOLD).plain == "HOLD"
    assert _format_action(None).plain == "N/A"

    assert _format_urgency(UrgencyLevel.HIGH).plain == "HIGH"
    assert _format_urgency(UrgencyLevel.MEDIUM).plain == "MED"
    assert _format_urgency(UrgencyLevel.LOW).plain == "LOW"
    assert _format_urgency(None).plain == "N/A"


def test_recommend_rebalance_empty_targets(tmp_path: Path) -> None:
    """Validates CLI terminates with error code 1 when target file is empty."""
    empty_file: Path = tmp_path / "empty_targets.json"
    empty_file.write_text("[]", encoding="utf-8")

    result: Any = runner.invoke(app, ["--targets-file", str(empty_file)])
    assert result.exit_code == 1
    assert "No targets found" in result.output


def test_recommend_rebalance_no_enriched_assets(tmp_path: Path) -> None:
    """Validates CLI terminates when target assets cannot be enriched."""
    targets_file: Path = tmp_path / "targets.json"
    targets_file.write_text('[{"symbol": "INVALID"}]', encoding="utf-8")

    with patch("src.cli.recommend.enrich_target_asset") as mock_enrich:
        mock_enrich.side_effect = ValueError("Invalid asset")
        result: Any = runner.invoke(app, ["--targets-file", str(targets_file)])
        assert result.exit_code == 1
        assert "Could not enrich any target asset" in result.output


@patch("src.cli.recommend.GeminiClient")
@patch("src.cli.recommend.StockProvider")
@patch("src.cli.recommend.ETFProvider")
def test_recommend_rebalance_full_ai_success(
    mock_etf_cls: MagicMock,
    mock_stock_cls: MagicMock,
    mock_gemini_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates CLI rebalance command execution with successful AI analysis."""
    targets_file: Path = tmp_path / "targets.json"
    portfolio_file: Path = tmp_path / "portfolio.json"

    targets_file.write_text(
        '[{"symbol": "AAPL", "type": "STOCK", "target_allocation_pct": 50.0}]',
        encoding="utf-8",
    )
    portfolio_file.write_text(
        '[{"symbol": "AAPL", "quantity": 10.0, "asset_type": "stock"}]',
        encoding="utf-8",
    )

    mock_stock_inst: MagicMock = MagicMock()
    mock_stock_inst.get_price.return_value = Quotation(price=150.0, currency="EUR")
    mock_stock_inst.get_details.return_value = StockDetails(
        sector="Tech",
        industry="Consumer Electronics",
        market_cap=2e12,
        pe_ratio=25.0,
        forward_pe=20.0,
        dividend_yield_pct=0.5,
        fifty_two_week_high=200.0,
        fifty_two_week_low=120.0,
    )
    mock_stock_cls.return_value = mock_stock_inst

    mock_gemini_inst: MagicMock = MagicMock()
    mock_gemini_inst.analyze_asset.return_value = RebalanceRecommendation(
        action=RecommendationAction.BUY,
        urgency_level=UrgencyLevel.HIGH,
        confidence_score=0.9,
        target_allocation_pct=50.0,
        risk_score=3,
        valuation_score=8,
        reasoning="Strong growth potential and undervaluation.",
    )
    mock_gemini_cls.return_value = mock_gemini_inst

    result: Any = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets_file),
            "--portfolio-file",
            str(portfolio_file),
        ],
    )

    assert result.exit_code == 0
    assert "AAPL" in result.output
    assert "BUY" in result.output
    assert "HIGH" in result.output
    assert "90%" in result.output


@patch("src.cli.recommend.send_discord_notification")
@patch("src.cli.recommend.StockProvider")
def test_recommend_rebalance_notify_flag_triggers_discord(
    mock_stock_cls: MagicMock,
    mock_send_discord: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates --notify flag triggers send_discord_notification."""
    targets_file: Path = tmp_path / "targets.json"
    portfolio_file: Path = tmp_path / "portfolio.json"

    targets_file.write_text(
        '[{"symbol": "AAPL", "type": "STOCK", "target_allocation_pct": 100.0}]',
        encoding="utf-8",
    )
    portfolio_file.write_text("[]", encoding="utf-8")

    mock_stock_inst: MagicMock = MagicMock()
    mock_stock_inst.get_price.return_value = Quotation(price=150.0, currency="EUR")
    mock_stock_inst.get_details.return_value = None
    mock_stock_cls.return_value = mock_stock_inst

    result: Any = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets_file),
            "--portfolio-file",
            str(portfolio_file),
            "--skip-ai",
            "--notify",
        ],
    )

    assert result.exit_code == 0
    mock_send_discord.assert_called_once()


@patch("src.cli.recommend.send_discord_notification")
@patch("src.cli.recommend.StockProvider")
def test_recommend_rebalance_without_notify_skips_discord(
    mock_stock_cls: MagicMock,
    mock_send_discord: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates missing --notify flag refrains from calling Discord notification."""
    targets_file: Path = tmp_path / "targets.json"
    portfolio_file: Path = tmp_path / "portfolio.json"

    targets_file.write_text(
        '[{"symbol": "AAPL", "type": "STOCK", "target_allocation_pct": 100.0}]',
        encoding="utf-8",
    )
    portfolio_file.write_text("[]", encoding="utf-8")

    mock_stock_inst: MagicMock = MagicMock()
    mock_stock_inst.get_price.return_value = Quotation(price=150.0, currency="EUR")
    mock_stock_inst.get_details.return_value = None
    mock_stock_cls.return_value = mock_stock_inst

    result: Any = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets_file),
            "--portfolio-file",
            str(portfolio_file),
            "--skip-ai",
        ],
    )

    assert result.exit_code == 0
    mock_send_discord.assert_not_called()


@patch("src.cli.recommend.GeminiClient")
@patch("src.cli.recommend.StockProvider")
def test_recommend_rebalance_gemini_auth_error_fallback(
    mock_stock_cls: MagicMock,
    mock_gemini_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates CLI falls back to quant-only mode on GeminiAuthError."""
    targets_file: Path = tmp_path / "targets.json"
    portfolio_file: Path = tmp_path / "portfolio.json"

    targets_file.write_text(
        '[{"symbol": "AAPL", "type": "STOCK", "target_allocation_pct": 50.0}]',
        encoding="utf-8",
    )
    portfolio_file.write_text("[]", encoding="utf-8")

    mock_stock_inst: MagicMock = MagicMock()
    mock_stock_inst.get_price.return_value = Quotation(price=150.0, currency="EUR")
    mock_stock_inst.get_details.return_value = None
    mock_stock_cls.return_value = mock_stock_inst

    mock_gemini_cls.side_effect = GeminiAuthError("API Key missing")

    result: Any = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets_file),
            "--portfolio-file",
            str(portfolio_file),
        ],
    )

    assert result.exit_code == 0
    assert "Gemini AI disabled" in result.output
    assert "AAPL" in result.output


@patch("src.cli.recommend.GeminiClient")
@patch("src.cli.recommend.StockProvider")
def test_recommend_rebalance_gemini_api_error_per_asset(
    mock_stock_cls: MagicMock,
    mock_gemini_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates error row handling when Gemini API fails for an asset."""
    targets_file: Path = tmp_path / "targets.json"
    portfolio_file: Path = tmp_path / "portfolio.json"

    targets_file.write_text(
        '[{"symbol": "AAPL", "type": "STOCK", "target_allocation_pct": 50.0}]',
        encoding="utf-8",
    )
    portfolio_file.write_text("[]", encoding="utf-8")

    mock_stock_inst: MagicMock = MagicMock()
    mock_stock_inst.get_price.return_value = Quotation(price=150.0, currency="EUR")
    mock_stock_inst.get_details.return_value = None
    mock_stock_cls.return_value = mock_stock_inst

    mock_gemini_inst: MagicMock = MagicMock()
    mock_gemini_inst.analyze_asset.side_effect = GeminiAPIError("Quota exceeded")
    mock_gemini_cls.return_value = mock_gemini_inst

    result: Any = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets_file),
            "--portfolio-file",
            str(portfolio_file),
        ],
    )

    assert result.exit_code == 0
    assert "ERROR" in result.output
    assert "AI analysis failed" in result.output


@patch("src.cli.recommend.StockProvider")
def test_recommend_rebalance_skip_ai(
    mock_stock_cls: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates --skip-ai flag bypasses Gemini client initialization."""
    targets_file: Path = tmp_path / "targets.json"
    portfolio_file: Path = tmp_path / "portfolio.json"

    targets_file.write_text(
        '[{"symbol": "MSFT", "type": "STOCK", "target_allocation_pct": 100.0}]',
        encoding="utf-8",
    )
    portfolio_file.write_text("[]", encoding="utf-8")

    mock_stock_inst: MagicMock = MagicMock()
    mock_stock_inst.get_price.return_value = Quotation(price=300.0, currency="EUR")
    mock_stock_inst.get_details.return_value = None
    mock_stock_cls.return_value = mock_stock_inst

    with patch("src.cli.recommend.GeminiClient") as mock_gemini_cls:
        result: Any = runner.invoke(
            app,
            [
                "--targets-file",
                str(targets_file),
                "--portfolio-file",
                str(portfolio_file),
                "--skip-ai",
            ],
        )

        assert result.exit_code == 0
        assert not mock_gemini_cls.called
        assert "MSFT" in result.output


def test_main_module_execution() -> None:
    """Validates module execution flow when invoked as __main__ script."""
    with patch.object(sys, "argv", ["recommend", "--help"]), patch.dict(sys.modules):
        sys.modules.pop("src.cli.recommend", None)
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("src.cli.recommend", run_name="__main__")
        assert exc_info.value.code == 0
