"""Global configuration module loading environment
variables and setting strategy parameters."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"

# Google Drive Paths & Identifiers
CREDS_PATH_GDRIVE: Path = Path(
    os.getenv("GDRIVE_CLIENT_SECRET_FILE", str(DATA_DIR / "credentials.json"))
)
TOKEN_PATH_GDRIVE: Path = Path(
    os.getenv("GDRIVE_TOKEN_FILE", str(DATA_DIR / "token.json"))
)
GDRIVE_CONFIG_FOLDER_ID: str | None = os.getenv("GDRIVE_CONFIG_FOLDER_ID")
GDRIVE_SNAPSHOT_FOLDER_ID: str | None = os.getenv("GDRIVE_SNAPSHOT_FOLDER_ID")

# Cache Settings
ETF_CACHE_FILE: Path = DATA_DIR / "etf_cache.json"
DEFAULT_ETF_CACHE_TTL_DAYS: int = int(os.getenv("ETF_CACHE_TTL_DAYS", "30"))


@dataclass(frozen=True)
class DipDetectorConfig:
    """Configuration parameters for generic dip detection scans."""

    min_drop_pct: float = float(os.getenv("MIN_DROP_PCT", "5.0"))
    max_drop_pct: float = float(os.getenv("MAX_DROP_PCT", "10.0"))
    lookback_days: int = int(os.getenv("LOOKBACK_DAYS", "30"))


DEFAULT_DIP_CONFIG: DipDetectorConfig = DipDetectorConfig()


@dataclass(frozen=True)
class StockStrategyConfig:
    """Configuration parameters for individual stock scoring strategy."""

    dip_min_pct: float = float(os.getenv("STOCK_DIP_MIN_PCT", "5.0"))
    dip_max_pct: float = float(os.getenv("STOCK_DIP_MAX_PCT", "20.0"))
    weight_dip: float = float(os.getenv("STOCK_WEIGHT_DIP", "0.30"))
    weight_forward_pe: float = float(os.getenv("STOCK_WEIGHT_FORWARD_PE", "0.30"))
    weight_52w_range: float = float(os.getenv("STOCK_WEIGHT_52W_RANGE", "0.15"))
    weight_allocation: float = float(os.getenv("STOCK_WEIGHT_ALLOCATION", "0.25"))
    alloc_gap_max_pct: float = float(os.getenv("STOCK_ALLOC_GAP_MAX_PCT", "10.0"))

    def __post_init__(self) -> None:
        """Validates that stock scoring criteria weights sum to 1.0."""
        total_weight: float = round(
            self.weight_dip
            + self.weight_forward_pe
            + self.weight_52w_range
            + self.weight_allocation,
            2,
        )
        if total_weight != 1.0:
            raise ValueError(
                f"Stock strategy weights must sum to 1.0, got {total_weight}"
            )


DEFAULT_STOCK_CONFIG: StockStrategyConfig = StockStrategyConfig()


@dataclass(frozen=True)
class EtfStrategyConfig:
    """Configuration parameters for ETF scoring strategy."""

    weight_dip: float = float(os.getenv("ETF_WEIGHT_DIP", "0.40"))
    weight_ter: float = float(os.getenv("ETF_WEIGHT_TER", "0.20"))
    weight_allocation: float = float(os.getenv("ETF_WEIGHT_ALLOCATION", "0.40"))

    dip_min_pct: float = float(os.getenv("ETF_DIP_MIN_PCT", "5.0"))
    dip_max_pct: float = float(os.getenv("ETF_DIP_MAX_PCT", "10.0"))

    ter_low_pct: float = float(os.getenv("ETF_TER_LOW_PCT", "0.10"))
    ter_high_pct: float = float(os.getenv("ETF_TER_HIGH_PCT", "0.50"))

    alloc_gap_max_pct: float = float(os.getenv("ETF_ALLOC_GAP_MAX_PCT", "10.0"))

    def __post_init__(self) -> None:
        """Validates that ETF scoring criteria weights sum to 1.0."""
        total_weight: float = round(
            self.weight_dip + self.weight_ter + self.weight_allocation, 2
        )
        if total_weight != 1.0:
            raise ValueError(
                f"ETF strategy weights must sum to 1.0, got {total_weight}"
            )


DEFAULT_ETF_CONFIG: EtfStrategyConfig = EtfStrategyConfig()
