"""This file contains functions for analyzing portfolio
performance and asset exposures."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.exceptions import StorageError
from src.core.models import Asset, ETFDetails, PortfolioSnapshot
from src.core.providers import ETFProvider
from src.core.repositories import (
    HistoryRepository,
    PortfolioRepository,
    SqliteHistoryRepository,
    SqlitePortfolioRepository,
)
from src.infra.database.connection import DEFAULT_DB_PATH
from src.utils.logger.logger import logger


@dataclass
class PortfolioExposure:
    """Aggregated portfolio exposure across sectors and countries."""

    sector_exposure: dict[str, float] = field(default_factory=dict)
    country_exposure: dict[str, float] = field(default_factory=dict)
    total_etf_value_eur: float = 0.0


def calculate_portfolio_exposure(
    snapshot: PortfolioSnapshot,
    portfolio_repo: PortfolioRepository | None = None,
    etf_provider: ETFProvider | None = None,
) -> PortfolioExposure:
    """Calculates value-weighted sector and country exposure for portfolio ETFs."""
    repo: PortfolioRepository = portfolio_repo or SqlitePortfolioRepository(
        DEFAULT_DB_PATH
    )
    provider: ETFProvider = etf_provider or ETFProvider()

    try:
        assets: list[Asset] = repo.load_assets()
    except Exception as e:
        logger.error(f"Failed to load assets for exposure calculation: {e}")
        return PortfolioExposure()

    asset_map: dict[str, Asset] = {a.isin: a for a in assets if a.isin}
    snapshot_map: dict[str, float] = {
        s.isin: s.value_eur for s in snapshot.assets_snapshot if s.isin
    }

    sector_weighted_val: dict[str, float] = {}
    country_weighted_val: dict[str, float] = {}
    total_etf_val: float = 0.0

    for isin, asset in asset_map.items():
        if not asset.isin or len(asset.isin) != 12:
            continue
        if asset.asset_type != "etf":
            continue

        asset_value_eur: float = snapshot_map.get(isin, 0.0)
        if asset_value_eur <= 0.0:
            continue

        details: ETFDetails | None = provider.get_details(asset)
        if details is None:
            continue

        total_etf_val += asset_value_eur

        for sector in details.sector_breakdown:
            current_sector: float = sector_weighted_val.get(sector.sector_name, 0.0)
            sector_weighted_val[sector.sector_name] = current_sector + (
                asset_value_eur * (sector.weight_pct / 100.0)
            )

        for country in details.country_breakdown:
            current_country: float = country_weighted_val.get(country.country_name, 0.0)
            country_weighted_val[country.country_name] = current_country + (
                asset_value_eur * (country.weight_pct / 100.0)
            )

    sector_pcts: dict[str, float] = {}
    country_pcts: dict[str, float] = {}

    total_analyzed_sector_val: float = sum(sector_weighted_val.values())
    total_analyzed_country_val: float = sum(country_weighted_val.values())

    if total_analyzed_sector_val > 0.0:
        for sector_name, val in sector_weighted_val.items():
            sector_pcts[sector_name] = round(
                (val / total_analyzed_sector_val) * 100.0, 2
            )

    if total_analyzed_country_val > 0.0:
        for country_name, val in country_weighted_val.items():
            country_pcts[country_name] = round(
                (val / total_analyzed_country_val) * 100.0, 2
            )

    return PortfolioExposure(
        sector_exposure=dict(
            sorted(sector_pcts.items(), key=lambda item: item[1], reverse=True)
        ),
        country_exposure=dict(
            sorted(country_pcts.items(), key=lambda item: item[1], reverse=True)
        ),
        total_etf_value_eur=round(total_etf_val, 2),
    )


def analyze_overall_performance(
    portfolio_repo: PortfolioRepository | None = None,
    history_repo: HistoryRepository | None = None,
) -> None:
    """Analyzes performance of individual assets and the overall portfolio."""
    logger.section("Portfolio Performance Analysis")

    p_repo: PortfolioRepository = portfolio_repo or SqlitePortfolioRepository(
        DEFAULT_DB_PATH
    )
    h_repo: HistoryRepository = history_repo or SqliteHistoryRepository(DEFAULT_DB_PATH)

    try:
        assets: list[Asset] = p_repo.load_assets()
        history: list[PortfolioSnapshot] = h_repo.load_history()

        if not history:
            logger.warning("History storage is empty. Cannot perform analysis.")
            return

        latest_snapshot: PortfolioSnapshot = history[-1]
    except StorageError as e:
        logger.error(f"Could not read data from storage: {e}")
        return

    latest_asset_values: dict[str, float] = {
        asset.isin: asset.value_eur
        for asset in latest_snapshot.assets_snapshot
        if asset.isin
    }

    valid_acquisition_cost: float = 0.0
    valid_latest_value: float = 0.0

    for asset in assets:
        logger.subsection(asset.name)

        acquisition_cost: float = asset.acquisition_cost
        latest_value: float | None = (
            latest_asset_values.get(asset.isin) if asset.isin else None
        )

        if latest_value is None:
            logger.warning(f"No recent market data found for {asset.name}. Skipping.")
            logger.print("--------------------")
            continue

        valid_acquisition_cost += acquisition_cost
        valid_latest_value += latest_value

        logger.info(f"Acquisition Cost: {acquisition_cost:.2f} EUR")
        logger.info(f"Latest Market Value: {latest_value:.2f} EUR")

        absolute_gain: float = latest_value - acquisition_cost
        if absolute_gain >= 0:
            logger.success(f"Absolute Gain: +{absolute_gain:.2f} EUR")
        else:
            logger.warning(f"Absolute Loss: {absolute_gain:.2f} EUR")

        logger.print("--------------------")

    logger.subsection("Global Analysis")

    total_acquisition_cost: float = valid_acquisition_cost
    total_latest_value: float = valid_latest_value

    logger.info(f"Total Acquisition Cost: {total_acquisition_cost:.2f} EUR")
    logger.info(f"Latest Market Value:   {total_latest_value:.2f} EUR")

    total_absolute_gain: float = total_latest_value - total_acquisition_cost
    if total_absolute_gain >= 0:
        logger.success(f"Absolute Gain: +{total_absolute_gain:.2f} EUR")
    else:
        logger.warning(f"Absolute Loss: {total_absolute_gain:.2f} EUR")

    roi_percentage: float = (
        (total_absolute_gain / total_acquisition_cost) * 100
        if total_acquisition_cost != 0
        else 0.0
    )
    if roi_percentage >= 0:
        logger.success(f"Return on Investment (ROI): +{roi_percentage:.2f}%")
    else:
        logger.warning(f"Return on Investment (ROI): {roi_percentage:.2f}%")
