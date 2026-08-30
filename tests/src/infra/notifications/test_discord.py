"""Unit tests for src/infra/notifications/discord.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import settings
from src.core.models import (
    RebalanceRecommendation,
    RecommendationAction,
    UrgencyLevel,
)
from src.infra.notifications.discord import (
    send_discord_notification,
)


@pytest.fixture
def mock_asset_score() -> MagicMock:
    """Provides a mocked AssetScore instance."""
    score: MagicMock = MagicMock()
    score.symbol = "AAPL"
    score.asset_type.value = "stock"
    score.total_score = 0.8542
    score.dip_score = 0.50
    score.cost_score = 0.80
    score.allocation_score = 0.90
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
    with patch.object(settings, "discord_webhook_url", ""):
        result: bool = send_discord_notification([], {}, 10000.0)
        assert result is False


@patch("src.infra.notifications.discord.DiscordWebhook")
def test_send_discord_notification_success(
    mock_webhook_class: MagicMock,
    mock_asset_score: MagicMock,
    valid_recommendation: RebalanceRecommendation,
) -> None:
    """Validates successful webhook dispatch."""
    mock_webhook: MagicMock = MagicMock()
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_webhook.execute.return_value = mock_response
    mock_webhook_class.return_value = mock_webhook

    with patch.object(
        settings, "discord_webhook_url", "https://discord.com/api/webhooks/fake"
    ):
        result: bool = send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={"AAPL": valid_recommendation},
            total_portfolio_value=12500.50,
        )

        assert result is True
        mock_webhook.execute.assert_called_once()


@patch("src.infra.notifications.discord.DiscordWebhook")
def test_send_discord_notification_with_image_attachment(
    mock_webhook_class: MagicMock,
    mock_asset_score: MagicMock,
    tmp_path: Path,
) -> None:
    """Validates sending image attachments via webhook."""
    mock_webhook: MagicMock = MagicMock()
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_webhook.execute.return_value = mock_response
    mock_webhook_class.return_value = mock_webhook

    chart_img: Path = tmp_path / "allocation_chart.png"
    chart_img.write_bytes(b"fake_image_bytes")

    with patch.object(
        settings, "discord_webhook_url", "https://discord.com/api/webhooks/fake"
    ):
        result: bool = send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={},
            total_portfolio_value=1000.0,
            image_path=chart_img,
        )

        assert result is True
        mock_webhook.add_file.assert_called_once()


@patch("src.infra.notifications.discord.DiscordWebhook")
def test_send_discord_notification_failure_returns_false(
    mock_webhook_class: MagicMock,
    mock_asset_score: MagicMock,
) -> None:
    """Validates failure response status code returns False."""
    mock_webhook: MagicMock = MagicMock()
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_webhook.execute.return_value = mock_response
    mock_webhook_class.return_value = mock_webhook

    with patch.object(
        settings, "discord_webhook_url", "https://discord.com/api/webhooks/fake"
    ):
        result: bool = send_discord_notification(
            ranked_assets=[mock_asset_score],
            recommendations_map={},
            total_portfolio_value=1000.0,
        )
        assert result is False
