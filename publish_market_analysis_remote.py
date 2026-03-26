from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.config import QUANTSERVICE_HANDOFF_DIR, REPORT_DIR
from quantmarket_market.payloads import write_payload_file
from quantmarket_market.remote_publish import RemotePublishConfig, publish_remote_handoff


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish existing QuantMarket handoff files to a remote source.")
    parser.add_argument("--handoff-dir", default=str(QUANTSERVICE_HANDOFF_DIR), help="Existing handoff directory to publish.")
    parser.add_argument("--asof", required=True, help="Asof timestamp matching the handoff set.")
    parser.add_argument("--remote-provider", default=None, help="Remote publish provider override.")
    parser.add_argument("--remote-gcs-bucket", default=None, help="GCS bucket override for remote publish.")
    parser.add_argument("--remote-base-url", default=None, help="Base URL override exposed to QuantService.")
    parser.add_argument("--remote-prefix", default=None, help="Remote object prefix override.")
    parser.add_argument("--remote-access-mode", default=None, help="Access mode metadata, e.g. public or signed.")
    parser.add_argument("--remote-credentials", default=None, help="Optional service account JSON path.")
    parser.add_argument("--remote-dry-run", action="store_true", help="Build and validate the publish plan without uploading files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    defaults = RemotePublishConfig(enabled=True)
    config = RemotePublishConfig(
        enabled=True,
        provider=(args.remote_provider or defaults.provider),
        gcs_bucket=(args.remote_gcs_bucket or defaults.gcs_bucket),
        base_url=(args.remote_base_url or defaults.base_url),
        prefix=(args.remote_prefix or defaults.prefix),
        access_mode=(args.remote_access_mode or defaults.access_mode),
        credentials_path=Path(args.remote_credentials) if args.remote_credentials else defaults.credentials_path,
        dry_run=bool(args.remote_dry_run),
    )
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    result = publish_remote_handoff(
        handoff_dir=Path(args.handoff_dir),
        run_id=run_id,
        asof=args.asof,
        config=config,
    )
    write_payload_file(REPORT_DIR / "remote_publish_status_latest.json", result)
    write_payload_file(REPORT_DIR / f"remote_publish_{run_id}.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
