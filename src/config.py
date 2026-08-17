import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"

CREDS_PATH_GDRIVE: Path = Path(
    os.getenv("GDRIVE_CREDS_PATH", str(DATA_DIR / "credentials.json"))
)
TOKEN_PATH_GDRIVE: Path = Path(
    os.getenv("GDRIVE_TOKEN_PATH", str(DATA_DIR / "token.json"))
)
GDRIVE_FOLDER_ID: str | None = os.getenv("GDRIVE_FOLDER_ID")


@dataclass(frozen=True)
class DipDetectorConfig:
    min_drop_pct: float = float(os.getenv("MIN_DROP_PCT", "5.0"))
    max_drop_pct: float = float(os.getenv("MAX_DROP_PCT", "10.0"))
    lookback_days: int = int(os.getenv("LOOKBACK_DAYS", "30"))


DEFAULT_DIP_CONFIG = DipDetectorConfig()
