"""
Custom domain and infrastructure exceptions for the finances application.
"""


class FinancesError(Exception):
    """Base exception for all domain-specific errors in the finances app."""


class DomainError(FinancesError):
    """Raised when a business logic or domain constraint is violated."""


class AssetNotFoundError(DomainError):
    """Raised when an asset or ticker cannot be found in configuration or history."""


class InvalidWatchlistError(DomainError):
    """Raised when watchlist configuration is malformed or unreadable."""


class QuotationError(FinancesError):
    """Base class for market data and exchange rate retrieval errors."""


class QuotationFetchError(QuotationError):
    """Raised when market quotation retrieval fails for a specific ticker."""


class ExchangeRateFetchError(QuotationError):
    """Raised when currency exchange rate conversion fails."""


class JustETFScrapeError(FinancesError):
    """Raised when scraping ETF details from JustETF fails."""


class StorageError(FinancesError):
    """Base class for storage or persistence errors."""


class StorageReadError(StorageError):
    """Raised when reading from storage (JSON/GDrive) fails."""


class StorageWriteError(StorageError):
    """Raised when writing to storage (JSON/GDrive) fails."""
