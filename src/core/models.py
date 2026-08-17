"""
Domain models for the finances application.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Quotation:
    """Represents a market quotation for a ticker."""

    price: float
    currency: str
    timestamp: datetime = field(default_factory=datetime.now)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "price": self.price,
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class Asset:
    """Represents an asset in the user's portfolio configuration."""

    name: str
    isin: str
    yahoo_ticker: str
    quantity: float
    average_buy_price: float
    asset_type: str = "stock"

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Asset:
        return cls(
            name=str(data.get("name", "")),
            isin=str(data.get("isin", "")),
            yahoo_ticker=str(data.get("yahoo_ticker", "")),
            quantity=float(data.get("quantity", 0.0)),
            average_buy_price=float(
                data.get("averageBuyPrice", data.get("average_buy_price", 0.0))
            ),
            asset_type=str(data.get("type", "stock")),
        )

    @property
    def acquisition_cost(self) -> float:
        return self.quantity * self.average_buy_price


@dataclass(frozen=True, slots=True)
class AssetSnapshot:
    """Represents the valuation of an asset at a specific point in time."""

    name: str
    isin: str
    yahoo_ticker: str
    native_price: float
    native_currency: str
    value_eur: float

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetSnapshot:
        return cls(
            name=str(data.get("name", "")),
            isin=str(data.get("isin", "")),
            yahoo_ticker=str(data.get("yahoo_ticker", "")),
            native_price=float(data.get("native_price", 0.0)),
            native_currency=str(data.get("native_currency", "EUR")),
            value_eur=float(data.get("value_eur", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Represents a complete portfolio valuation snapshot."""

    timestamp: str
    total_value_eur: float
    assets_snapshot: list[AssetSnapshot]

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioSnapshot:
        return cls(
            timestamp=str(data.get("timestamp", "")),
            total_value_eur=float(data.get("total_value_eur", 0.0)),
            assets_snapshot=[
                AssetSnapshot.from_dict(item)
                for item in data.get("assets_snapshot", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_value_eur": self.total_value_eur,
            "assets_snapshot": [item.to_dict() for item in self.assets_snapshot],
        }


@dataclass(frozen=True, slots=True)
class Holding:
    """Represents an individual stock or asset holding within an ETF."""

    name: str
    isin: str
    ticker: str | None
    weight_pct: float

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Holding:
        return cls(
            name=str(data.get("name", "")),
            isin=str(data.get("isin", "")),
            ticker=data.get("ticker"),
            weight_pct=float(data.get("weight_pct", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SectorExposure:
    """Represents sector breakdown weight within an ETF."""

    sector_name: str
    weight_pct: float

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SectorExposure:
        return cls(
            sector_name=str(data.get("sector_name", "")),
            weight_pct=float(data.get("weight_pct", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CountryExposure:
    """Represents country breakdown weight within an ETF."""

    country_name: str
    weight_pct: float

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CountryExposure:
        return cls(
            country_name=str(data.get("country_name", "")),
            weight_pct=float(data.get("weight_pct", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ETFDetails:
    """Consolidates ETF holdings, sector exposure, country exposure, and TER."""

    holdings: list[Holding]
    sector_breakdown: list[SectorExposure]
    country_breakdown: list[CountryExposure]
    ter_pct: float | None = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ETFDetails:
        raw_ter: Any = data.get("ter_pct")
        ter_pct: float | None = float(raw_ter) if raw_ter is not None else None

        return cls(
            holdings=[Holding.from_dict(item) for item in data.get("holdings", [])],
            sector_breakdown=[
                SectorExposure.from_dict(item)
                for item in data.get("sector_breakdown", [])
            ],
            country_breakdown=[
                CountryExposure.from_dict(item)
                for item in data.get("country_breakdown", [])
            ],
            ter_pct=ter_pct,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "holdings": [item.to_dict() for item in self.holdings],
            "sector_breakdown": [item.to_dict() for item in self.sector_breakdown],
            "country_breakdown": [item.to_dict() for item in self.country_breakdown],
            "ter_pct": self.ter_pct,
        }


@dataclass(frozen=True, slots=True)
class StockDetails:
    """Consolidates stock fundamental metrics and market data."""

    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    dividend_yield_pct: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    sector: str | None = None
    industry: str | None = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StockDetails:
        def _get_float(key: str) -> float | None:
            val: Any = data.get(key)
            return float(val) if val is not None else None

        def _get_str(key: str) -> str | None:
            val: Any = data.get(key)
            return str(val) if val is not None else None

        return cls(
            market_cap=_get_float("market_cap"),
            pe_ratio=_get_float("pe_ratio"),
            forward_pe=_get_float("forward_pe"),
            dividend_yield_pct=_get_float("dividend_yield_pct"),
            fifty_two_week_high=_get_float("fifty_two_week_high"),
            fifty_two_week_low=_get_float("fifty_two_week_low"),
            sector=_get_str("sector"),
            industry=_get_str("industry"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
