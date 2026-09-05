"""Automated executive portfolio report generator (HTML + PDF)."""

from __future__ import annotations

import base64
import json
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

import jinja2
from markupsafe import Markup

from src.config import DATA_DIR
from src.core.models import (
    Asset,
    AssetPerformanceSummary,
    DashboardOverview,
    GrowthProjectionScenario,
)
from src.core.portfolio_analytics import PortfolioAnalyticsEngine
from src.core.projections import ProjectionEngine
from src.core.repositories import SqliteOpportunityRepository, SqlitePortfolioRepository
from src.infra.database.connection import DEFAULT_DB_PATH
from src.infra.database.finance_sql_extraction import (
    AssetHistoricalRecord,
    FinanceSQLExtractor,
    PortfolioHistoricalRecord,
)
from src.utils.graphics.portfolio_charts import PortfolioChartExporter

_DEFAULT_TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / "templates"


class PortfolioReportGenerator:
    """Generates a dark-theme HTML + PDF executive portfolio report."""

    def __init__(
        self,
        db_path: Path = Path(DEFAULT_DB_PATH),
        config_path: Path = DATA_DIR / "portfolio.json",
        output_dir: Path = Path("output/reports"),
        template_dir: Path = _DEFAULT_TEMPLATE_DIR,
    ) -> None:
        self.db_path = db_path
        self.config_path = config_path
        self.output_dir = output_dir
        self._jinja_env: jinja2.Environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            autoescape=jinja2.select_autoescape(["html"]),
        )

    def _build_overview(self) -> DashboardOverview:
        extractor = FinanceSQLExtractor(db_path=self.db_path)
        asset_records: list[AssetHistoricalRecord] = extractor.fetch_asset_history()
        portfolio_records: list[PortfolioHistoricalRecord] = (
            extractor.fetch_portfolio_history()
        )

        current_assets: list[Asset] = []
        try:
            current_assets = SqlitePortfolioRepository(self.db_path).load_assets()
        except Exception:  # nosec B110
            pass

        if not current_assets and self.config_path.exists():
            try:
                data: Any = json.loads(self.config_path.read_text(encoding="utf-8"))
                items: list[dict[str, Any]] = (
                    data if isinstance(data, list) else data.get("assets", [])
                )
                current_assets = [Asset.from_dict(item) for item in items]
            except Exception:  # nosec B110
                pass

        return PortfolioAnalyticsEngine().build_dashboard_overview(
            asset_records=asset_records,
            portfolio_records=portfolio_records,
            current_assets=current_assets,
        )

    @staticmethod
    def _chart_to_b64(chart_path: Path) -> Markup:
        """Returns a Markup-wrapped base64 string for safe embedding in HTML."""
        if not chart_path.exists():
            return Markup("")
        return Markup(
            base64.b64encode(chart_path.read_bytes()).decode("utf-8")
        )  # nosec B704

    def _build_growth_scenarios(self) -> list[dict[str, Any]]:
        extractor = FinanceSQLExtractor(db_path=self.db_path)
        history = extractor.fetch_portfolio_history()
        initial_value: float = history[-1].total_value_eur if history else 0.0
        monthly_contribution: float = 500.0

        engine = ProjectionEngine()
        scenarios_def = [
            ("Conservative", 0.05),
            ("Moderate", 0.07),
            ("Aggressive", 0.09),
        ]
        result: list[dict[str, Any]] = []
        for name, rate in scenarios_def:
            scenario: GrowthProjectionScenario = engine.generate_scenario(
                name, initial_value, monthly_contribution, rate
            )
            milestones = [
                {
                    "year": yr,
                    "projected_value": scenario.milestones[yr].projected_value,
                    "inflation_adjusted_value": scenario.milestones[
                        yr
                    ].inflation_adjusted_value,
                    "compound_interest": scenario.milestones[yr].compound_interest,
                    "total_invested": scenario.milestones[yr].total_invested,
                }
                for yr in [10, 20, 30]
                if yr in scenario.milestones
            ]
            result.append(
                {
                    "name": name,
                    "annual_return_pct": rate * 100,
                    "milestones": milestones,
                }
            )
        return result

    def _build_template_context(
        self,
        overview: DashboardOverview,
        chart_valuation_b64: Markup,
        chart_class_b64: Markup,
        opportunities: list[dict[str, Any]],
        generated_at: str,
    ) -> dict[str, Any]:
        value_history = overview.portfolio_history.value_history
        period_start: str = value_history[0].date if value_history else "—"
        period_end: str = value_history[-1].date if value_history else "—"
        total_value_eur: float = value_history[-1].value if value_history else 0.0
        summaries: list[AssetPerformanceSummary] = overview.asset_summaries
        total_cost_basis_eur: float = sum(s.cost_basis_eur for s in summaries)
        total_roi_eur: float = sum(s.roi_eur for s in summaries)
        total_roi_percent: float = (
            (total_roi_eur / total_cost_basis_eur * 100.0)
            if total_cost_basis_eur > 0
            else 0.0
        )

        asset_dicts: list[dict[str, Any]] = [
            {
                "ticker": s.ticker,
                "name": s.name,
                "asset_type": s.asset_type,
                "latest_quantity": s.latest_quantity,
                "latest_value_eur": s.latest_value_eur,
                "cost_basis_eur": s.cost_basis_eur,
                "roi_eur": s.roi_eur,
                "roi_percent": s.roi_percent,
                "portfolio_share_percent": s.portfolio_share_percent,
            }
            for s in summaries
        ]

        class_totals: dict[str, float] = {}
        for s in summaries:
            key = s.asset_type.upper()
            class_totals[key] = class_totals.get(key, 0.0) + s.latest_value_eur
        composition: list[dict[str, Any]] = [
            {
                "asset_type": k,
                "value_eur": v,
                "share_percent": (
                    (v / total_value_eur * 100.0) if total_value_eur > 0 else 0.0
                ),
            }
            for k, v in sorted(class_totals.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "generated_at": generated_at,
            "period_start": period_start,
            "period_end": period_end,
            "total_value_eur": total_value_eur,
            "total_cost_basis_eur": total_cost_basis_eur,
            "total_roi_eur": total_roi_eur,
            "total_roi_percent": total_roi_percent,
            "max_drawdown_percent": overview.max_drawdown_percent,
            "top_growth_contributor": overview.top_growth_contributor,
            "asset_summaries": asset_dicts,
            "composition": composition,
            "chart_valuation_b64": chart_valuation_b64,
            "chart_class_b64": chart_class_b64,
            "opportunities": opportunities,
            "has_opportunities": len(opportunities) > 0,
            "growth_scenarios": self._build_growth_scenarios(),
        }

    def generate(self, open_browser: bool = True) -> Path:
        """Generates the HTML report and returns html_path."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html_path = self.output_dir / "portfolio_report.html"

        overview = self._build_overview()

        chart_exporter = PortfolioChartExporter()
        val_path = chart_exporter.export_portfolio_valuation_chart(overview)
        class_path = chart_exporter.export_asset_class_chart(overview)
        chart_valuation_b64 = self._chart_to_b64(val_path)
        chart_class_b64 = self._chart_to_b64(class_path)

        opportunities: list[dict[str, Any]] = []
        try:
            opportunities = SqliteOpportunityRepository(
                self.db_path
            ).load_latest_top_opportunities(limit=5)
        except Exception:  # nosec B110
            pass

        context = self._build_template_context(
            overview=overview,
            chart_valuation_b64=chart_valuation_b64,
            chart_class_b64=chart_class_b64,
            opportunities=opportunities,
            generated_at=generated_at,
        )

        template = self._jinja_env.get_template("report.html.j2")
        html_content = template.render(**context)

        html_path.write_text(html_content, encoding="utf-8")

        if open_browser:
            webbrowser.open(html_path.resolve().as_uri())

        return html_path
