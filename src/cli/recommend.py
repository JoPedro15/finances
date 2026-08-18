"""CLI module for evaluating and ranking investment targets with live market data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.config import DATA_DIR
from src.core.decision.base import AssetScore
from src.core.decision.engine import PortfolioDecisionEngine
from src.core.models import Asset, ETFDetails, Quotation, StockDetails
from src.core.providers import ETFProvider, StockProvider


def load_json_data(file_path: Path) -> list[dict[str, Any]]:
    """Loads and normalizes JSON data containing asset lists or holdings."""
    if not file_path.exists():
        return []

    with open(file_path, encoding="utf-8") as file:
        data: Any = json.load(file)

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and "assets" in data:
        return [item for item in data["assets"] if isinstance(item, dict)]

    return []


def calculate_current_allocations(
    portfolio_items: list[dict[str, Any]],
    stock_provider: StockProvider,
) -> tuple[dict[str, float], float]:
    """Fetches live prices for active holdings and
    computes real current allocation %."""
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
    """Enriches wishlist asset with real-time market data and valuation metrics."""
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

    stock_details: StockDetails | None = stock_provider.get_details(dummy_asset)

    peak_price: float = (
        stock_details.fifty_two_week_high
        if stock_details and stock_details.fifty_two_week_high
        else current_price
    )
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


def run_decision_cli() -> None:
    """Orchestrates live data enrichment, asset scoring, and CLI output rendering."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Rank portfolio investment targets using live market data."
    )
    parser.add_argument(
        "--targets-file",
        type=str,
        default=str(DATA_DIR / "portfolio_targets.json"),
        help="Path to JSON file containing target wishlist",
    )
    parser.add_argument(
        "--portfolio-file",
        type=str,
        default=str(DATA_DIR / "portfolio.json"),
        help="Path to JSON file containing active holdings",
    )

    args: argparse.Namespace = parser.parse_args()

    targets_raw: list[dict[str, Any]] = load_json_data(Path(args.targets_file))
    portfolio_raw: list[dict[str, Any]] = load_json_data(Path(args.portfolio_file))

    stock_provider: StockProvider = StockProvider()
    etf_provider: ETFProvider = ETFProvider()

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
        enriched_assets.append(
            enrich_target_asset(target, alloc_pct, stock_provider, etf_provider)
        )

    engine: PortfolioDecisionEngine = PortfolioDecisionEngine()
    ranked_scores: list[AssetScore] = engine.rank_assets(enriched_assets)

    price_map: dict[str, float] = {
        str(asset["symbol"]): float(asset["current_price"]) for asset in enriched_assets
    }

    print("=" * 72)
    print("INVESTMENT TARGETS RANKING (LIVE MARKET DATA)")
    print(f"Total Portfolio Value: {total_val:.2f} EUR")
    print("=" * 72)
    print(
        f"{'Rank':<5} | {'Symbol':<8} | {'Type':<6} | {'Price (€)':<9} | "
        f"{'Current %':<9} | {'Target %':<8} | {'Score':<7}"
    )
    print("-" * 72)

    for rank, score in enumerate(ranked_scores, start=1):
        price: float = price_map[score.symbol]
        target_item: dict[str, Any] = next(
            a for a in enriched_assets if a["symbol"] == score.symbol
        )
        curr_pct: float = float(target_item["current_allocation_pct"])
        targ_pct: float = float(target_item["target_allocation_pct"])

        print(
            f"{rank:<5} | {score.symbol:<8} | {score.asset_type.value:<6} | "
            f"{price:>8.2f}€ | {curr_pct:>8.2f}% | {targ_pct:>7.2f}% | "
            f"{score.total_score:>7.4f}"
        )

    print("-" * 72)


if __name__ == "__main__":
    run_decision_cli()
