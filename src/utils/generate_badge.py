"""Utility module to parse coverage.xml and generate a clean,
vibrant green SVG badge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET  # type: ignore[import-untyped]


def generate_coverage_badge(
    xml_path: Path | str = "coverage.xml",
    output_path: Path | str = "coverage.svg",
) -> None:
    """Parses coverage.xml and outputs a custom vibrant green SVG badge."""
    xml_file: Path = Path(xml_path)
    out_file: Path = Path(output_path)

    coverage_pct: float = 0.0
    if xml_file.exists():
        try:
            tree: Any = ET.parse(xml_file)
            root: Any = tree.getroot()
            line_rate_str: str | None = root.get("line-rate")
            if line_rate_str:
                coverage_pct = float(line_rate_str) * 100.0
        except Exception as err:
            print(f"Error parsing coverage.xml: {err}")

    pct_text: str = f"{coverage_pct:.2f}%"
    badge_color: str = "#44cc11"

    svg_lines: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="104" '
        f'height="20" role="img" aria-label="coverage: {pct_text}">',
        '  <linearGradient id="s" x2="0" y2="100%">',
        '    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>',
        '    <stop offset="1" stop-opacity=".1"/>',
        "  </linearGradient>",
        '  <clipPath id="r">',
        '    <rect width="104" height="20" rx="3" fill="#fff"/>',
        "  </clipPath>",
        '  <g clip-path="url(#r)">',
        '    <rect width="63" height="20" fill="#555"/>',
        f'    <rect x="63" width="41" height="20" fill="{badge_color}"/>',
        '    <rect width="104" height="20" fill="url(#s)"/>',
        "  </g>",
        '  <g fill="#fff" text-anchor="middle" '
        'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">',
        '    <text x="31.5" y="15" fill="#010101" ' 'fill-opacity=".3">coverage</text>',
        '    <text x="31.5" y="14">coverage</text>',
        f'    <text x="82.5" y="15" fill="#010101" '
        f'fill-opacity=".3">{pct_text}</text>',
        f'    <text x="82.5" y="14">{pct_text}</text>',
        "  </g>",
        "</svg>",
    ]
    svg_content: str = "\n".join(svg_lines)

    out_file.write_text(svg_content, encoding="utf-8")
    print(f"Generated vibrant green badge for {pct_text} at {out_file}")


if __name__ == "__main__":
    generate_coverage_badge()
