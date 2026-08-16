import os
from dataclasses import dataclass
from dotenv import load_dotenv  # type: ignore[import-untyped]

# Loads environment variables from a local .env file if present
load_dotenv()


@dataclass(frozen=True)
class DipDetectorConfig:
    min_drop_pct: float = float(os.getenv("MIN_DROP_PCT", "5.0"))
    max_drop_pct: float = float(os.getenv("MAX_DROP_PCT", "10.0"))
    lookback_days: int = int(os.getenv("LOOKBACK_DAYS", "30"))


DEFAULT_DIP_CONFIG = DipDetectorConfig()
