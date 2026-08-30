"""Unit tests for dashboard CLI command."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner, Result

from src.cli.dashboard import app

runner: CliRunner = CliRunner()


def create_test_db(db_path: Path) -> None:
    """Helper to create SQLite database with test records."""
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    try:
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE snapshots (id INTEGER PRIMARY KEY, date TEXT, "
            "total_value_eur REAL);"
        )
        cursor.execute(
            "CREATE TABLE assets (id INTEGER PRIMARY KEY, ticker TEXT, "
            "name TEXT, type TEXT);"
        )
        cursor.execute(
            "CREATE TABLE asset_snapshots (id INTEGER PRIMARY KEY, "
            "snapshot_id INTEGER, asset_id INTEGER, quantity REAL, "
            "value_eur REAL);"
        )
        cursor.execute("INSERT INTO snapshots VALUES (1, '2026-08-01', 1000.0);")
        cursor.execute("INSERT INTO assets VALUES (1, 'AAPL', 'Apple Inc.', 'STOCK');")
        cursor.execute("INSERT INTO asset_snapshots VALUES (1, 1, 1, 5.0, 1000.0);")
        conn.commit()
    finally:
        conn.close()


def test_dashboard_show_full(tmp_path: Path) -> None:
    """Tests executing dashboard show command for full overview."""
    db_file: Path = tmp_path / "finances.db"
    create_test_db(db_file)

    result: Result = runner.invoke(app, ["show", "--db-path", str(db_file)])

    assert result.exit_code == 0
    assert "GLOBAL PORTFOLIO EXECUTIVE SUMMARY" in result.output
    assert "AAPL" in result.output


def test_dashboard_show_with_config_list(tmp_path: Path) -> None:
    """Tests executing dashboard show command with list asset config."""
    db_file: Path = tmp_path / "finances.db"
    create_test_db(db_file)

    config_file: Path = tmp_path / "assets.json"
    config_data: list[dict[str, str | float]] = [
        {
            "name": "Apple Inc.",
            "isin": "US0378331005",
            "yahoo_ticker": "AAPL",
            "quantity": 5.0,
            "average_buy_price": 150.0,
            "asset_type": "STOCK",
        }
    ]
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    result: Result = runner.invoke(
        app,
        ["show", "--db-path", str(db_file), "--config", str(config_file)],
    )

    assert result.exit_code == 0
    assert "GLOBAL PORTFOLIO EXECUTIVE SUMMARY" in result.output


def test_dashboard_show_with_config_dict(tmp_path: Path) -> None:
    """Tests executing dashboard show command with dict asset config."""
    db_file: Path = tmp_path / "finances.db"
    create_test_db(db_file)

    config_file: Path = tmp_path / "assets.json"
    config_data: dict[str, list[dict[str, str | float]]] = {
        "assets": [
            {
                "name": "Apple Inc.",
                "isin": "US0378331005",
                "yahoo_ticker": "AAPL",
                "quantity": 5.0,
                "average_buy_price": 150.0,
                "asset_type": "STOCK",
            }
        ]
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    result: Result = runner.invoke(
        app,
        ["show", "--db-path", str(db_file), "--config", str(config_file)],
    )

    assert result.exit_code == 0
    assert "GLOBAL PORTFOLIO EXECUTIVE SUMMARY" in result.output


def test_dashboard_show_invalid_config(tmp_path: Path) -> None:
    """Tests handling broken config file gracefully with warning."""
    db_file: Path = tmp_path / "finances.db"
    create_test_db(db_file)

    config_file: Path = tmp_path / "assets.json"
    config_file.write_text("invalid json content", encoding="utf-8")

    result: Result = runner.invoke(
        app,
        ["show", "--db-path", str(db_file), "--config", str(config_file)],
    )

    assert result.exit_code == 0
    assert "Could not load config" in result.output


def test_dashboard_show_ticker_filter(tmp_path: Path) -> None:
    """Tests executing dashboard show command with ticker filter."""
    db_file: Path = tmp_path / "finances.db"
    create_test_db(db_file)

    result: Result = runner.invoke(
        app, ["show", "--db-path", str(db_file), "--ticker", "AAPL"]
    )

    assert result.exit_code == 0
    assert "ASSET DETAIL ANALYSIS - AAPL" in result.output


def test_dashboard_show_ticker_not_found(tmp_path: Path) -> None:
    """Tests executing dashboard show command with non-existent ticker."""
    db_file: Path = tmp_path / "finances.db"
    create_test_db(db_file)

    result: Result = runner.invoke(
        app, ["show", "--db-path", str(db_file), "--ticker", "INVALID"]
    )

    assert result.exit_code == 1
    assert "Ticker 'INVALID' not found" in result.output


@patch("src.cli.dashboard.PortfolioChartExporter")
def test_dashboard_show_export_plots(
    mock_exporter_cls: MagicMock, tmp_path: Path
) -> None:
    """Tests executing dashboard show command with plot export flag."""
    mock_exporter: MagicMock = MagicMock()
    mock_exporter_cls.return_value = mock_exporter
    mock_exporter.export_portfolio_valuation_chart.return_value = Path("val.png")
    mock_exporter.export_asset_class_chart.return_value = Path("class.png")

    db_file: Path = tmp_path / "finances.db"
    create_test_db(db_file)

    result: Result = runner.invoke(
        app, ["show", "--db-path", str(db_file), "--export-plots"]
    )

    assert result.exit_code == 0
    assert "Charts exported successfully" in result.output
