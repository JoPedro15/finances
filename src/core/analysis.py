"""This file contains functions for analyzing portfolio
performance and asset exposures using Pandas vectorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

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
    """Calculates value-weighted sector and country exposure

    for portfolio ETFs using Pandas.
    """
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

    raw_sector_records: list[dict[str, float | str]] = []
    raw_country_records: list[dict[str, float | str]] = []
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
            raw_sector_records.append(
                {
                    "name": sector.sector_name,
                    "weighted_value": asset_value_eur * (sector.weight_pct / 100.0),
                }
            )

        for country in details.country_breakdown:
            raw_country_records.append(
                {
                    "name": country.country_name,
                    "weighted_value": asset_value_eur * (country.weight_pct / 100.0),
                }
            )

    sector_pcts: dict[str, float] = {}
    country_pcts: dict[str, float] = {}

    if raw_sector_records:
        df_sectors: pd.DataFrame = pd.DataFrame(raw_sector_records)
        sector_grouped: pd.Series[float] = df_sectors.groupby("name")[
            "weighted_value"
        ].sum()
        total_sector_val: float = float(sector_grouped.sum())

        if total_sector_val > 0.0:
            sector_pcts = {
                str(name): round(float((val / total_sector_val) * 100.0), 2)
                for name, val in sector_grouped.items()
            }

    if raw_country_records:
        df_countries: pd.DataFrame = pd.DataFrame(raw_country_records)
        country_grouped: pd.Series[float] = df_countries.groupby("name")[
            "weighted_value"
        ].sum()
        total_country_val: float = float(country_grouped.sum())

        if total_country_val > 0.0:
            country_pcts = {
                str(name): round(float((val / total_country_val) * 100.0), 2)
                for name, val in country_grouped.items()
            }

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
    """Analyzes performance of individual assets and

    the overall portfolio using vectorised DataFrames.
    """
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

    performance_records: list[dict[str, Any]] = []

    for asset in assets:
        acquisition_cost: float = asset.acquisition_cost
        latest_value: float | None = (
            latest_asset_values.get(asset.isin) if asset.isin else None
        )

        if latest_value is None:
            logger.warning(f"No recent market data found for {asset.name}. Skipping.")
            logger.print("--------------------")
            continue

        performance_records.append(
            {
                "name": asset.name,
                "acquisition_cost": acquisition_cost,
                "latest_value": latest_value,
                "absolute_gain": latest_value - acquisition_cost,
            }
        )

    if not performance_records:
        logger.warning("No valid asset performance records found.")
        return

    df_perf: pd.DataFrame = pd.DataFrame(performance_records)

    for _, row in df_perf.iterrows():
        name: str = str(row["name"])
        acq_cost: float = float(row["acquisition_cost"])
        lat_val: float = float(row["latest_value"])
        abs_gain: float = float(row["absolute_gain"])

        logger.subsection(name)
        logger.info(f"Acquisition Cost: {acq_cost:.2f} EUR")
        logger.info(f"Latest Market Value: {lat_val:.2f} EUR")

        if abs_gain >= 0:
            logger.success(f"Absolute Gain: +{abs_gain:.2f} EUR")
        else:
            logger.warning(f"Absolute Loss: {abs_gain:.2f} EUR")

        logger.print("--------------------")

    logger.subsection("Global Analysis")

    total_acquisition_cost: float = float(df_perf["acquisition_cost"].sum())
    total_latest_value: float = float(df_perf["latest_value"].sum())
    total_absolute_gain: float = float(df_perf["absolute_gain"].sum())

    logger.info(f"Total Acquisition Cost: {total_acquisition_cost:.2f} EUR")
    logger.info(f"Latest Market Value:   {total_latest_value:.2f} EUR")

    if total_absolute_gain >= 0:
        logger.success(f"Absolute Gain: +{total_absolute_gain:.2f} EUR")
    else:
        logger.warning(f"Absolute Loss: {total_absolute_gain:.2f} EUR")

    roi_percentage: float = (
        (total_absolute_gain / total_acquisition_cost) * 100.0
        if total_acquisition_cost != 0.0
        else 0.0
    )

    if roi_percentage >= 0:
        logger.success(f"Return on Investment (ROI): +{roi_percentage:.2f}%")
    else:
        logger.warning(f"Return on Investment (ROI): {roi_percentage:.2f}%")
