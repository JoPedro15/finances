"""Unit tests for CLI decision module in src/cli/decision.py covering all scenarios."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.decision import (
    _display_rebalance_results,
    _format_action,
    _format_urgency,
    app,
    calculate_current_allocations,
    enrich_target_asset,
    export_outputs,
    load_json_data,
)
from src.core.decision.base import AssetScore, AssetType
from src.core.exceptions import GeminiAPIError, GeminiAuthError
from src.core.models import (
    CountryExposure,
    ETFDetails,
    Holding,
    Quotation,
    RebalanceRecommendation,
    RecommendationAction,
    SectorExposure,
    StockDetails,
    UrgencyLevel,
)

runner = CliRunner()


# ==============================================================================
# load_json_data
# ==============================================================================


def test_load_json_data_file_not_found(tmp_path: Path) -> None:
    """Validates load_json_data returns empty list when file does not exist."""
    non_existent: Path = tmp_path / "missing.json"
    assert load_json_data(non_existent) == []


def test_load_json_data_invalid_json(tmp_path: Path) -> None:
    """Validates load_json_data handles corrupted JSON gracefully."""
    invalid_file: Path = tmp_path / "invalid.json"
    invalid_file.write_text("{broken_json: ", encoding="utf-8")
    assert load_json_data(invalid_file) == []


def test_load_json_data_list_format(tmp_path: Path) -> None:
    """Validates load_json_data reads direct list JSON structure."""
    valid_file: Path = tmp_path / "list.json"
    data: list[dict[str, Any]] = [{"symbol": "AAPL", "quantity": 10}]
    valid_file.write_text(json.dumps(data), encoding="utf-8")

    result: list[dict[str, Any]] = load_json_data(valid_file)
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


def test_load_json_data_assets_dict_format(tmp_path: Path) -> None:
    """Validates load_json_data reads dict with 'assets' key structure."""
    valid_file: Path = tmp_path / "dict.json"
    data: dict[str, Any] = {"assets": [{"symbol": "NVDA", "quantity": 5}]}
    valid_file.write_text(json.dumps(data), encoding="utf-8")

    result: list[dict[str, Any]] = load_json_data(valid_file)
    assert len(result) == 1
    assert result[0]["symbol"] == "NVDA"


def test_load_json_data_unexpected_types(tmp_path: Path) -> None:
    """Validates load_json_data returns empty list on invalid root types."""
    num_file: Path = tmp_path / "number.json"
    num_file.write_text("123", encoding="utf-8")
    assert load_json_data(num_file) == []


# ==============================================================================
# calculate_current_allocations
# ==============================================================================


def test_calculate_current_allocations_success() -> None:
    """Validates real allocation % and total value calculation with mock provider."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_stock_provider.get_price.side_effect = [
        Quotation(price=100.0, currency="EUR"),
        Quotation(price=200.0, currency="EUR"),
    ]

    portfolio_items: list[dict[str, Any]] = [
        {"yahoo_ticker": "AAPL", "quantity": 2.0, "asset_type": "STOCK"},
        {"yahoo_ticker": "MSFT", "quantity": 1.0, "asset_type": "STOCK"},
    ]

    allocations, total_val = calculate_current_allocations(
        portfolio_items, mock_stock_provider
    )

    assert total_val == 400.0
    assert allocations["AAPL"] == 50.0
    assert allocations["MSFT"] == 50.0


def test_calculate_current_allocations_skips_invalid_items() -> None:
    """Validates calculate_current_allocations skips invalid or unpriced items."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_stock_provider.get_price.return_value = Quotation(price=0.0, currency="EUR")

    portfolio_items: list[dict[str, Any]] = [
        {"quantity": 0.0},
        {"yahoo_ticker": "AAPL", "quantity": 1.0},
    ]

    allocations, total_val = calculate_current_allocations(
        portfolio_items, mock_stock_provider
    )

    assert total_val == 0.0
    assert allocations == {}


# ==============================================================================
# enrich_target_asset
# ==============================================================================


def test_enrich_target_asset_missing_symbol_raises_value_error() -> None:
    """Validates enrich_target_asset raises ValueError when symbol is missing."""
    mock_stock: MagicMock = MagicMock()
    mock_etf: MagicMock = MagicMock()

    with pytest.raises(ValueError, match="Missing symbol or type"):
        enrich_target_asset({}, 0.0, mock_stock, mock_etf)


def test_enrich_target_asset_stock() -> None:
    """Validates target enrichment for STOCK assets fetching live details."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    mock_stock_provider.get_price.return_value = Quotation(price=150.0, currency="EUR")
    mock_stock_provider.get_details.return_value = StockDetails(
        fifty_two_week_high=200.0,
        fifty_two_week_low=100.0,
        pe_ratio=25.0,
        forward_pe=20.0,
    )

    target: dict[str, Any] = {
        "yahoo_ticker": "AAPL",
        "asset_type": "STOCK",
        "target_allocation_pct": 15.0,
    }

    enriched: dict[str, Any] = enrich_target_asset(
        target=target,
        current_alloc_pct=10.0,
        stock_provider=mock_stock_provider,
        etf_provider=mock_etf_provider,
    )

    assert enriched["symbol"] == "AAPL"
    assert enriched["asset_type"] == "STOCK"
    assert enriched["current_price"] == 150.0
    assert enriched["peak_price"] == 200.0
    assert enriched["trailing_pe"] == 25.0
    assert enriched["forward_pe"] == 20.0
    assert enriched["ter"] is None


def test_enrich_target_asset_etf() -> None:
    """Validates target enrichment for ETF assets fetching TER and breakdowns."""
    mock_stock_provider: MagicMock = MagicMock()
    mock_etf_provider: MagicMock = MagicMock()

    mock_stock_provider.get_price.return_value = Quotation(price=100.0, currency="EUR")
    mock_stock_provider.get_details.return_value = None
    mock_etf_provider.get_details.return_value = ETFDetails(
        holdings=[Holding(name="Apple", isin="US1", ticker="AAPL", weight_pct=5.0)],
        sector_breakdown=[SectorExposure(sector_name="Tech", weight_pct=50.0)],
        country_breakdown=[CountryExposure(country_name="US", weight_pct=100.0)],
        ter_pct=0.20,
    )

    target: dict[str, Any] = {
        "yahoo_ticker": "EUNL.DE",
        "asset_type": "ETF",
        "target_allocation_pct": 20.0,
    }

    enriched: dict[str, Any] = enrich_target_asset(
        target=target,
        current_alloc_pct=5.0,
        stock_provider=mock_stock_provider,
        etf_provider=mock_etf_provider,
    )

    assert enriched["symbol"] == "EUNL.DE"
    assert enriched["asset_type"] == "ETF"
    assert enriched["ter"] == 0.20
    assert len(enriched["sector_breakdown"]) == 1
    assert len(enriched["country_breakdown"]) == 1
    assert len(enriched["top_holdings"]) == 1


# ==============================================================================
# Helpers & Formatting
# ==============================================================================


def test_format_action_and_urgency() -> None:
    """Validates color-coded formatting for actions and urgency levels."""
    assert "BUY" in _format_action(RecommendationAction.BUY).plain
    assert "SELL" in _format_action(RecommendationAction.SELL).plain
    assert "HOLD" in _format_action(RecommendationAction.HOLD).plain
    assert "N/A" in _format_action(None).plain

    assert "HIGH" in _format_urgency(UrgencyLevel.HIGH).plain
    assert "MED" in _format_urgency(UrgencyLevel.MEDIUM).plain
    assert "LOW" in _format_urgency(UrgencyLevel.LOW).plain
    assert "N/A" in _format_urgency(None).plain


# ==============================================================================
# Outputs Export
# ==============================================================================


def test_export_outputs_success(tmp_path: Path) -> None:
    """Validates export_outputs writes structured
    decision matrix and markdown report."""
    score: AssetScore = AssetScore(
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        dip_score=0.8,
        cost_score=0.9,
        allocation_score=0.7,
        total_score=0.82,
    )

    asset_dict: dict[str, dict[str, Any]] = {
        "AAPL": {
            "current_price": 150.0,
            "current_allocation_pct": 10.0,
            "target_allocation_pct": 15.0,
        }
    }

    rec: RebalanceRecommendation = RebalanceRecommendation(
        action=RecommendationAction.BUY,
        confidence_score=0.95,
        reasoning="Good valuation dip.",
        target_allocation_pct=15.0,
        urgency_level=UrgencyLevel.HIGH,
        risk_score=2,
        valuation_score=8,
    )

    export_outputs(
        ranked_scores=[score],
        asset_dict_map=asset_dict,
        recommendations_map={"AAPL": rec},
        total_val=1000.0,
        has_ai=True,
        output_dir=tmp_path,
    )

    csv_path: Path = tmp_path / "decision_output.csv"
    md_path: Path = tmp_path / "decision_report.md"

    assert csv_path.exists()
    assert md_path.exists()

    with open(csv_path, encoding="utf-8") as file:
        reader = list(csv.DictReader(file))
        assert len(reader) == 1
        assert reader[0]["symbol"] == "AAPL"
        assert reader[0]["ai_action"] == "BUY"


def test_export_outputs_error_handling(tmp_path: Path) -> None:
    """Validates export_outputs handles permission/path failure gracefully."""
    invalid_path: Path = tmp_path / "non_existent_folder" / "sub"
    with patch("builtins.open", side_effect=OSError("Disk full")):
        export_outputs([], {}, {}, 1000.0, False, output_dir=invalid_path)


# ==============================================================================
# Result Rendering & Display
# ==============================================================================


def test_display_rebalance_results_rendering() -> None:
    """Validates _display_rebalance_results renders tables and advisory cards."""
    score_stock: AssetScore = AssetScore(
        symbol="AAPL",
        asset_type=AssetType.STOCK,
        dip_score=0.8,
        cost_score=0.9,
        allocation_score=0.7,
        total_score=0.82,
    )
    score_etf: AssetScore = AssetScore(
        symbol="EUNL.DE",
        asset_type=AssetType.ETF,
        dip_score=0.5,
        cost_score=0.6,
        allocation_score=0.5,
        total_score=0.55,
    )

    asset_dict: dict[str, dict[str, Any]] = {
        "AAPL": {
            "asset_type": "STOCK",
            "current_price": 150.0,
            "peak_price": 200.0,
            "low_52w": 120.0,
            "current_allocation_pct": 10.0,
            "target_allocation_pct": 15.0,
            "trailing_pe": 25.0,
            "forward_pe": 20.0,
        },
        "EUNL.DE": {
            "asset_type": "ETF",
            "current_price": 80.0,
            "peak_price": 85.0,
            "current_allocation_pct": 5.0,
            "target_allocation_pct": 10.0,
            "ter": 0.20,
        },
    }

    rec: RebalanceRecommendation = RebalanceRecommendation(
        action=RecommendationAction.BUY,
        confidence_score=0.90,
        reasoning="Solid buy opportunity.",
        target_allocation_pct=15.0,
        urgency_level=UrgencyLevel.HIGH,
        risk_score=2,
        valuation_score=8,
    )

    _display_rebalance_results(
        ranked_scores=[score_stock, score_etf],
        asset_dict_map=asset_dict,
        recommendations_map={"AAPL": rec},
        total_val=1000.0,
        has_ai=True,
        verbose=True,
    )


# ==============================================================================
# CLI Typer Command Integration
# ==============================================================================


def test_rebalance_command_missing_targets(tmp_path: Path) -> None:
    """Validates CLI exits with non-zero code when target file is empty."""
    targets: Path = tmp_path / "empty_targets.json"
    portfolio: Path = tmp_path / "portfolio.json"
    targets.write_text("[]", encoding="utf-8")
    portfolio.write_text("[]", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets),
            "--portfolio-file",
            str(portfolio),
        ],
    )

    assert result.exit_code != 0


@patch("src.cli.decision.calculate_current_allocations")
@patch("src.cli.decision.enrich_target_asset")
@patch("src.cli.decision.GeminiClient")
def test_rebalance_command_full_success(
    mock_gemini_cls: MagicMock,
    mock_enrich: MagicMock,
    mock_calc: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates full execution of rebalance command including AI integration."""
    targets: Path = tmp_path / "targets.json"
    portfolio: Path = tmp_path / "portfolio.json"

    targets.write_text(
        '[{"yahoo_ticker": "AAPL", "asset_type": "STOCK"}]', encoding="utf-8"
    )
    portfolio.write_text(
        '[{"yahoo_ticker": "AAPL", "quantity": 1.0}]', encoding="utf-8"
    )

    mock_calc.return_value = ({"AAPL": 100.0}, 150.0)
    mock_enrich.return_value = {
        "symbol": "AAPL",
        "asset_type": "STOCK",
        "current_price": 150.0,
        "peak_price": 180.0,
        "target_allocation_pct": 100.0,
        "current_allocation_pct": 100.0,
        "ter": None,
        "trailing_pe": 25.0,
        "forward_pe": 20.0,
        "low_52w": 120.0,
        "high_52w": 180.0,
        "sector_breakdown": [],
        "country_breakdown": [],
        "top_holdings": [],
    }

    mock_instance = MagicMock()
    mock_instance.analyze_portfolio_batch.return_value = {}
    mock_gemini_cls.return_value = mock_instance

    result = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets),
            "--portfolio-file",
            str(portfolio),
            "--verbose",
        ],
    )

    assert result.exit_code == 0


@patch("src.cli.decision.calculate_current_allocations")
@patch("src.cli.decision.enrich_target_asset")
@patch("src.cli.decision.GeminiClient")
def test_rebalance_command_gemini_auth_error_fallback(
    mock_gemini_cls: MagicMock,
    mock_enrich: MagicMock,
    mock_calc: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates rebalance command falls back cleanly when Gemini auth fails."""
    targets: Path = tmp_path / "targets.json"
    portfolio: Path = tmp_path / "portfolio.json"

    targets.write_text(
        '[{"yahoo_ticker": "AAPL", "asset_type": "STOCK"}]', encoding="utf-8"
    )
    portfolio.write_text("[]", encoding="utf-8")

    mock_calc.return_value = ({}, 150.0)
    mock_enrich.return_value = {
        "symbol": "AAPL",
        "asset_type": "STOCK",
        "current_price": 150.0,
        "peak_price": 180.0,
        "target_allocation_pct": 100.0,
        "current_allocation_pct": 0.0,
        "ter": None,
        "trailing_pe": 25.0,
        "forward_pe": 20.0,
        "low_52w": 120.0,
        "high_52w": 180.0,
        "sector_breakdown": [],
        "country_breakdown": [],
        "top_holdings": [],
    }

    mock_gemini_cls.side_effect = GeminiAuthError("Missing API Key")

    result = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets),
            "--portfolio-file",
            str(portfolio),
        ],
    )

    assert result.exit_code == 0


@patch("src.cli.decision.calculate_current_allocations")
@patch("src.cli.decision.enrich_target_asset")
@patch("src.cli.decision.GeminiClient")
def test_rebalance_command_gemini_api_error_fallback(
    mock_gemini_cls: MagicMock,
    mock_enrich: MagicMock,
    mock_calc: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates rebalance command falls back when Gemini API execution fails."""
    targets: Path = tmp_path / "targets.json"
    portfolio: Path = tmp_path / "portfolio.json"

    targets.write_text(
        '[{"yahoo_ticker": "AAPL", "asset_type": "STOCK"}]', encoding="utf-8"
    )
    portfolio.write_text("[]", encoding="utf-8")

    mock_calc.return_value = ({}, 150.0)
    mock_enrich.return_value = {
        "symbol": "AAPL",
        "asset_type": "STOCK",
        "current_price": 150.0,
        "peak_price": 180.0,
        "target_allocation_pct": 100.0,
        "current_allocation_pct": 0.0,
        "ter": None,
        "trailing_pe": 25.0,
        "forward_pe": 20.0,
        "low_52w": 120.0,
        "high_52w": 180.0,
        "sector_breakdown": [],
        "country_breakdown": [],
        "top_holdings": [],
    }

    mock_instance = MagicMock()
    mock_instance.analyze_portfolio_batch.side_effect = GeminiAPIError("API error")
    mock_gemini_cls.return_value = mock_instance

    result = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets),
            "--portfolio-file",
            str(portfolio),
        ],
    )

    assert result.exit_code == 0


@patch("src.cli.decision.calculate_current_allocations")
@patch("src.cli.decision.enrich_target_asset")
def test_rebalance_command_enrichment_failure_exits(
    mock_enrich: MagicMock,
    mock_calc: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates CLI exits with non-zero exit code when target enrichments fail."""
    targets: Path = tmp_path / "targets.json"
    portfolio: Path = tmp_path / "portfolio.json"
    targets.write_text(
        '[{"yahoo_ticker": "AAPL", "asset_type": "STOCK"}]', encoding="utf-8"
    )
    portfolio.write_text("[]", encoding="utf-8")

    mock_calc.return_value = ({}, 0.0)
    mock_enrich.side_effect = Exception("Provider error")

    result = runner.invoke(
        app,
        [
            "--targets-file",
            str(targets),
            "--portfolio-file",
            str(portfolio),
            "--skip-ai",
        ],
    )

    assert result.exit_code != 0
