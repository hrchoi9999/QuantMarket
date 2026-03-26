from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.config import ADMIN_HANDOFF_DIR, ADMIN_SNAPSHOT_DIR, DEFAULT_DB_PATH
from quantmarket_market.db import connect, init_db
from quantmarket_market.intraday_market import collect_intraday_market_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QuantMarket intraday market snapshot pipeline.")
    parser.add_argument("--market", default="KR")
    parser.add_argument("--asof", default=None)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--admin-snapshot-dir", default=None)
    parser.add_argument("--admin-handoff-dir", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path) if args.db_path else DEFAULT_DB_PATH
    admin_snapshot_dir = Path(args.admin_snapshot_dir) if args.admin_snapshot_dir else ADMIN_SNAPSHOT_DIR
    admin_handoff_dir = Path(args.admin_handoff_dir) if args.admin_handoff_dir else ADMIN_HANDOFF_DIR
    init_db(db_path)
    with connect(db_path) as con:
        artifacts = collect_intraday_market_snapshot(
            con,
            market=args.market,
            asof=args.asof,
            snapshot_dir=admin_snapshot_dir,
            handoff_dir=admin_handoff_dir,
        )
    print(json.dumps({
        "market": artifacts.summary.get("market"),
        "asof": artifacts.summary.get("asof"),
        "session_status": artifacts.summary.get("session_status"),
        "direction_label": artifacts.summary.get("direction_label"),
        "total_score": artifacts.summary.get("total_score"),
        "summary_line": artifacts.summary.get("summary_line"),
        "admin_snapshot_dir": str(admin_snapshot_dir),
        "admin_handoff_dir": str(admin_handoff_dir),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
