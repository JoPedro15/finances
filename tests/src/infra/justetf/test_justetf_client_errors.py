"""Unit tests targeting network exceptions and HTML parsing edge cases in
JustETFClient.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.exceptions import JustETFScrapeError
from src.infra.justetf.client import JustETFClient


@patch("requests.Session.get")
def test_get_etf_details_http_error(mock_session_get: MagicMock) -> None:
    """Validates get_etf_details raises JustETFScrapeError on network failures."""
    mock_session_get.side_effect = requests.RequestException("Connection timeout")
    client: JustETFClient = JustETFClient()

    with pytest.raises(JustETFScrapeError, match="Network error fetching JustETF page"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_status_code_error(mock_session_get: MagicMock) -> None:
    """Validates get_etf_details raises JustETFScrapeError when response status
    code is not 200.
    """
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 404
    mock_session_get.return_value = mock_response

    client: JustETFClient = JustETFClient()

    with pytest.raises(JustETFScrapeError, match="HTTP error 404"):
        client.get_etf_details("IE00B4L5Y983")


@patch("requests.Session.get")
def test_get_etf_details_malformed_html(mock_session_get: MagicMock) -> None:
    """Validates get_etf_details handles HTML missing expected DOM structures
    cleanly.
    """
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><div>No relevant ETF tables</div></body></html>"
    mock_session_get.return_value = mock_response

    client: JustETFClient = JustETFClient()
    details = client.get_etf_details("IE00B4L5Y983")

    assert details is not None
    assert details.holdings == []
    assert details.sector_breakdown == []
    assert details.country_breakdown == []
    assert details.ter_pct is None


@patch("src.infra.justetf.client.JustETFClient._parse_holdings")
@patch("requests.Session.get")
def test_get_etf_details_parsing_error(
    mock_session_get: MagicMock, mock_parse_holdings: MagicMock
) -> None:
    """Validates get_etf_details catches and wraps unexpected DOM parsing
    failures.
    """
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"
    mock_session_get.return_value = mock_response
    mock_parse_holdings.side_effect = Exception("Unexpected DOM error")

    client: JustETFClient = JustETFClient()
    with pytest.raises(JustETFScrapeError, match="Failed to parse JustETF response"):
        client.get_etf_details("IE00B4L5Y983")
