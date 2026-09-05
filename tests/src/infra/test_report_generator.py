"""Unit tests for src/infra/report_generator.py."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from markupsafe import Markup

from src.infra.report_generator import PortfolioReportGenerator

# ==============================================================================
# Helpers / fixtures
# ==============================================================================


def _make_generator(tmp_path: Path, **kwargs: Any) -> PortfolioReportGenerator:
    return PortfolioReportGenerator(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "portfolio.json",
        output_dir=tmp_path / "reports",
        **kwargs,
    )


def _overview_stub() -> MagicMock:
    """Returns a minimal DashboardOverview mock with value_history and summaries."""
    vh = MagicMock()
    vh.date = "2026-01-01"
    vh.value = 2600.0
    history = MagicMock()
    history.value_history = [vh, vh]
    summary = MagicMock()
    summary.ticker = "NVDA"
    summary.name = "NVIDIA"
    summary.asset_type = "STOCK"
    summary.latest_quantity = 10.0
    summary.latest_value_eur = 1980.0
    summary.cost_basis_eur = 1500.0
    summary.roi_eur = 480.0
    summary.roi_percent = 32.0
    summary.portfolio_share_percent = 76.0
    overview = MagicMock()
    overview.portfolio_history = history
    overview.asset_summaries = [summary]
    overview.max_drawdown_percent = 5.0
    overview.top_growth_contributor = "NVDA"
    return overview


def _milestone_stub(yr: int) -> MagicMock:
    m = MagicMock()
    m.projected_value = 100_000.0 * yr
    m.inflation_adjusted_value = 80_000.0 * yr
    m.compound_interest = 20_000.0 * yr
    m.total_invested = 60_000.0 * yr
    return m


def _scenario_stub(name: str) -> MagicMock:
    s = MagicMock()
    s.milestones = {yr: _milestone_stub(yr) for yr in [10, 20, 30]}
    return s


# ==============================================================================
# _chart_to_b64
# ==============================================================================


def test_chart_to_b64_missing_file_returns_empty_markup(tmp_path: Path) -> None:
    """Returns empty Markup when chart file does not exist."""
    result = PortfolioReportGenerator._chart_to_b64(tmp_path / "missing.png")
    assert result == Markup("")


def test_chart_to_b64_existing_file_returns_base64(tmp_path: Path) -> None:
    """Returns a non-empty Markup-wrapped base64 string for an existing file."""
    img = tmp_path / "chart.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = PortfolioReportGenerator._chart_to_b64(img)
    assert isinstance(result, Markup)
    assert len(result) > 0
    decoded = base64.b64decode(str(result))
    assert decoded == b"\x89PNG\r\n\x1a\n"


# ==============================================================================
# _build_growth_scenarios
# ==============================================================================


def test_build_growth_scenarios_returns_three_scenarios(tmp_path: Path) -> None:
    """Three scenarios (Conservative, Moderate, Aggressive) are returned."""
    gen = _make_generator(tmp_path)
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_extractor_cls,
        patch("src.infra.report_generator.ProjectionEngine") as mock_engine_cls,
    ):
        mock_extractor_cls.return_value.fetch_portfolio_history.return_value = []
        mock_engine_cls.return_value.generate_scenario.side_effect = (
            lambda name, *a, **kw: _scenario_stub(name)
        )
        result = gen._build_growth_scenarios()

    assert len(result) == 3
    names = [s["name"] for s in result]
    assert names == ["Conservative", "Moderate", "Aggressive"]


def test_build_growth_scenarios_rates(tmp_path: Path) -> None:
    """Annual return percentages match expected rates."""
    gen = _make_generator(tmp_path)
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_eng.return_value.generate_scenario.side_effect = (
            lambda name, *a, **kw: _scenario_stub(name)
        )
        result = gen._build_growth_scenarios()

    rates = [s["annual_return_pct"] for s in result]
    assert rates == pytest.approx([5.0, 7.0, 9.0])


def test_build_growth_scenarios_milestones_present(tmp_path: Path) -> None:
    """Each scenario contains milestones for years 10, 20, 30."""
    gen = _make_generator(tmp_path)
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_eng.return_value.generate_scenario.side_effect = (
            lambda name, *a, **kw: _scenario_stub(name)
        )
        result = gen._build_growth_scenarios()

    for scenario in result:
        years = [m["year"] for m in scenario["milestones"]]
        assert years == [10, 20, 30]


def test_build_growth_scenarios_uses_last_portfolio_value(tmp_path: Path) -> None:
    """Initial value is taken from the last record in portfolio history."""
    gen = _make_generator(tmp_path)
    record = MagicMock()
    record.total_value_eur = 5000.0
    calls: list[float] = []

    def capture_scenario(name: str, initial: float, *a: Any, **kw: Any) -> MagicMock:
        calls.append(initial)
        return _scenario_stub(name)

    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = [record]
        mock_eng.return_value.generate_scenario.side_effect = capture_scenario
        gen._build_growth_scenarios()

    assert all(v == pytest.approx(5000.0) for v in calls)


def test_build_growth_scenarios_empty_history_uses_zero(tmp_path: Path) -> None:
    """Initial value defaults to 0.0 when portfolio history is empty."""
    gen = _make_generator(tmp_path)
    calls: list[float] = []

    def capture_scenario(name: str, initial: float, *a: Any, **kw: Any) -> MagicMock:
        calls.append(initial)
        return _scenario_stub(name)

    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_eng.return_value.generate_scenario.side_effect = capture_scenario
        gen._build_growth_scenarios()

    assert all(v == pytest.approx(0.0) for v in calls)


# ==============================================================================
# _build_overview
# ==============================================================================


def test_build_overview_uses_repo_assets(tmp_path: Path) -> None:
    """Assets are loaded from SqlitePortfolioRepository when available."""
    gen = _make_generator(tmp_path)
    mock_asset = MagicMock()
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.SqlitePortfolioRepository") as mock_repo_cls,
        patch("src.infra.report_generator.PortfolioAnalyticsEngine") as mock_analytics,
    ):
        mock_ext.return_value.fetch_asset_history.return_value = []
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_repo_cls.return_value.load_assets.return_value = [mock_asset]
        mock_analytics.return_value.build_dashboard_overview.return_value = (
            _overview_stub()
        )
        gen._build_overview()

    call_kwargs = mock_analytics.return_value.build_dashboard_overview.call_args[1]
    assert mock_asset in call_kwargs["current_assets"]


def test_build_overview_falls_back_to_config_json(tmp_path: Path) -> None:
    """Falls back to portfolio.json when repository raises."""
    import json

    config = tmp_path / "portfolio.json"
    config.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "name": "NVDA",
                        "isin": "",
                        "yahoo_ticker": "NVDA",
                        "asset_type": "STOCK",
                        "quantity": 1.0,
                        "average_buy_price": 100.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    gen = _make_generator(tmp_path)
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.SqlitePortfolioRepository") as mock_repo_cls,
        patch("src.infra.report_generator.PortfolioAnalyticsEngine") as mock_analytics,
    ):
        mock_ext.return_value.fetch_asset_history.return_value = []
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_repo_cls.return_value.load_assets.side_effect = RuntimeError("no db")
        mock_analytics.return_value.build_dashboard_overview.return_value = (
            _overview_stub()
        )
        gen._build_overview()

    call_kwargs = mock_analytics.return_value.build_dashboard_overview.call_args[1]
    assert len(call_kwargs["current_assets"]) == 1
    assert call_kwargs["current_assets"][0].yahoo_ticker == "NVDA"


def test_build_overview_repo_and_config_both_fail(tmp_path: Path) -> None:
    """Returns empty current_assets list when both repo and config fail."""
    gen = _make_generator(tmp_path)
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.SqlitePortfolioRepository") as mock_repo_cls,
        patch("src.infra.report_generator.PortfolioAnalyticsEngine") as mock_analytics,
    ):
        mock_ext.return_value.fetch_asset_history.return_value = []
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_repo_cls.return_value.load_assets.side_effect = RuntimeError("no db")
        mock_analytics.return_value.build_dashboard_overview.return_value = (
            _overview_stub()
        )
        gen._build_overview()

    call_kwargs = mock_analytics.return_value.build_dashboard_overview.call_args[1]
    assert call_kwargs["current_assets"] == []


# ==============================================================================
# _build_template_context
# ==============================================================================


def test_build_template_context_keys_present(tmp_path: Path) -> None:
    """All required template keys are present in the context dict."""
    gen = _make_generator(tmp_path)
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_eng.return_value.generate_scenario.side_effect = (
            lambda name, *a, **kw: _scenario_stub(name)
        )
        ctx = gen._build_template_context(
            overview=_overview_stub(),
            chart_valuation_b64=Markup(""),
            chart_class_b64=Markup(""),
            opportunities=[],
            generated_at="2026-01-01 00:00:00",
        )

    for key in [
        "generated_at",
        "total_value_eur",
        "total_roi_eur",
        "total_roi_percent",
        "max_drawdown_percent",
        "asset_summaries",
        "composition",
        "opportunities",
        "has_opportunities",
        "growth_scenarios",
    ]:
        assert key in ctx, f"Missing key: {key}"


def test_build_template_context_composition_etf_stock(tmp_path: Path) -> None:
    """Composition list groups assets by type correctly."""
    gen = _make_generator(tmp_path)
    overview = _overview_stub()
    etf_summary = MagicMock()
    etf_summary.ticker = "EUNL.DE"
    etf_summary.name = "World ETF"
    etf_summary.asset_type = "ETF"
    etf_summary.latest_quantity = 5.0
    etf_summary.latest_value_eur = 620.0
    etf_summary.cost_basis_eur = 500.0
    etf_summary.roi_eur = 120.0
    etf_summary.roi_percent = 24.0
    etf_summary.portfolio_share_percent = 24.0
    overview.asset_summaries = [overview.asset_summaries[0], etf_summary]

    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_eng.return_value.generate_scenario.side_effect = (
            lambda name, *a, **kw: _scenario_stub(name)
        )
        ctx = gen._build_template_context(
            overview=overview,
            chart_valuation_b64=Markup(""),
            chart_class_b64=Markup(""),
            opportunities=[],
            generated_at="2026-01-01 00:00:00",
        )

    types = {c["asset_type"] for c in ctx["composition"]}
    assert "STOCK" in types
    assert "ETF" in types


def test_build_template_context_has_opportunities_flag(tmp_path: Path) -> None:
    """has_opportunities is True when opportunities list is non-empty."""
    gen = _make_generator(tmp_path)
    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_eng.return_value.generate_scenario.side_effect = (
            lambda name, *a, **kw: _scenario_stub(name)
        )
        ctx = gen._build_template_context(
            overview=_overview_stub(),
            chart_valuation_b64=Markup(""),
            chart_class_b64=Markup(""),
            opportunities=[{"symbol": "LLY"}],
            generated_at="2026-01-01 00:00:00",
        )

    assert ctx["has_opportunities"] is True


def test_build_template_context_empty_value_history(tmp_path: Path) -> None:
    """Empty value history yields fallback dash strings and 0.0 total value."""
    gen = _make_generator(tmp_path)
    overview = _overview_stub()
    overview.portfolio_history.value_history = []

    with (
        patch("src.infra.report_generator.FinanceSQLExtractor") as mock_ext,
        patch("src.infra.report_generator.ProjectionEngine") as mock_eng,
    ):
        mock_ext.return_value.fetch_portfolio_history.return_value = []
        mock_eng.return_value.generate_scenario.side_effect = (
            lambda name, *a, **kw: _scenario_stub(name)
        )
        ctx = gen._build_template_context(
            overview=overview,
            chart_valuation_b64=Markup(""),
            chart_class_b64=Markup(""),
            opportunities=[],
            generated_at="2026-01-01",
        )

    assert ctx["total_value_eur"] == pytest.approx(0.0)
    assert ctx["period_start"] == "—"
    assert ctx["period_end"] == "—"


# ==============================================================================
# generate
# ==============================================================================


def _patch_generate(tmp_path: Path) -> tuple[PortfolioReportGenerator, dict]:
    """Returns a generator and a dict of all the patches needed for generate()."""
    gen = _make_generator(tmp_path)
    patches: dict = {
        "overview": patch.object(gen, "_build_overview", return_value=_overview_stub()),
        "chart_exp": patch(
            "src.infra.report_generator.PortfolioChartExporter",
            return_value=MagicMock(
                export_portfolio_valuation_chart=MagicMock(
                    return_value=tmp_path / "v.png"
                ),
                export_asset_class_chart=MagicMock(return_value=tmp_path / "c.png"),
            ),
        ),
        "opp_repo": patch(
            "src.infra.report_generator.SqliteOpportunityRepository",
            return_value=MagicMock(
                load_latest_top_opportunities=MagicMock(return_value=[])
            ),
        ),
        "growth": patch.object(gen, "_build_growth_scenarios", return_value=[]),
    }
    return gen, patches


def test_generate_creates_html_file(tmp_path: Path) -> None:
    """generate() writes the HTML file to disk."""
    gen, patches = _patch_generate(tmp_path)
    with (
        patches["overview"],
        patches["chart_exp"],
        patches["opp_repo"],
        patches["growth"],
        patch("webbrowser.open"),
    ):
        html_path = gen.generate(open_browser=False)

    assert html_path.exists()
    assert html_path.name == "portfolio_report.html"


def test_generate_html_contains_expected_content(tmp_path: Path) -> None:
    """Generated HTML includes asset name from context."""
    gen, patches = _patch_generate(tmp_path)
    with (
        patches["overview"],
        patches["chart_exp"],
        patches["opp_repo"],
        patches["growth"],
    ):
        html_path = gen.generate(open_browser=False)

    content = html_path.read_text(encoding="utf-8")
    assert "NVIDIA" in content


def test_generate_returns_path(tmp_path: Path) -> None:
    """generate() returns a Path object."""
    gen, patches = _patch_generate(tmp_path)
    with (
        patches["overview"],
        patches["chart_exp"],
        patches["opp_repo"],
        patches["growth"],
    ):
        result = gen.generate(open_browser=False)

    assert isinstance(result, Path)


def test_generate_opens_browser_when_requested(tmp_path: Path) -> None:
    """webbrowser.open is called when open_browser=True."""
    gen, patches = _patch_generate(tmp_path)
    with (
        patches["overview"],
        patches["chart_exp"],
        patches["opp_repo"],
        patches["growth"],
        patch("webbrowser.open") as mock_browser,
    ):
        gen.generate(open_browser=True)

    mock_browser.assert_called_once()


def test_generate_no_browser_when_flag_false(tmp_path: Path) -> None:
    """webbrowser.open is NOT called when open_browser=False."""
    gen, patches = _patch_generate(tmp_path)
    with (
        patches["overview"],
        patches["chart_exp"],
        patches["opp_repo"],
        patches["growth"],
        patch("webbrowser.open") as mock_browser,
    ):
        gen.generate(open_browser=False)

    mock_browser.assert_not_called()


def test_generate_opportunity_repo_failure_graceful(tmp_path: Path) -> None:
    """generate() succeeds even when opportunity repository raises."""
    gen, patches = _patch_generate(tmp_path)
    with (
        patches["overview"],
        patches["chart_exp"],
        patch(
            "src.infra.report_generator.SqliteOpportunityRepository",
            return_value=MagicMock(
                load_latest_top_opportunities=MagicMock(
                    side_effect=RuntimeError("db error")
                )
            ),
        ),
        patches["growth"],
    ):
        html_path = gen.generate(open_browser=False)

    assert html_path.exists()


def test_generate_overwrites_existing_file(tmp_path: Path) -> None:
    """Calling generate() twice overwrites the previous HTML file."""
    gen, patches = _patch_generate(tmp_path)
    html_path = gen.output_dir / "portfolio_report.html"
    gen.output_dir.mkdir(parents=True, exist_ok=True)
    html_path.write_text("old content", encoding="utf-8")

    with (
        patches["overview"],
        patches["chart_exp"],
        patches["opp_repo"],
        patches["growth"],
    ):
        gen.generate(open_browser=False)

    assert "old content" not in html_path.read_text(encoding="utf-8")
