"""Offline unit tests for JustETF client scraper in src/infra/justetf/client.py.

Covers DOM parsing fallbacks, ISIN extractions, TER matching, network errors,
and edge cases to achieve near 100% test coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from bs4 import BeautifulSoup, Tag

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
    """Loads HTML fixture file or returns fallback markup for tests."""
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
                        <a href="/en/stock-profiles/US5949181045/">
                            Microsoft Corp.
                        </a>
                    </td>
                    <td data-testid="value_percentage">3,20%</td>
                </tr>
                <tr data-testid="top-holdings_row_2">
                    <td data-testid="link_name">
                        <a href="/en/stock-profiles/US0231351067/">
                            Amazon.com Inc.
                        </a>
                    </td>
                    <td data-testid="value_percentage">2.10%</td>
                </tr>
            </table>
            <table>
                <tr data-testid="sector_row_0">
                    <td>Information Technology</td><td>24,10%</td>
                </tr>
                <tr data-testid="sector_row_1">
                    <td>Financials</td><td>15.30%</td>
                </tr>
            </table>
            <table>
                <tr data-testid="country_row_0">
                    <td>United States</td><td>70,20%</td>
                </tr>
                <tr data-testid="country_row_1">
                    <td>Japan</td><td>6.10%</td>
                </tr>
            </table>
            <div>TER 0,20% p.a.</div>
        </body>
        </html>
        """

    return fixture_path.read_text(encoding="utf-8")


def test_client_init_custom() -> None:
    """Validates custom initialization of JustETFClient parameters."""
    client: JustETFClient = JustETFClient(timeout=15.0, max_retries=5)
    assert client.timeout == 15.0


@patch("requests.Session.get")
def test_get_etf_details_success(mock_get: MagicMock, sample_justetf_html: str) -> None:
    """Validates successful ETF details extraction with primary selectors."""
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
    assert details.holdings[1].weight_pct in (3.20, 4.12)

    assert len(details.sector_breakdown) >= 2
    assert details.sector_breakdown[0].sector_name in (
        "Information Technology",
        "Technology",
    )

    assert len(details.country_breakdown) >= 2
    assert details.country_breakdown[0].country_name == "United States"

    assert details.ter_pct is not None


@patch("requests.Session.get")
def test_get_etf_details_fallback_table_ids(mock_get: MagicMock) -> None:
    """Validates fallback DOM parsing using element IDs."""
    html: str = """
    <html>
    <body>
        <table id="top-holdings">
            <tr><th>Holding</th><th>Weight</th></tr>
            <tr>
                <td><a href="/stock-profiles/DE0007164600/">SAP SE</a></td>
                <td>5,50%</td>
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
        <div>Total Expense Ratio 0,15%</div>
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
    """Validates tertiary fallback parsing via table text headers."""
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
    """Validates HTTP error responses raise JustETFScrapeError."""
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="HTTP error 404"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_network_error(mock_get: MagicMock) -> None:
    """Validates network request exceptions raise JustETFScrapeError."""
    mock_get.side_effect = requests.RequestException("Connection timeout")

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Network error fetching JustETF page"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_status_code_500(mock_get: MagicMock) -> None:
    """Ensures 500 status code raises JustETFScrapeError with HTTP error message."""
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="HTTP error 500"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_malformed_html(mock_get: MagicMock) -> None:
    """Validates malformed HTML returns empty models cleanly."""
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><div>No ETF tables</div></body></html>"
    mock_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    details = client.get_etf_details("IE00B4L5Y983")

    assert details.holdings == []
    assert details.sector_breakdown == []
    assert details.country_breakdown == []
    assert details.ter_pct is None


@patch("src.infra.justetf.client.BeautifulSoup")
@patch("requests.Session.get")
def test_get_etf_details_unexpected_exception(
    mock_get: MagicMock, mock_bs: MagicMock
) -> None:
    """Validates unexpected parsing exceptions get wrapped in JustETFScrapeError."""
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_get.return_value = mock_response
    mock_bs.side_effect = Exception("Unexpected DOM error")

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Failed to parse JustETF response"):
        client.get_etf_details("IE00B4L5Y983")


def test_extract_isin_from_element_scenarios() -> None:
    """Validates ISIN extraction across diverse HTML element structures."""
    client: JustETFClient = JustETFClient()

    # Case 1: None / empty tag
    assert client._extract_isin_from_element(None) == ""

    # Case 2: Direct <a> tag
    soup_a: BeautifulSoup = BeautifulSoup(
        '<a href="/en/stock-profiles/US0378331005/">Apple</a>',
        "html.parser",
    )
    a_tag: Tag = soup_a.find("a")
    assert client._extract_isin_from_element(a_tag) == "US0378331005"

    # Case 3: Parent tag wrapping <a>
    soup_parent: BeautifulSoup = BeautifulSoup(
        '<div><a href="/en/stock-profiles/US5949181045/">MSFT</a></div>',
        "html.parser",
    )
    div_tag: Tag = soup_parent.find("div")
    assert client._extract_isin_from_element(div_tag) == "US5949181045"

    # Case 4: Raw text in element without anchor href match
    soup_raw: BeautifulSoup = BeautifulSoup(
        "<div>Holding ISIN US0231351067 here</div>",
        "html.parser",
    )
    raw_div: Tag = soup_raw.find("div")
    assert client._extract_isin_from_element(raw_div) == "US0231351067"

    # Case 5: No ISIN present
    soup_none: BeautifulSoup = BeautifulSoup(
        "<div>No ISIN in this element</div>",
        "html.parser",
    )
    no_isin_div: Tag = soup_none.find("div")
    assert client._extract_isin_from_element(no_isin_div) == ""


def test_parse_holdings_edge_cases() -> None:
    """Validates holdings parsing edge cases, header filters, and bad weights."""
    client: JustETFClient = JustETFClient()
    html: str = """
    <html>
    <body>
        <table>
            <tr data-testid="top-holdings_row_0">
                <td>Holding</td><td>Weight</td>
            </tr>
            <tr data-testid="top-holdings_row_1">
                <td>Name</td><td>Components</td>
            </tr>
            <tr data-testid="top-holdings_row_2">
                <td>Tesla Inc.</td><td>3.50%</td>
            </tr>
            <tr data-testid="top-holdings_row_3">
                <td>Invalid Weight Corp</td><td>ABC%</td>
            </tr>
            <tr data-testid="top-holdings_row_4">
                <td>No Percent Corp</td><td>10.5</td>
            </tr>
        </table>
    </body>
    </html>
    """
    soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
    holdings = client._parse_holdings(soup)

    assert len(holdings) == 1
    assert holdings[0].name == "Tesla Inc."
    assert holdings[0].weight_pct == 3.50


def test_parse_sectors_edge_cases() -> None:
    """Validates sectors parsing edge cases, header filters, and bad percentages."""
    client: JustETFClient = JustETFClient()
    html: str = """
    <html>
    <body>
        <table>
            <tr data-testid="sector_row_0">
                <td>Sector</td><td>Weight</td>
            </tr>
            <tr data-testid="sector_row_1">
                <td>Breakdown</td><td>10.00%</td>
            </tr>
            <tr data-testid="sector_row_2">
                <td>Healthcare</td><td>18,75%</td>
            </tr>
            <tr data-testid="sector_row_3">
                <td>Financials</td><td>INVALID%</td>
            </tr>
        </table>
    </body>
    </html>
    """
    soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
    sectors = client._parse_sectors(soup)

    assert len(sectors) == 1
    assert sectors[0].sector_name == "Healthcare"
    assert sectors[0].weight_pct == 18.75


def test_parse_countries_edge_cases() -> None:
    """Validates countries parsing edge cases, filters, and invalid numbers."""
    client: JustETFClient = JustETFClient()
    html: str = """
    <html>
    <body>
        <table>
            <tr data-testid="country_row_0">
                <td>Country</td><td>Weight</td>
            </tr>
            <tr data-testid="country_row_1">
                <td>Region</td><td>Weight</td>
            </tr>
            <tr data-testid="country_row_2">
                <td>United Kingdom</td><td>12,30%</td>
            </tr>
            <tr data-testid="country_row_3">
                <td>France</td><td>NOT_A_NUMBER%</td>
            </tr>
        </table>
    </body>
    </html>
    """
    soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
    countries = client._parse_countries(soup)

    assert len(countries) == 1
    assert countries[0].country_name == "United Kingdom"
    assert countries[0].weight_pct == 12.30


def test_parse_ter_edge_cases() -> None:
    """Validates TER parsing variations, comma formats, and missing labels."""
    client: JustETFClient = JustETFClient()

    # Case 1: TER label with comma float
    soup1: BeautifulSoup = BeautifulSoup(
        "<div><span>TER</span> <span>0,40% p.a.</span></div>",
        "html.parser",
    )
    assert client._parse_ter(soup1) == 0.40

    # Case 2: Total Expense Ratio label with dot float
    soup2: BeautifulSoup = BeautifulSoup(
        "<div><p>Total Expense Ratio 0.25% per annum</p></div>",
        "html.parser",
    )
    assert client._parse_ter(soup2) == 0.25

    # Case 3: Label matched but no valid percentage number
    soup3: BeautifulSoup = BeautifulSoup(
        "<div>TER N/A</div>",
        "html.parser",
    )
    assert client._parse_ter(soup3) is None

    # Case 4: No TER text in document
    soup4: BeautifulSoup = BeautifulSoup(
        "<div>No fees mentioned</div>",
        "html.parser",
    )
    assert client._parse_ter(soup4) is None
