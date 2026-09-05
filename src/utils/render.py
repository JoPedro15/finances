"""Shared HTML rendering utilities for report generation."""

from __future__ import annotations

from pathlib import Path

import jinja2

_TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / "templates"

_jinja_env: jinja2.Environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(["html"]),
)


def render_html(
    template_name: str,
    context: dict,
    html_path: Path,
) -> None:
    """Renders a Jinja2 template to HTML, overwriting existing file."""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    template = _jinja_env.get_template(template_name)
    html_path.write_text(template.render(**context), encoding="utf-8")
