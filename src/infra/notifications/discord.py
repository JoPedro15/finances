"""Infrastructure module for dispatching opportunity_evaluation
alerts to Discord webhooks.
"""

from __future__ import annotations

from pathlib import Path

from discord_webhook import DiscordEmbed, DiscordWebhook  # type: ignore[import-untyped]

from src.config import settings
from src.core.models import RebalanceRecommendation, RecommendationAction
from src.core.opportunity_evaluation.base import AssetScore
from src.utils.logger.logger import logger

COLOR_GREEN: int = 0x2ECC71
COLOR_RED: int = 0xE74C3C
COLOR_BLUE: int = 0x3498DB


def _format_action_emoji(action: RecommendationAction | None) -> str:
    """Returns visual emoji indicators for AI recommendation actions."""
    if action == RecommendationAction.BUY:
        return "🟢 BUY"
    if action == RecommendationAction.SELL:
        return "🔴 SELL"
    if action == RecommendationAction.HOLD:
        return "🟡 HOLD"
    return "⚪ N/A"


def send_discord_notification(
    ranked_assets: list[AssetScore],
    recommendations_map: dict[str, RebalanceRecommendation],
    total_portfolio_value: float,
    image_path: Path | None = None,
) -> bool:
    """Dispatches opportunity_evaluation summary, matrix, and
    action cards to Discord.
    """
    webhook_url: str | None = settings.discord_webhook_url
    if not webhook_url:
        logger.warning("Discord webhook URL is not configured in settings. Skipping.")
        return False

    try:
        webhook = DiscordWebhook(url=webhook_url, username="Project Finance Bot")

        # Main Portfolio & Decision Strategy Embed
        stock_weights: str = (
            f"Dip: `{settings.stock_weight_dip:.2f}` | "
            f"Fwd P/E: `{settings.stock_weight_forward_pe:.2f}` | "
            f"52w Range: `{settings.stock_weight_52w_range:.2f}` | "
            f"Gap: `{settings.stock_weight_allocation:.2f}`"
        )
        etf_weights: str = (
            f"Dip: `{settings.etf_weight_dip:.2f}` | "
            f"TER/Cost: `{settings.etf_weight_ter:.2f}` | "
            f"Gap: `{settings.etf_weight_allocation:.2f}`"
        )

        main_embed = DiscordEmbed(
            title="📊 Portfolio Rebalance & Decision Strategy Summary",
            description=(
                f"💰 **Total Portfolio Value:** `{total_portfolio_value:,.2f} EUR`\n"
                f"🎯 **Target Assets Evaluated:** `{len(ranked_assets)}`"
            ),
            color=f"{COLOR_BLUE:06x}",
        )

        main_embed.add_embed_field(
            name="⚖️ Active Decision Strategy Weights",
            value=(
                f"• **Stocks Formula:** {stock_weights}\n"
                f"• **ETFs Formula:** {etf_weights}"
            ),
            inline=False,
        )

        # Build Untruncated Decision Matrix Text
        hdr: str = (
            f"{'Rank':<4} {'Symbol':<10} {'Type':<6} "
            f"{'Price (€)':>9} {'Current %':>9} {'Target %':>8} "
            f"{'Score':>7} {'AI Action':<9}"
        )
        matrix_lines: list[str] = [
            "```text",
            hdr,
            "─" * 72,
        ]

        score_map: dict[str, AssetScore] = {s.symbol: s for s in ranked_assets}

        for rank, score in enumerate(ranked_assets, start=1):
            rec: RebalanceRecommendation | None = recommendations_map.get(score.symbol)
            act_str: str = rec.action.value.upper() if rec and rec.action else "N/A"

            matrix_lines.append(
                f"{rank:<4} "
                f"{score.symbol:<10} "
                f"{score.asset_type.value.upper():<6} "
                f"{0.0:>9.2f} "
                f"{0.0:>8.1f}% "
                f"{0.0:>7.1f}% "
                f"{score.total_score:>7.3f} "
                f"{act_str:<9}"
            )

        matrix_lines.append("```")
        main_embed.add_embed_field(
            name="📋 Investment Decision Matrix",
            value="\n".join(matrix_lines),
            inline=False,
        )

        webhook.add_embed(main_embed)

        # Generate Actionable Advisory Insights Cards (Matching Terminal Layout)
        active_recs: list[tuple[str, RebalanceRecommendation]] = [
            (sym, r)
            for sym, r in recommendations_map.items()
            if r.action in (RecommendationAction.BUY, RecommendationAction.SELL)
        ]

        if active_recs:
            for symbol, rec in active_recs:
                score_info: AssetScore | None = score_map.get(symbol)
                action_text: str = _format_action_emoji(rec.action)
                urgency_text: str = (
                    rec.urgency_level.value.upper() if rec.urgency_level else "N/A"
                )
                conf_text: str = f"{rec.confidence_score * 100:.0f}%"

                color_code: int = (
                    COLOR_GREEN if rec.action == RecommendationAction.BUY else COLOR_RED
                )

                card_embed = DiscordEmbed(
                    title=f"🔹 {symbol}",
                    color=f"{color_code:06x}",
                )

                header_info: str = (
                    f"**Action:** {action_text}  │  "
                    f"**Urgency:** `{urgency_text}`  │  "
                    f"**Confidence:** `{conf_text}`"
                )

                factor_lines: str = ""
                if score_info:
                    factor_lines = (
                        f"• **Factor Scores:**\n"
                        f"  - Dip Score: `{score_info.dip_score:.2f}`\n"
                        f"  - Valuation/Cost Score: `{score_info.cost_score:.2f}`\n"
                        f"  - Gap Score: `{score_info.allocation_score:.2f}`\n"
                        f"  - Quant Total: `{score_info.total_score:.3f}`"
                    )

                card_content: str = (
                    f"{header_info}\n"
                    f"─────────────────────────────────────────\n"
                    f"{factor_lines}\n"
                    f"─────────────────────────────────────────\n"
                    f"_{rec.reasoning}_"
                )

                card_embed.set_description(card_content)
                webhook.add_embed(card_embed)

        # Attach Allocation Chart Image if generated
        if image_path and image_path.exists():
            with open(image_path, "rb") as img_file:
                webhook.add_file(file=img_file.read(), filename=image_path.name)

        response = webhook.execute()
        if response.status_code in (200, 204):
            logger.success(
                "Successfully sent opportunity_evaluation report to Discord."
            )
            return True

        logger.error(
            f"Discord webhook failed ({response.status_code}): " f"{response.text}"
        )
        return False

    except Exception as err:
        logger.error(f"Failed to send Discord notification: {err}")
        return False
