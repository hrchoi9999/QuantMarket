from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.pipeline import run_market_analysis_pipeline
from quantmarket_market.remote_publish import RemotePublishConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QuantMarket market-analysis pipeline.")
    parser.add_argument("--market", default="KR", help="Market code, e.g. KR or US.")
    parser.add_argument("--asof", default=None, help="ISO timestamp for the pipeline as-of time.")
    parser.add_argument("--db-path", default=None, help="Optional override for market_analysis.db path.")
    parser.add_argument("--snapshot-dir", default=None, help="Optional override for output snapshot directory.")
    parser.add_argument("--handoff-dir", default=None, help="Optional override for QuantService handoff directory.")
    parser.add_argument("--seed-sample", action="store_true", help="Seed deterministic sample official data into D:\\QuantMarket before computing features.")
    parser.add_argument("--skip-quant-readonly", action="store_true", help="Do not read D:\\Quant read-only data sources for breadth/relative-strength inputs.")
    parser.add_argument("--skip-official-collect", action="store_true", help="Do not fetch official market data before feature generation.")
    parser.add_argument("--publish-remote", action="store_true", help="Publish QuantService handoff JSON to the configured remote source after local generation.")
    parser.add_argument("--remote-provider", default=None, help="Remote publish provider override. Currently only 'gcs' is supported.")
    parser.add_argument("--remote-gcs-bucket", default=None, help="GCS bucket override for remote publish.")
    parser.add_argument("--remote-base-url", default=None, help="Base URL override exposed to QuantService for current market-analysis handoff files.")
    parser.add_argument("--remote-prefix", default=None, help="Remote object prefix override. Default is market_analysis.")
    parser.add_argument("--remote-access-mode", default=None, help="Access mode metadata, e.g. public or signed.")
    parser.add_argument("--remote-credentials", default=None, help="Optional service account JSON path for remote publish.")
    parser.add_argument("--remote-dry-run", action="store_true", help="Build and validate the remote publish plan without uploading files.")
    return parser.parse_args()


def build_remote_publish_config(args: argparse.Namespace) -> RemotePublishConfig | None:
    if not args.publish_remote:
        return None
    return RemotePublishConfig(
        enabled=True,
        provider=(args.remote_provider or RemotePublishConfig().provider),
        gcs_bucket=(args.remote_gcs_bucket or RemotePublishConfig().gcs_bucket),
        base_url=(args.remote_base_url or RemotePublishConfig().base_url),
        prefix=(args.remote_prefix or RemotePublishConfig().prefix),
        access_mode=(args.remote_access_mode or RemotePublishConfig().access_mode),
        credentials_path=Path(args.remote_credentials) if args.remote_credentials else RemotePublishConfig().credentials_path,
        dry_run=bool(args.remote_dry_run),
    )


def main() -> None:
    args = parse_args()
    remote_publish_config = build_remote_publish_config(args)
    result = run_market_analysis_pipeline(
        market=args.market,
        asof=args.asof,
        db_path=Path(args.db_path) if args.db_path else None,
        snapshot_dir=Path(args.snapshot_dir) if args.snapshot_dir else None,
        handoff_dir=Path(args.handoff_dir) if args.handoff_dir else None,
        seed_sample=args.seed_sample,
        use_quant_readonly=not args.skip_quant_readonly,
        collect_official=not args.skip_official_collect,
        remote_publish_config=remote_publish_config,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
