"""
Unit tests for JustETF client scraper in src/infra/justetf/client.py.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.exceptions import JustETFScrapeError
from src.infra.justetf.client import JustETFClient


@pytest.fixture
def sample_justetf_html() -> str:
    return """
    <html>
        <body>
            <table id="top-holdings" class="table">
                <tr><th>Name</th><th>Weight</th></tr>
                <tr><td>Microsoft Corp</td><td>8.1%</td></tr>
                <tr><td>Apple Inc</td><td>7.2%</td></tr>
            </table>
            <div id="sectors">
                <table>
                    <tr><td>Technology</td><td>30.5%</td></tr>
                    <tr><td>Financials</td><td>15.2%</td></tr>
                </table>
            </div>
            <div id="countries">
                <table>
                    <tr><td>United States</td><td>65.0%</td></tr>
                    <tr><td>Japan</td><td>6.0%</td></tr>
                </table>
            </div>
            <div><span>TER</span> <span>0.07%</span></div>
        </body>
    </html>
    """


@patch("requests.Session.get")
def test_get_etf_details_success(mock_get: MagicMock, sample_justetf_html: str) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = sample_justetf_html
    mock_get.return_value = mock_response

    client = JustETFClient()
    details = client.get_etf_details("IE00B4L5Y983")

    assert len(details.holdings) == 2
    assert details.holdings[0].name == "Microsoft Corp"
    assert details.holdings[0].weight_pct == 8.1
    assert len(details.sector_breakdown) == 2
    assert details.sector_breakdown[0].sector_name == "Technology"
    assert len(details.country_breakdown) == 2
    assert details.country_breakdown[0].country_name == "United States"
    assert details.ter_pct == 0.07


@patch("requests.Session.get")
def test_get_etf_details_http_error(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    client = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="HTTP error 404"):
        client.get_etf_details("INVALID_ISIN")


@patch("requests.Session.get")
def test_get_etf_details_network_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.RequestException("Connection refused")

    client = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Network error fetching JustETF page"):
        client.get_etf_details("IE00B4L5Y983")
