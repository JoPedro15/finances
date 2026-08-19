"""Offline unit tests for JustETF client scraper in src/infra/justetf/client.py
covering DOM parsing fallbacks, ISIN extractions, TER matching, network errors,
and edge cases.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.exceptions import JustETFScrapeError
from src.infra.justetf.client import JustETFClient


def _find_tests_dir(start_path: Path) -> Path:
    """Recursively locates the tests directory from a given path."""
    current: Path = start_path.resolve()
    while current.name != "tests" and current.parent != current:
        current = current.parent
    return current


@pytest.fixture
def sample_justetf_html() -> str:
    """Loads HTML fixture file or returns fallback markup for offline test execution."""
    tests_dir: Path = _find_tests_dir(Path(__file__))
    fixture_path: Path = tests_dir / "fixtures" / "justetf" / "sample_etf_profile.html"

    if not fixture_path.exists():
        return """
        <html>
        <body>
            <table>
                <tr data-testid="top-holdings_row_0">
                    <td data-testid="link_name">
                        <a href="/en/stock-profiles/US0378331005/">Apple Inc.</a>
                    </td>
                    <td data-testid="value_percentage">4.85%</td>
                </tr>
                <tr data-testid="top-holdings_row_1">
                    <td data-testid="link_name">
                        <a href="/en/stock-profiles/US5949181045/">Microsoft Corp.</a>
                    </td>
                    <td data-testid="value_percentage">3.20%</td>
                </tr>
                <tr data-testid="top-holdings_row_2">
                    <td data-testid="link_name">
                        <a href="/en/stock-profiles/US0231351067/">Amazon.com Inc.</a>
                    </td>
                    <td data-testid="value_percentage">2.10%</td>
                </tr>
            </table>
            <table>
                <tr data-testid="sector_row_0">
                    <td>Information Technology</td><td>24.10%</td>
                </tr>
                <tr data-testid="sector_row_1"><td>Financials</td><td>15.30%</td></tr>
            </table>
            <table>
                <tr data-testid="country_row_0">
                    <td>United States</td><td>70.20%</td>
                </tr>
                <tr data-testid="country_row_1"><td>Japan</td><td>6.10%</td></tr>
            </table>
            <div>TER 0.20% p.a.</div>
        </body>
        </html>
        """

    return fixture_path.read_text(encoding="utf-8")


@patch("requests.Session.get")
def test_get_etf_details_success(mock_get: MagicMock, sample_justetf_html: str) -> None:
    """Validates successful ETF details extraction using primary data-testid
    selectors.
    """
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = sample_justetf_html
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    details = client.get_etf_details("IE00B4L5Y983")

    assert len(details.holdings) == 3
    assert details.holdings[0].name == "Apple Inc."
    assert details.holdings[0].isin in ("US0378331005", "")
    assert details.holdings[0].weight_pct == 4.85

    assert len(details.sector_breakdown) == 2
    assert details.sector_breakdown[0].sector_name == "Information Technology"
    assert details.sector_breakdown[0].weight_pct == 24.10

    assert len(details.country_breakdown) == 2
    assert details.country_breakdown[0].country_name == "United States"
    assert details.country_breakdown[0].weight_pct == 70.20

    assert details.ter_pct == 0.20


@patch("requests.Session.get")
def test_get_etf_details_fallback_table_ids(mock_get: MagicMock) -> None:
    """Validates secondary DOM fallback parsing via table and div element IDs."""
    html: str = """
    <html>
    <body>
        <table id="top-holdings">
            <tr><th>Holding</th><th>Weight</th></tr>
            <tr>
                <td><a href="/stock-profiles/DE0007164600/">SAP SE</a></td>
                <td>5.50%</td>
            </tr>
        </table>
        <div id="sectors">
            <table>
                <tr><td>Software</td><td>40.00%</td></tr>
            </table>
        </div>
        <div id="countries">
            <table>
                <tr><td>Germany</td><td>100.00%</td></tr>
            </table>
        </div>
        <div>Total Expense Ratio 0.15%</div>
    </body>
    </html>
    """
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    details = client.get_etf_details("DE0007164600")

    assert len(details.holdings) == 1
    assert details.holdings[0].name == "SAP SE"
    assert details.holdings[0].isin == "DE0007164600"
    assert details.holdings[0].weight_pct == 5.50

    assert len(details.sector_breakdown) == 1
    assert details.sector_breakdown[0].sector_name == "Software"
    assert len(details.country_breakdown) == 1
    assert details.country_breakdown[0].country_name == "Germany"
    assert details.ter_pct == 0.15


@patch("requests.Session.get")
def test_get_etf_details_fallback_header_text(mock_get: MagicMock) -> None:
    """Validates tertiary DOM fallback parsing via plain table text content matching."""
    html: str = """
    <html>
    <body>
        <table>
            <tr><td>Top Holdings</td><td>Weight</td></tr>
            <tr><td>NVIDIA Corp.</td><td>8.20%</td></tr>
        </table>
        <table>
            <tr><td>Sector Breakdown</td><td>Weight</td></tr>
            <tr><td>Semiconductors</td><td>50.00%</td></tr>
        </table>
        <table>
            <tr><td>Region Breakdown</td><td>Weight</td></tr>
            <tr><td>Taiwan</td><td>30.00%</td></tr>
        </table>
    </body>
    </html>
    """
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    details = client.get_etf_details("US67066G1040")

    assert len(details.holdings) == 1
    assert details.holdings[0].name == "NVIDIA Corp."
    assert details.holdings[0].weight_pct == 8.20
    assert details.sector_breakdown[0].sector_name == "Semiconductors"
    assert details.country_breakdown[0].country_name == "Taiwan"


@patch("requests.Session.get")
def test_get_etf_details_http_error(mock_get: MagicMock) -> None:
    """Validates that non-200 HTTP response codes raise JustETFScrapeError."""
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="HTTP error 500"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_network_error(mock_get: MagicMock) -> None:
    """Validates that network connection errors raise JustETFScrapeError."""
    mock_get.side_effect = requests.RequestException("Connection refused")

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Network error fetching JustETF page"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_timeout_error(mock_get: MagicMock) -> None:
    """Validates that request timeout errors raise JustETFScrapeError."""
    mock_get.side_effect = requests.Timeout("Connection timed out")

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Network error fetching JustETF page"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_malformed_html(mock_get: MagicMock) -> None:
    """Validates that malformed HTML returns empty models without throwing unexpected
    exceptions.
    """
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><div>Broken markup</div></body></html>"
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    details = client.get_etf_details("IE00B4L5Y983")

    assert details.holdings == []
    assert details.sector_breakdown == []
    assert details.country_breakdown == []
    assert details.ter_pct is None


@patch("src.infra.justetf.client.BeautifulSoup")
@patch("requests.Session.get")
def test_get_etf_details_parsing_unexpected_exception(
    mock_get: MagicMock, mock_bs: MagicMock
) -> None:
    """Validates that unhandled parsing errors get re-wrapped in JustETFScrapeError."""
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_get.return_value = mock_response

    mock_bs.side_effect = AttributeError("Unexpected DOM tree structure")

    client: JustETFClient = JustETFClient()
    with pytest.raises(
        JustETFScrapeError, match="Failed to parse JustETF response for ISIN"
    ):
        client.get_etf_details("IE00B4L5Y983")
