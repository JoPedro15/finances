"""Unit tests for domain models in src/core/models.py covering serialisation,
subscript access, default values, immutability, and edge cases.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from typing import Any

import pytest

from src.core.models import (
    Asset,
    AssetSnapshot,
    CountryExposure,
    ETFDetails,
    Holding,
    PortfolioSnapshot,
    Quotation,
    SectorExposure,
    StockDetails,
)

# ==============================================================================
# Quotation
# ==============================================================================


def test_quotation_to_dict() -> None:
    """Validates Quotation.to_dict() serialises all fields correctly."""
    ts: datetime = datetime(2026, 8, 17, 10, 0, 0)
    q: Quotation = Quotation(price=150.5, currency="USD", timestamp=ts)

    result: dict[str, Any] = q.to_dict()

    assert result["price"] == 150.5
    assert result["currency"] == "USD"
    assert result["timestamp"] == ts.isoformat()


def test_quotation_default_timestamp() -> None:
    """Validates Quotation sets a default timestamp when none is provided."""
    before: datetime = datetime.now()
    q: Quotation = Quotation(price=100.0, currency="EUR")
    after: datetime = datetime.now()

    assert before <= q.timestamp <= after


def test_quotation_subscript_access() -> None:
    """Validates Quotation.__getitem__() subscript field retrieval."""
    q: Quotation = Quotation(price=250.0, currency="EUR")

    assert q["price"] == 250.0
    assert q["currency"] == "EUR"


# ==============================================================================
# Asset
# ==============================================================================


def test_asset_from_dict_standard_key() -> None:
    """Validates Asset.from_dict() reads average_buy_price key correctly."""
    data: dict[str, Any] = {
        "name": "Apple",
        "isin": "US0378331005",
        "yahoo_ticker": "AAPL",
        "quantity": 10.0,
        "average_buy_price": 150.0,
        "type": "stock",
    }
    asset: Asset = Asset.from_dict(data)

    assert asset.name == "Apple"
    assert asset.isin == "US0378331005"
    assert asset.yahoo_ticker == "AAPL"
    assert asset.quantity == 10.0
    assert asset.average_buy_price == 150.0
    assert asset.asset_type == "STOCK"


def test_asset_from_dict_legacy_key() -> None:
    """Validates Asset.from_dict() falls back to averageBuyPrice (legacy JSON key)."""
    data: dict[str, Any] = {
        "name": "NVIDIA",
        "isin": "US67066G1040",
        "yahoo_ticker": "NVDA",
        "quantity": 2.0,
        "averageBuyPrice": 117.06,
        "type": "etf",
    }
    asset: Asset = Asset.from_dict(data)

    assert asset.average_buy_price == 117.06
    assert asset.asset_type == "ETF"


def test_asset_from_dict_empty_defaults() -> None:
    """Validates Asset.from_dict() default values when empty dictionary is provided."""
    asset: Asset = Asset.from_dict({})

    assert asset.name == ""
    assert asset.isin == ""
    assert asset.yahoo_ticker == ""
    assert asset.quantity == 0.0
    assert asset.average_buy_price == 0.0
    assert asset.asset_type == "STOCK"


def test_asset_acquisition_cost() -> None:
    """Validates acquisition_cost property returns quantity * average_buy_price."""
    asset: Asset = Asset(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=10.0,
        average_buy_price=150.0,
    )

    assert asset.acquisition_cost == 1500.0


def test_asset_acquisition_cost_zero_quantity() -> None:
    """Validates acquisition_cost returns 0.0 when quantity is zero."""
    asset: Asset = Asset(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=0.0,
        average_buy_price=150.0,
    )

    assert asset.acquisition_cost == 0.0


def test_asset_subscript_access() -> None:
    """Validates Asset.__getitem__() subscript field retrieval."""
    asset: Asset = Asset(
        name="Microsoft",
        isin="US5949181045",
        yahoo_ticker="MSFT",
        quantity=5.0,
        average_buy_price=200.0,
    )

    assert asset["name"] == "Microsoft"
    assert asset["isin"] == "US5949181045"
    assert asset["quantity"] == 5.0


def test_asset_immutability() -> None:
    """Validates Asset is immutable (frozen dataclass)."""
    asset: Asset = Asset(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        quantity=10.0,
        average_buy_price=150.0,
    )

    with pytest.raises(FrozenInstanceError):
        asset.quantity = 99.0  # type: ignore[misc]


# ==============================================================================
# AssetSnapshot
# ==============================================================================


def test_asset_snapshot_round_trip() -> None:
    """Validates AssetSnapshot serialises and deserialises correctly."""
    snapshot: AssetSnapshot = AssetSnapshot(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        native_price=180.0,
        native_currency="USD",
        value_eur=162.0,
    )

    result: AssetSnapshot = AssetSnapshot.from_dict(snapshot.to_dict())

    assert result.name == snapshot.name
    assert result.isin == snapshot.isin
    assert result.native_price == snapshot.native_price
    assert result.native_currency == snapshot.native_currency
    assert result.value_eur == snapshot.value_eur


def test_asset_snapshot_from_dict_defaults() -> None:
    """Validates AssetSnapshot.from_dict() defaults for missing values."""
    snapshot: AssetSnapshot = AssetSnapshot.from_dict({})

    assert snapshot.name == ""
    assert snapshot.isin == ""
    assert snapshot.yahoo_ticker == ""
    assert snapshot.native_price == 0.0
    assert snapshot.native_currency == "EUR"
    assert snapshot.value_eur == 0.0


def test_asset_snapshot_subscript_access() -> None:
    """Validates AssetSnapshot.__getitem__() subscript field retrieval."""
    snapshot: AssetSnapshot = AssetSnapshot(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        native_price=180.0,
        native_currency="USD",
        value_eur=162.0,
    )

    assert snapshot["name"] == "Apple"
    assert snapshot["native_price"] == 180.0


# ==============================================================================
# PortfolioSnapshot
# ==============================================================================


def test_portfolio_snapshot_round_trip() -> None:
    """Validates PortfolioSnapshot serialises and deserialises correctly."""
    asset_snap: AssetSnapshot = AssetSnapshot(
        name="Apple",
        isin="US0378331005",
        yahoo_ticker="AAPL",
        native_price=180.0,
        native_currency="USD",
        value_eur=162.0,
    )
    snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-17T10:00:00",
        total_value_eur=162.0,
        assets_snapshot=[asset_snap],
    )

    result: PortfolioSnapshot = PortfolioSnapshot.from_dict(snapshot.to_dict())

    assert result.timestamp == snapshot.timestamp
    assert result.total_value_eur == snapshot.total_value_eur
    assert len(result.assets_snapshot) == 1
    assert result.assets_snapshot[0].name == "Apple"


def test_portfolio_snapshot_empty_assets() -> None:
    """Validates PortfolioSnapshot handles empty asset list."""
    snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-17T10:00:00",
        total_value_eur=0.0,
        assets_snapshot=[],
    )

    result: PortfolioSnapshot = PortfolioSnapshot.from_dict(snapshot.to_dict())

    assert result.assets_snapshot == []
    assert result.total_value_eur == 0.0


def test_portfolio_snapshot_subscript_access() -> None:
    """Validates PortfolioSnapshot.__getitem__() subscript field retrieval."""
    snapshot: PortfolioSnapshot = PortfolioSnapshot(
        timestamp="2026-08-17T10:00:00",
        total_value_eur=500.0,
        assets_snapshot=[],
    )

    assert snapshot["timestamp"] == "2026-08-17T10:00:00"
    assert snapshot["total_value_eur"] == 500.0


# ==============================================================================
# Holding
# ==============================================================================


def test_holding_round_trip_with_ticker() -> None:
    """Validates Holding serialises and deserialises correctly when ticker is set."""
    holding: Holding = Holding(
        name="Apple", isin="US0378331005", ticker="AAPL", weight_pct=5.0
    )

    result: Holding = Holding.from_dict(holding.to_dict())

    assert result.name == holding.name
    assert result.isin == holding.isin
    assert result.ticker == holding.ticker
    assert result.weight_pct == holding.weight_pct


def test_holding_round_trip_without_ticker() -> None:
    """Validates Holding handles None ticker correctly."""
    holding: Holding = Holding(
        name="Apple", isin="US0378331005", ticker=None, weight_pct=5.0
    )

    result: Holding = Holding.from_dict(holding.to_dict())

    assert result.ticker is None


def test_holding_subscript_access() -> None:
    """Validates Holding.__getitem__() subscript field retrieval."""
    holding: Holding = Holding(
        name="Microsoft", isin="US5949181045", ticker="MSFT", weight_pct=8.0
    )

    assert holding["ticker"] == "MSFT"
    assert holding["weight_pct"] == 8.0


# ==============================================================================
# SectorExposure & CountryExposure
# ==============================================================================


def test_sector_exposure_round_trip_and_subscript() -> None:
    """Validates SectorExposure round-trip and subscript retrieval."""
    sector: SectorExposure = SectorExposure(sector_name="Technology", weight_pct=24.5)

    result: SectorExposure = SectorExposure.from_dict(sector.to_dict())

    assert result.sector_name == "Technology"
    assert result.weight_pct == 24.5
    assert sector["sector_name"] == "Technology"


def test_country_exposure_round_trip_and_subscript() -> None:
    """Validates CountryExposure round-trip and subscript retrieval."""
    country: CountryExposure = CountryExposure(
        country_name="United States", weight_pct=70.2
    )

    result: CountryExposure = CountryExposure.from_dict(country.to_dict())

    assert result.country_name == "United States"
    assert result.weight_pct == 70.2
    assert country["country_name"] == "United States"


# ==============================================================================
# ETFDetails
# ==============================================================================


def test_etf_details_round_trip() -> None:
    """Validates ETFDetails serialises and deserialises all nested models."""
    details: ETFDetails = ETFDetails(
        holdings=[
            Holding(name="Apple", isin="US0378331005", ticker="AAPL", weight_pct=5.0)
        ],
        sector_breakdown=[SectorExposure(sector_name="Technology", weight_pct=24.5)],
        country_breakdown=[
            CountryExposure(country_name="United States", weight_pct=70.2)
        ],
        ter_pct=0.20,
    )

    result: ETFDetails = ETFDetails.from_dict(details.to_dict())

    assert result.ter_pct == 0.20
    assert len(result.holdings) == 1
    assert result.holdings[0].name == "Apple"
    assert len(result.sector_breakdown) == 1
    assert result.sector_breakdown[0].sector_name == "Technology"
    assert len(result.country_breakdown) == 1
    assert result.country_breakdown[0].country_name == "United States"


def test_etf_details_none_ter_and_string_coercion() -> None:
    """Validates ETFDetails handles None TER and parses string floats."""
    details_none: ETFDetails = ETFDetails.from_dict({})
    assert details_none.ter_pct is None

    details_str: ETFDetails = ETFDetails.from_dict({"ter_pct": "0.15"})
    assert details_str.ter_pct == 0.15


def test_etf_details_subscript_access() -> None:
    """Validates ETFDetails.__getitem__() subscript field retrieval."""
    details: ETFDetails = ETFDetails(
        holdings=[],
        sector_breakdown=[],
        country_breakdown=[],
        ter_pct=0.07,
    )

    assert details["ter_pct"] == 0.07
    assert details["holdings"] == []


# ==============================================================================
# StockDetails
# ==============================================================================


def test_stock_details_round_trip() -> None:
    """Validates StockDetails serialises and deserialises all fields correctly."""
    details: StockDetails = StockDetails(
        market_cap=3000000000000.0,
        pe_ratio=32.5,
        forward_pe=28.0,
        dividend_yield_pct=0.55,
        fifty_two_week_high=235.0,
        fifty_two_week_low=165.0,
        sector="Technology",
        industry="Consumer Electronics",
    )

    result: StockDetails = StockDetails.from_dict(details.to_dict())

    assert result.market_cap == 3000000000000.0
    assert result.pe_ratio == 32.5
    assert result.forward_pe == 28.0
    assert result.dividend_yield_pct == 0.55
    assert result.fifty_two_week_high == 235.0
    assert result.fifty_two_week_low == 165.0
    assert result.sector == "Technology"
    assert result.industry == "Consumer Electronics"


def test_stock_details_none_values() -> None:
    """Validates StockDetails handles None values correctly in round-trip."""
    details: StockDetails = StockDetails()

    result: StockDetails = StockDetails.from_dict(details.to_dict())

    assert result.market_cap is None
    assert result.pe_ratio is None
    assert result.forward_pe is None
    assert result.dividend_yield_pct is None
    assert result.fifty_two_week_high is None
    assert result.fifty_two_week_low is None
    assert result.sector is None
    assert result.industry is None


def test_stock_details_subscript_access() -> None:
    """Validates StockDetails.__getitem__() subscript field retrieval."""
    details: StockDetails = StockDetails(
        pe_ratio=15.0,
        sector="Energy",
    )

    assert details["pe_ratio"] == 15.0
    assert details["sector"] == "Energy"
    assert details["market_cap"] is None
