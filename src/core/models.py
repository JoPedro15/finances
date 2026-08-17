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

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Asset:
        return cls(
            name=data.get("name", ""),
            isin=data.get("isin", ""),
            yahoo_ticker=data.get("yahoo_ticker", ""),
            quantity=float(data.get("quantity", 0.0)),
            average_buy_price=float(
                data.get("averageBuyPrice", data.get("average_buy_price", 0.0))
            ),
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
            name=data.get("name", ""),
            isin=data.get("isin", ""),
            yahoo_ticker=data.get("yahoo_ticker", ""),
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
