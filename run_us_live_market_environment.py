from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.config import DEFAULT_DB_PATH
from quantmarket_market.global_context_db import DEFAULT_GLOBAL_CONTEXT_DB_PATH
from quantmarket_market.market_environment_indicators import (
    build_market_environment_indicators_manifest,
    build_market_environment_indicators_payload,
)
from quantmarket_market.payloads import build_api_response, write_payload_file
from quantmarket_market.remote_publish import RemotePublishConfig, publish_remote_files
from quantmarket_market.yahoo_global_assets import collect_yahoo_global_assets_intraday

KST = timezone(timedelta(hours=9))
FILENAMES = [
    "quantservice_market_environment_indicators.json",
    "api_v1_market_environment_indicators.json",
    "quantservice_market_environment_indicators_manifest.json",
]


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh US/global live market-environment indicator payload only.")
    parser.add_argument("--market", default="KR")
    parser.add_argument("--asof", default=None)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--global-db", default=str(DEFAULT_GLOBAL_CONTEXT_DB_PATH))
    parser.add_argument("--handoff-dir", default=str(ROOT / "service_platform" / "web" / "public_data" / "handoff" / "quantservice" / "current"))
    parser.add_argument("--snapshot-dir", default=str(ROOT / "service_platform" / "web" / "public_data" / "current"))
    parser.add_argument("--sync-to-quantservice", action="store_true")
    parser.add_argument("--quantservice-target-dir", default="D:/QuantService/service_platform/web/public_data/market_analysis/current")
    parser.add_argument("--publish-remote", action="store_true")
    parser.add_argument("--remote-gcs-bucket", default="quantservice-489808-market-analysis")
    parser.add_argument("--remote-base-url", default="https://storage.googleapis.com/quantservice-489808-market-analysis/market_analysis/current")
    parser.add_argument("--remote-prefix", default="market_analysis")
    parser.add_argument("--remote-credentials", default="D:/QuantService/data/gcp/quantmarket-handoff-uploader.json")
    parser.add_argument("--sleep", type=float, default=0.05)
    return parser.parse_args()


def _copy_files(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in FILENAMES:
        shutil.copy2(source_dir / filename, target_dir / filename)


def main() -> None:
    args = parse_args()
    asof = args.asof or _now_kst()
    generated_at = _now_kst()
    db_path = Path(args.db)
    global_db_path = Path(args.global_db)
    handoff_dir = Path(args.handoff_dir)
    snapshot_dir = Path(args.snapshot_dir)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    collect_result = collect_yahoo_global_assets_intraday(
        db_path=global_db_path,
        asof=asof,
        sleep_seconds=args.sleep,
    )
    with sqlite3.connect(str(db_path)) as con:
        con.row_factory = sqlite3.Row
        payload = build_market_environment_indicators_payload(
            con,
            market=args.market,
            asof=asof,
            generated_at=generated_at,
            global_db_path=global_db_path,
        )
    manifest = build_market_environment_indicators_manifest(
        market=args.market,
        asof=asof,
        generated_at=generated_at,
        payload=payload,
    )
    api_payload = build_api_response(
        endpoint="/api/v1/market-environment-indicators?market=KR",
        market=args.market,
        asof=asof,
        payload=payload,
    )

    write_payload_file(handoff_dir / "quantservice_market_environment_indicators.json", payload)
    write_payload_file(handoff_dir / "api_v1_market_environment_indicators.json", api_payload)
    write_payload_file(handoff_dir / "quantservice_market_environment_indicators_manifest.json", manifest)
    write_payload_file(snapshot_dir / "market_environment_indicators.json", payload)
    write_payload_file(snapshot_dir / "api_v1_market_environment_indicators.json", api_payload)
    write_payload_file(snapshot_dir / "market_environment_indicators_manifest.json", manifest)

    if args.sync_to_quantservice:
        _copy_files(handoff_dir, Path(args.quantservice_target_dir))

    remote_result = None
    if args.publish_remote:
        remote_result = publish_remote_files(
            handoff_dir=handoff_dir,
            filenames=FILENAMES,
            config=RemotePublishConfig(
                enabled=True,
                provider="gcs",
                gcs_bucket=args.remote_gcs_bucket,
                base_url=args.remote_base_url,
                prefix=args.remote_prefix,
                access_mode="public",
                credentials_path=Path(args.remote_credentials),
                dry_run=False,
            ),
        )

    report = {
        "market": args.market,
        "asof": asof,
        "generated_at": generated_at,
        "collect_result": collect_result,
        "handoff_dir": str(handoff_dir),
        "snapshot_dir": str(snapshot_dir),
        "sync_to_quantservice": bool(args.sync_to_quantservice),
        "publish_remote": remote_result,
        "files": FILENAMES,
    }
    report_dir = ROOT / "reports" / "market_environment_live"
    report_dir.mkdir(parents=True, exist_ok=True)
    write_payload_file(report_dir / "us_live_market_environment_latest.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
