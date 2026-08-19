"""Unit tests for src/infra/notifications/discord.py.

Covers Discord webhook notification dispatching, embed color determination,
field formatting, reasoning truncation, test mode headers, and error handling.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.models import (
    RebalanceRecommendation,
    RecommendationAction,
    UrgencyLevel,
)
from src.infra.notifications.discord import (
    COLOR_BLUE,
    COLOR_GREEN,
    COLOR_RED,
    send_discord_notification,
)


@pytest.fixture
def mock_asset_score() -> MagicMock:
    """Provides a mocked AssetScore instance."""
    score: MagicMock = MagicMock()
    score.symbol = "AAPL"
    score.asset_type.value = "stock"
    score.total_score = 0.8542
    return score


@pytest.fixture
def valid_recommendation() -> RebalanceRecommendation:
    """Provides a valid RebalanceRecommendation instance."""
    return RebalanceRecommendation(
        action=RecommendationAction.BUY,
        urgency_level=UrgencyLevel.HIGH,
        confidence_score=0.90,
        reasoning="Strong growth potential.",
        target_allocation_pct=10.0,
        risk_score=2,
        valuation_score=8,
    )


def test_send_discord_notification_missing_webhook_returns_false() -> None:
    """Validates execution stops when webhook URL is missing."""
    with patch.dict("os.environ", {}, clear=True):
        result: bool = send_discord_notification([], {}, 10000.0)
        assert result is False


@patch("src.infra.notifications.discord.requests.post")
def test_send_discord_notification_success_green_embed(
    mock_post: MagicMock,
    mock_asset_score: MagicMock,
    valid_recommendation: RebalanceRecommendation,
) -> None:
    """Validates successful webhook dispatch with green embed."""
    mock_response: MagicMock = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    env_vars: dict[str, str] = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/fake"
    }
    with patch.dict("os.environ", env_vars):
        result: bool = send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={"AAPL": valid_recommendation},
            total_portfolio_value=12500.50,
        )

        assert result is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload: dict[str, Any] = kwargs["json"]
        assert payload["embeds"][0]["color"] == COLOR_GREEN


@patch("src.infra.notifications.discord.requests.post")
def test_send_discord_notification_sell_action_red_embed(
    mock_post: MagicMock,
    mock_asset_score: MagicMock,
) -> None:
    """Validates red embed color selected when SELL recommendation exists."""
    mock_response: MagicMock = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    sell_rec: RebalanceRecommendation = RebalanceRecommendation(
        action=RecommendationAction.SELL,
        urgency_level=UrgencyLevel.MEDIUM,
        confidence_score=0.80,
        reasoning="Overvalued position.",
        target_allocation_pct=0.0,
        risk_score=4,
        valuation_score=3,
    )

    env_vars: dict[str, str] = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/fake"
    }
    with patch.dict("os.environ", env_vars):
        result: bool = send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={"AAPL": sell_rec},
            total_portfolio_value=5000.0,
        )

        assert result is True
        _, kwargs = mock_post.call_args
        payload: dict[str, Any] = kwargs["json"]
        assert payload["embeds"][0]["color"] == COLOR_RED


@patch("src.infra.notifications.discord.requests.post")
def test_send_discord_notification_default_blue_embed_and_none_rec(
    mock_post: MagicMock,
    mock_asset_score: MagicMock,
) -> None:
    """Validates default blue embed color and fallback formatting."""
    mock_response: MagicMock = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    env_vars: dict[str, str] = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/fake"
    }
    with patch.dict("os.environ", env_vars):
        result: bool = send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={},
            total_portfolio_value=5000.0,
        )

        assert result is True
        _, kwargs = mock_post.call_args
        payload: dict[str, Any] = kwargs["json"]
        assert payload["embeds"][0]["color"] == COLOR_BLUE
        field_val: str = payload["embeds"][0]["fields"][0]["value"]
        assert "**Action:** `HOLD`" in field_val
        assert "*Quantitative evaluation only.*" in field_val


@patch("src.infra.notifications.discord.requests.post")
def test_send_discord_notification_truncates_long_reasoning(
    mock_post: MagicMock,
    mock_asset_score: MagicMock,
) -> None:
    """Validates long reasoning string truncation to 150 characters."""
    mock_response: MagicMock = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    long_reasoning: str = "A" * 200
    long_rec: RebalanceRecommendation = RebalanceRecommendation(
        action=RecommendationAction.HOLD,
        urgency_level=UrgencyLevel.LOW,
        confidence_score=0.50,
        reasoning=long_reasoning,
        target_allocation_pct=5.0,
        risk_score=5,
        valuation_score=5,
    )

    env_vars: dict[str, str] = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/fake"
    }
    with patch.dict("os.environ", env_vars):
        send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={"AAPL": long_rec},
            total_portfolio_value=1000.0,
        )

        _, kwargs = mock_post.call_args
        payload: dict[str, Any] = kwargs["json"]
        field_val: str = payload["embeds"][0]["fields"][0]["value"]
        assert "A" * 147 + "..." in field_val


@patch("src.infra.notifications.discord.requests.post")
def test_send_discord_notification_test_mode_prefix(
    mock_post: MagicMock,
    mock_asset_score: MagicMock,
) -> None:
    """Validates test mode header inclusion when DISCORD_TEST_MODE is true."""
    mock_response: MagicMock = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    env_vars: dict[str, str] = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/fake",
        "DISCORD_TEST_MODE": "true",
    }
    with patch.dict("os.environ", env_vars):
        send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={},
            total_portfolio_value=1000.0,
        )

        _, kwargs = mock_post.call_args
        payload: dict[str, Any] = kwargs["json"]
        assert "[TEST MESSAGE - AUTOMATED TEST]" in payload["content"]


@patch("src.infra.notifications.discord.requests.post")
def test_send_discord_notification_request_failure_returns_false(
    mock_post: MagicMock,
    mock_asset_score: MagicMock,
) -> None:
    """Validates request exception handling returns False."""
    mock_post.side_effect = requests.RequestException("Network Error")

    env_vars: dict[str, str] = {
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/fake"
    }
    with patch.dict("os.environ", env_vars):
        result: bool = send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={},
            total_portfolio_value=1000.0,
        )
        assert result is False
