"""
Offline unit tests for JustETF client scraper in src/infra/justetf/client.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.exceptions import JustETFScrapeError
from src.infra.justetf.client import JustETFClient


@pytest.fixture
def sample_justetf_html() -> str:
    fixture_path = (
        Path(__file__).parent.parent.parent
        / "fixtures"
        / "justetf"
        / "sample_etf_profile.html"
    )
    return fixture_path.read_text(encoding="utf-8")


@patch("requests.Session.get")
def test_get_etf_details_success(mock_get: MagicMock, sample_justetf_html: str) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = sample_justetf_html
    mock_get.return_value = mock_response

    client = JustETFClient()
    details = client.get_etf_details("IE00B4L5Y983")

    assert len(details.holdings) == 3
    assert details.holdings[0].name == "Apple Inc."
    assert details.holdings[0].weight_pct == 4.85

    assert len(details.sector_breakdown) == 2
    assert details.sector_breakdown[0].sector_name == "Information Technology"
    assert details.sector_breakdown[0].weight_pct == 24.10

    assert len(details.country_breakdown) == 2
    assert details.country_breakdown[0].country_name == "United States"
    assert details.country_breakdown[0].weight_pct == 70.20

    assert details.ter_pct == 0.20


@patch("requests.Session.get")
def test_get_etf_details_http_error(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    client = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="HTTP error 500"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_network_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.RequestException("Connection refused")

    client = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Network error fetching JustETF page"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_timeout_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.Timeout("Connection timed out")

    client = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Network error fetching JustETF page"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_malformed_html(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><div>Broken markup</div></body></html>"
    mock_get.return_value = mock_response

    client = JustETFClient()
    details = client.get_etf_details("IE00B4L5Y983")

    assert details.holdings == []
    assert details.sector_breakdown == []
    assert details.country_breakdown == []
    assert details.ter_pct is None
