"""Discord webhook notification service for investment recommendations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from src.core.models import (
    RebalanceRecommendation,
    RecommendationAction,
    UrgencyLevel,
)
from src.utils.logger.logger import logger

# Discord Embed Color Constants
COLOR_BLUE: int = 3447003  # Default / Neutral
COLOR_RED: int = 15548997  # SELL / Critical
COLOR_GREEN: int = 5763719  # BUY / HIGH Urgency


def send_discord_notification(
    ranked_assets: list[Any],
    recommendations_map: dict[str, RebalanceRecommendation],
    total_portfolio_value: float,
    image_path: Path | None = None,
) -> bool:
    """Sends formatted rebalance recommendations, AI insights,
    and optional allocation charts to a Discord webhook.
    """
    webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL is not set. Skipping Discord notification.")
        return False

    # Determine embed color based on recommendation priority
    embed_color: int = COLOR_BLUE
    has_sell: bool = False
    has_high_buy: bool = False

    for item_rec in recommendations_map.values():
        if item_rec.action == RecommendationAction.SELL:
            has_sell = True
        elif (
            item_rec.action == RecommendationAction.BUY
            and item_rec.urgency_level == UrgencyLevel.HIGH
        ):
            has_high_buy = True

    if has_sell:
        embed_color = COLOR_RED
    elif has_high_buy:
        embed_color = COLOR_GREEN

    fields: list[dict[str, Any]] = []
    for score in ranked_assets:
        symbol: str = str(score.symbol)
        rec: RebalanceRecommendation | None = recommendations_map.get(symbol)

        action_str: str = rec.action.value if rec and rec.action else "HOLD"
        urgency_str: str = (
            rec.urgency_level.value if rec and rec.urgency_level else "LOW"
        )
        conf_pct: float = float(rec.confidence_score) * 100.0 if rec else 0.0
        reasoning: str = str(rec.reasoning) if rec else "Quantitative evaluation only."

        # Truncate reasoning for Discord embed field limits
        if len(reasoning) > 150:
            reasoning = reasoning[:147] + "..."

        field_value: str = (
            f"**Action:** `{action_str}` | **Urgency:** `{urgency_str}`\n"
            f"**Confidence:** `{conf_pct:.0f}%` | "
            f"**Quant Score:** `{score.total_score:.4f}`\n"
            f"*{reasoning}*"
        )

        fields.append(
            {
                "name": f"🔹 {symbol} ({score.asset_type.value.upper()})",
                "value": field_value,
                "inline": False,
            }
        )

    # Check if running in test mode to inject disclaimer
    is_test_mode: bool = os.getenv("DISCORD_TEST_MODE", "").lower() == "true"
    test_prefix: str = (
        "🧪 **[TEST MESSAGE - AUTOMATED TEST]**\n" if is_test_mode else ""
    )

    payload: dict[str, Any] = {
        "content": (
            f"{test_prefix}"
            f"📊 **Portfolio Rebalance & AI Advisory Alert**\n"
            f"💰 **Total Value:** `{total_portfolio_value:,.2f} EUR`"
        ),
        "embeds": [
            {
                "title": "Investment Decision Matrix",
                "color": embed_color,
                "fields": fields[:25],  # Discord limit per embed
                "footer": {"text": "Project Finance Automated Monitoring System"},
            }
        ],
    }

    try:
        # If an image path is provided and exists, attach it via multipart/form-data
        if image_path and image_path.exists():
            payload["embeds"][0]["image"] = {"url": f"attachment://{image_path.name}"}
            with open(image_path, "rb") as f:
                files: dict[str, Any] = {"file0": (image_path.name, f, "image/png")}
                data: dict[str, str] = {"payload_json": json.dumps(payload)}
                response: requests.Response = requests.post(
                    webhook_url, data=data, files=files, timeout=15
                )
        else:
            response = requests.post(webhook_url, json=payload, timeout=10)

        response.raise_for_status()
        logger.success("Successfully dispatched notification to Discord.")
        return True
    except Exception as err:
        logger.error(f"Failed to dispatch Discord notification: {err}")
        return False
