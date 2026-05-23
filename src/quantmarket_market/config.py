from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
REFERENCE_DIR = DATA_DIR / "reference"
SNAPSHOT_DIR = ROOT_DIR / "service_platform" / "web" / "public_data" / "current"
QUANTSERVICE_HANDOFF_DIR = (
    ROOT_DIR / "service_platform" / "web" / "public_data" / "handoff" / "quantservice" / "current"
)
ADMIN_SNAPSHOT_DIR = ROOT_DIR / "service_platform" / "web" / "public_data" / "admin_market" / "current"
ADMIN_HANDOFF_DIR = (
    ROOT_DIR / "service_platform" / "web" / "public_data" / "handoff" / "quantservice" / "admin_market" / "current"
)
NEXT_DAY_PREVIEW_SNAPSHOT_ROOT = ROOT_DIR / "service_platform" / "web" / "public_data" / "next_day_preview" / "snapshot"
REPORT_DIR = ROOT_DIR / "reports" / "market_analysis"
DEFAULT_DB_PATH = DB_DIR / "market_analysis.db"
MANUAL_RATE_SEED_PATH = REFERENCE_DIR / "kr_rates_manual_seed.csv"

QUANT_ROOT_DIR = Path(r"D:\Quant")
QUANT_DB_DIR = QUANT_ROOT_DIR / "data" / "db"
QUANT_UNIVERSE_DIR = QUANT_ROOT_DIR / "data" / "universe"
QUANT_PRICE_DB_PATH = QUANT_DB_DIR / "price.db"
QUANT_REGIME_DB_PATH = QUANT_DB_DIR / "regime.db"
QUANTSERVICE_LOCAL_TARGET_DIR = Path(
    r"D:\QuantService\service_platform\web\public_data\market_analysis\current"
)

REMOTE_PUBLISH_ENABLED = os.getenv("QUANTMARKET_REMOTE_PUBLISH_ENABLED", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
REMOTE_PUBLISH_PROVIDER = os.getenv("QUANTMARKET_REMOTE_PUBLISH_PROVIDER", "gcs").strip().lower() or "gcs"
REMOTE_GCS_BUCKET = os.getenv("QUANTMARKET_REMOTE_GCS_BUCKET", "").strip()
REMOTE_BASE_URL = os.getenv("QUANTMARKET_REMOTE_BASE_URL", "").strip()
REMOTE_PREFIX = os.getenv("QUANTMARKET_REMOTE_PREFIX", "market_analysis").strip().strip("/") or "market_analysis"
REMOTE_ACCESS_MODE = os.getenv("QUANTMARKET_REMOTE_ACCESS_MODE", "public").strip().lower() or "public"
REMOTE_CREDENTIALS_PATH = (
    Path(os.getenv("QUANTMARKET_GCP_CREDENTIALS", "")).expanduser()
    if os.getenv("QUANTMARKET_GCP_CREDENTIALS")
    else None
)
REMOTE_DRY_RUN = os.getenv("QUANTMARKET_REMOTE_DRY_RUN", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def ensure_runtime_dirs() -> None:
    for path in (
        DATA_DIR,
        DB_DIR,
        REFERENCE_DIR,
        SNAPSHOT_DIR,
        QUANTSERVICE_HANDOFF_DIR,
        ADMIN_SNAPSHOT_DIR,
        ADMIN_HANDOFF_DIR,
        NEXT_DAY_PREVIEW_SNAPSHOT_ROOT,
        REPORT_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
