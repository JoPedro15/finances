"""CLI module for evaluating investment targets and AI portfolio rebalancing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import DATA_DIR
from src.core.decision.base import AssetScore
from src.core.decision.engine import PortfolioDecisionEngine
from src.core.exceptions import GeminiAPIError, GeminiAuthError
from src.core.models import (
    Asset,
    ETFDetails,
    Quotation,
    RebalanceRecommendation,
    RecommendationAction,
    StockDetails,
    UrgencyLevel,
)
from src.core.providers import ETFProvider, StockProvider
from src.infra.ai.client import GeminiClient
from src.infra.notifications.discord import send_discord_notification
from src.utils.logger.logger import logger

app = typer.Typer(help="Investment decision engine and AI rebalancing CLI commands.")
console = Console()


def load_json_data(file_path: Path) -> list[dict[str, Any]]:
    """Loads and normalizes JSON data containing asset lists or holdings."""
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return []

    try:
        with open(file_path, encoding="utf-8") as file:
            data: Any = json.load(file)
    except Exception as err:
        logger.error(f"Failed to read JSON file '{file_path}': {err}")
        return []

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and "assets" in data:
        raw_assets: Any = data.get("assets")
        if isinstance(raw_assets, list):
            return [item for item in raw_assets if isinstance(item, dict)]

    return []


def calculate_current_allocations(
    portfolio_items: list[dict[str, Any]],
    stock_provider: StockProvider,
) -> tuple[dict[str, float], float]:
    """Fetches live prices for active holdings and computes real allocation %."""
    holdings_value_map: dict[str, float] = {}
    total_portfolio_value: float = 0.0

    for item in portfolio_items:
        symbol: str = str(item.get("yahoo_ticker") or item.get("symbol") or "").strip()
        quantity: float = float(item.get("quantity", 0.0))

        if not symbol or quantity <= 0.0:
            continue

        dummy_asset: Asset = Asset(
            name=symbol,
            isin=str(item.get("isin", "")),
            yahoo_ticker=symbol,
            quantity=quantity,
            average_buy_price=float(item.get("averageBuyPrice", 0.0)),
            asset_type=str(item.get("asset_type", "stock")).lower(),
        )

        quote: Quotation | None = stock_provider.get_price(dummy_asset)
        current_price: float = quote.price if quote else 0.0

        if current_price <= 0.0:
            logger.warning(
                f"Could not retrieve valid price for holding '{symbol}'. "
                "Skipping position value calculation."
            )
            continue

        position_value: float = quantity * current_price
        holdings_value_map[symbol] = position_value
        total_portfolio_value += position_value

    if total_portfolio_value <= 0.0:
        return {}, 0.0

    allocation_pct_map: dict[str, float] = {
        symbol: (val / total_portfolio_value) * 100.0
        for symbol, val in holdings_value_map.items()
    }

    return allocation_pct_map, total_portfolio_value


def enrich_target_asset(
    target: dict[str, Any],
    current_alloc_pct: float,
    stock_provider: StockProvider,
    etf_provider: ETFProvider,
) -> dict[str, Any]:
    """Enriches wishlist asset with real-time market data and metrics."""
    symbol: str = str(target.get("yahoo_ticker") or target.get("symbol") or "").strip()
    asset_type: str = str(target.get("type") or target.get("asset_type") or "").upper()

    if not symbol or not asset_type:
        raise ValueError(f"Missing symbol or type for target asset: {target}")

    dummy_asset: Asset = Asset(
        name=symbol,
        isin=str(target.get("isin", "")),
        yahoo_ticker=symbol,
        quantity=0.0,
        average_buy_price=0.0,
        asset_type=asset_type.lower(),
    )

    quote: Quotation | None = stock_provider.get_price(dummy_asset)
    current_price: float = quote.price if quote else 0.0

    if current_price <= 0.0:
        logger.warning(f"Live market price unavailable for target '{symbol}'.")

    stock_details: StockDetails | None = stock_provider.get_details(dummy_asset)

    peak_price: float = (
        stock_details.fifty_two_week_high
        if stock_details and stock_details.fifty_two_week_high
        else current_price
    )
    if peak_price <= 0.0:
        peak_price = max(current_price, 0.01)

    low_52w: float | None = stock_details.fifty_two_week_low if stock_details else None

    ter: float | None = None
    if asset_type == "ETF":
        etf_details: ETFDetails | None = etf_provider.get_details(dummy_asset)
        ter = etf_details.ter_pct if etf_details else None
        if ter is None and target.get("ter") is not None:
            ter = float(target["ter"])

    trailing_pe: float | None = stock_details.pe_ratio if stock_details else None
    forward_pe: float | None = stock_details.forward_pe if stock_details else None

    return {
        "symbol": symbol,
        "asset_type": asset_type,
        "current_price": current_price,
        "peak_price": peak_price,
        "target_allocation_pct": float(target.get("target_allocation_pct", 0.0)),
        "current_allocation_pct": current_alloc_pct,
        "ter": ter,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "low_52w": low_52w,
        "high_52w": peak_price,
    }


def _format_action(action: RecommendationAction | None) -> Text:
    """Formats recommendation action with color coding."""
    if action == RecommendationAction.BUY:
        return Text("BUY", style="bold green")
    if action == RecommendationAction.SELL:
        return Text("SELL", style="bold red")
    if action == RecommendationAction.HOLD:
        return Text("HOLD", style="bold yellow")
    return Text("N/A", style="dim")


def _format_urgency(urgency: UrgencyLevel | None) -> Text:
    """Formats urgency level with color coding."""
    if urgency == UrgencyLevel.HIGH:
        return Text("HIGH", style="bold red")
    if urgency == UrgencyLevel.MEDIUM:
        return Text("MED", style="yellow")
    if urgency == UrgencyLevel.LOW:
        return Text("LOW", style="green")
    return Text("N/A", style="dim")


@app.command(name="rebalance")
def recommend_rebalance(
    targets_file: Annotated[
        Path,
        typer.Option(
            "--targets-file",
            "-t",
            help="Path to JSON file containing target wishlist.",
        ),
    ] = DATA_DIR
    / "portfolio_targets.json",
    portfolio_file: Annotated[
        Path,
        typer.Option(
            "--portfolio-file",
            "-p",
            help="Path to JSON file containing active holdings.",
        ),
    ] = DATA_DIR
    / "portfolio.json",
    skip_ai: Annotated[
        bool,
        typer.Option(
            "--skip-ai",
            help="Skip Gemini AI analysis and display quantitative scores only.",
        ),
    ] = False,
    notify: Annotated[
        bool,
        typer.Option(
            "--notify",
            help="Send rebalancing recommendations to Discord webhook.",
        ),
    ] = False,
) -> None:
    """Ranks targets and provides AI-driven rebalancing recommendations."""
    targets_raw: list[dict[str, Any]] = load_json_data(targets_file)
    portfolio_raw: list[dict[str, Any]] = load_json_data(portfolio_file)

    if not targets_raw:
        console.print(
            f"[bold red]Error:[/bold red] No targets found in '{targets_file}'."
        )
        raise typer.Exit(code=1)

    stock_provider: StockProvider = StockProvider()
    etf_provider: ETFProvider = ETFProvider()

    with console.status("[bold cyan]Fetching market data and evaluating portfolio..."):
        current_alloc_map: dict[str, float]
        total_val: float
        current_alloc_map, total_val = calculate_current_allocations(
            portfolio_raw, stock_provider
        )

        enriched_assets: list[dict[str, Any]] = []
        for target in targets_raw:
            symbol: str = str(
                target.get("yahoo_ticker") or target.get("symbol") or ""
            ).strip()
            alloc_pct: float = current_alloc_map.get(symbol, 0.0)
            try:
                enriched: dict[str, Any] = enrich_target_asset(
                    target, alloc_pct, stock_provider, etf_provider
                )
                enriched_assets.append(enriched)
            except Exception as err:
                logger.error(f"Failed to enrich asset '{symbol}': {err}")

    if not enriched_assets:
        console.print("[bold red]Error:[/bold red] Could not enrich any target asset.")
        raise typer.Exit(code=1)

    engine: PortfolioDecisionEngine = PortfolioDecisionEngine()
    ranked_scores: list[AssetScore] = engine.rank_assets(enriched_assets)

    gemini_client: GeminiClient | None = None
    if not skip_ai:
        try:
            gemini_client = GeminiClient()
        except GeminiAuthError as err:
            console.print(
                f"[yellow]Warning:[/yellow] Gemini AI disabled ({err}). "
                "Running in quantitative-only mode."
            )

    table = Table(
        title="PORTFOLIO REBALANCING & INVESTMENT DECISION MATRIX",
        header_style="bold magenta",
        expand=True,
    )

    table.add_column("Rank", justify="right", style="cyan", no_wrap=True)
    table.add_column("Symbol", style="bold white", no_wrap=True)
    table.add_column("Type", style="dim", no_wrap=True)
    table.add_column("Price (€)", justify="right")
    table.add_column("Current %", justify="right")
    table.add_column("Target %", justify="right")
    table.add_column("Quant Score", justify="right", style="bold blue")

    if gemini_client:
        table.add_column("AI Action", justify="center")
        table.add_column("Urgency", justify="center")
        table.add_column("Conf.", justify="right")
        table.add_column("AI Reasoning", style="italic")

    recommendations_map: dict[str, RebalanceRecommendation] = {}

    asset_dict_map: dict[str, dict[str, Any]] = {
        str(a["symbol"]): a for a in enriched_assets
    }

    with console.status("[bold magenta]Running Gemini AI rebalancing analysis..."):
        for rank, score in enumerate(ranked_scores, start=1):
            target_item: dict[str, Any] = asset_dict_map[score.symbol]
            price: float = float(target_item["current_price"])
            curr_pct: float = float(target_item["current_allocation_pct"])
            targ_pct: float = float(target_item["target_allocation_pct"])

            row_data: list[Any] = [
                str(rank),
                score.symbol,
                score.asset_type.value,
                f"{price:.2f}€",
                f"{curr_pct:.2f}%",
                f"{targ_pct:.2f}%",
                f"{score.total_score:.4f}",
            ]

            if gemini_client:
                portfolio_ctx: dict[str, Any] = {
                    "total_portfolio_value_eur": total_val,
                    "current_allocation_pct": curr_pct,
                    "target_allocation_pct": targ_pct,
                }
                try:
                    rec: RebalanceRecommendation = gemini_client.analyze_asset(
                        asset_data=target_item,
                        portfolio_context=portfolio_ctx,
                    )
                    recommendations_map[score.symbol] = rec

                    conf_str: str = f"{rec.confidence_score * 100:.0f}%"
                    row_data.extend(
                        [
                            _format_action(rec.action),
                            _format_urgency(rec.urgency_level),
                            conf_str,
                            rec.reasoning,
                        ]
                    )
                except (GeminiAPIError, Exception) as err:
                    logger.error(
                        f"Gemini AI analysis failed for '{score.symbol}': {err}"
                    )
                    row_data.extend(
                        [
                            Text("ERROR", style="bold red"),
                            Text("N/A", style="dim"),
                            "N/A",
                            "AI analysis failed",
                        ]
                    )

            table.add_row(*row_data)

    header_panel = Panel(
        Text.from_markup(
            f"[bold white]Total Portfolio Value:[/bold white] "
            f"[green]{total_val:,.2f} EUR[/green]\n"
            f"[bold white]Target Assets Evaluated:[/bold white] "
            f"[cyan]{len(ranked_scores)}[/cyan]"
        ),
        title="[bold yellow]Portfolio Summary[/bold yellow]",
        border_style="blue",
    )

    console.print(header_panel)
    console.print(table)

    # Dispatches Discord notification if explicitly requested via CLI flag
    if notify:
        send_discord_notification(ranked_scores, recommendations_map, total_val)


if __name__ == "__main__":
    app()
