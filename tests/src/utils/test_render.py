"""Unit tests for src/utils/render.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.render import render_html

# ==============================================================================
# render_html
# ==============================================================================


def test_render_html_creates_file(tmp_path: Path) -> None:
    """Rendered HTML file is written to the given path."""
    out = tmp_path / "out.html"
    render_html("quality_report.html.j2", _quality_ctx(), out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_html_content_contains_context_values(tmp_path: Path) -> None:
    """Template variables are interpolated in the output."""
    out = tmp_path / "out.html"
    render_html("quality_report.html.j2", _quality_ctx(), out)
    content = out.read_text(encoding="utf-8")
    assert "2026-01-01 12:00:00" in content
    assert "EUNL.DE" in content
    assert "Tier A" in content


def test_render_html_overwrites_existing_file(tmp_path: Path) -> None:
    """Calling render_html twice overwrites the previous file."""
    out = tmp_path / "out.html"
    out.write_text("old content", encoding="utf-8")
    render_html("quality_report.html.j2", _quality_ctx(), out)
    assert "old content" not in out.read_text(encoding="utf-8")


def test_render_html_creates_parent_dirs(tmp_path: Path) -> None:
    """Missing parent directories are created automatically."""
    out = tmp_path / "a" / "b" / "c" / "out.html"
    render_html("quality_report.html.j2", _quality_ctx(), out)
    assert out.exists()


def test_render_html_opportunity_template(tmp_path: Path) -> None:
    """Opportunity template renders without error and contains key labels."""
    out = tmp_path / "opp.html"
    render_html("opportunity_report.html.j2", _opportunity_ctx(), out)
    content = out.read_text(encoding="utf-8")
    assert "LLY" in content
    assert "BUY" in content


def test_render_html_unknown_template_raises(tmp_path: Path) -> None:
    """TemplateNotFound is raised for a non-existent template."""
    import jinja2

    out = tmp_path / "out.html"
    with pytest.raises(jinja2.TemplateNotFound):
        render_html("does_not_exist.html.j2", {}, out)


def test_render_html_etf_asset_rendered(tmp_path: Path) -> None:
    """ETF branch in quality template renders TER and holdings."""
    out = tmp_path / "out.html"
    render_html("quality_report.html.j2", _quality_ctx(asset_type="ETF"), out)
    content = out.read_text(encoding="utf-8")
    assert "0.20%" in content
    assert "NVDA" in content


def test_render_html_stock_asset_rendered(tmp_path: Path) -> None:
    """STOCK branch in quality template renders P/E and beta."""
    out = tmp_path / "out.html"
    render_html("quality_report.html.j2", _quality_ctx(asset_type="STOCK"), out)
    content = out.read_text(encoding="utf-8")
    assert "Trailing P/E" in content
    assert "Beta" in content


def test_render_html_empty_assets_list(tmp_path: Path) -> None:
    """Template renders without error when assets list is empty."""
    out = tmp_path / "out.html"
    ctx = {"generated_at": "2026-01-01 00:00:00", "assets": []}
    render_html("quality_report.html.j2", ctx, out)
    assert out.exists()


def test_render_html_tier_a_css_class(tmp_path: Path) -> None:
    """Tier A assets use the tier-a CSS class."""
    out = tmp_path / "out.html"
    render_html("quality_report.html.j2", _quality_ctx(), out)
    assert "tier-a" in out.read_text(encoding="utf-8")


def test_render_html_tier_b_css_class(tmp_path: Path) -> None:
    """Tier B assets use the tier-b CSS class."""
    out = tmp_path / "out.html"
    ctx = _quality_ctx()
    ctx["assets"][0]["tier"] = "Tier B"
    render_html("quality_report.html.j2", ctx, out)
    assert "tier-b" in out.read_text(encoding="utf-8")


def test_render_html_tier_c_card_class(tmp_path: Path) -> None:
    """Tier C assets use the tier-c-card CSS class on the card."""
    out = tmp_path / "out.html"
    ctx = _quality_ctx()
    ctx["assets"][0]["tier"] = "Tier C"
    render_html("quality_report.html.j2", ctx, out)
    assert "tier-c-card" in out.read_text(encoding="utf-8")


# ==============================================================================
# Helpers
# ==============================================================================


def _quality_ctx(asset_type: str = "ETF") -> dict:
    asset: dict = {
        "name": "iShares Core MSCI World",
        "symbol": "EUNL.DE",
        "asset_type": asset_type,
        "tier": "Tier A",
        "score": 82,
        "valuation_status": "Fair",
        "bull_case": ["Low cost", "Broad diversification"],
        "bear_case": ["USD concentration"],
    }
    if asset_type == "ETF":
        asset.update(
            {
                "ter_str": "0.20%",
                "holdings_str": "NVDA (5.2%), AAPL (4.8%)",
                "sectors_str": "Technology (36.2%)",
                "countries_str": "US (70.3%)",
            }
        )
    else:
        asset.update(
            {
                "tr_str": "29.2",
                "fw_str": "14.9",
                "peg_str": "0.58",
                "pb_str": "24.29",
                "div_str": "0.43%",
                "beta_str": "2.22",
                "margin_str": "63.7%",
                "rev_str": "105.9%",
                "earn_str": "127.8%",
                "low_str": "164.27 EUR",
                "peak_str": "236.54 EUR",
            }
        )
    return {"generated_at": "2026-01-01 12:00:00", "assets": [asset]}


def _opportunity_ctx() -> dict:
    return {
        "generated_at": "2026-01-01 12:00:00",
        "total_value_eur": 2600.0,
        "has_ai": True,
        "assets": [
            {
                "rank": 1,
                "symbol": "LLY",
                "asset_type": "STOCK",
                "price_eur": 989.02,
                "current_pct": 0.0,
                "target_pct": 4.0,
                "score": 0.824,
                "ai_action": "BUY",
                "ai_urgency": "HIGH",
                "ai_conf": "91%",
            }
        ],
        "advisories": [],
        "w_stock_dip": 0.35,
        "w_stock_pe": 0.35,
        "w_stock_52w": 0.15,
        "w_stock_gap": 0.15,
        "w_etf_dip": 0.60,
        "w_etf_ter": 0.20,
        "w_etf_gap": 0.20,
        "w_sector_pen": 0.30,
        "w_country_pen": 0.20,
    }
