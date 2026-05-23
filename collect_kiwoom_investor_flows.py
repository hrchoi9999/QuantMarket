from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.quantmarket_market.config import DEFAULT_DB_PATH, ROOT_DIR
from src.quantmarket_market.db import connect, init_db
from src.quantmarket_market.kiwoom_investor_flow_collector import DEFAULT_UNIVERSE_FILE, collect_kiwoom_investor_flows

KST = timezone(timedelta(hours=9))


def _today_kst() -> str:
    return datetime.now(tz=KST).date().isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Kiwoom REST investor flow data into QuantMarket DB.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--universe-file", type=Path, default=DEFAULT_UNIVERSE_FILE)
    parser.add_argument("--end", default=_today_kst(), help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD or YYYYMMDD. Default: end - 7 days.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--report-dir", type=Path, default=ROOT_DIR / "reports" / "kiwoom")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    end_date = datetime.strptime(args.end.replace("-", ""), "%Y%m%d").date().isoformat()
    start_date = args.start
    if start_date is None:
        start_date = (datetime.fromisoformat(end_date).date() - timedelta(days=7)).isoformat()
    generated_at = datetime.now(tz=KST).replace(microsecond=0).isoformat()

    init_db(args.db_path)
    with connect(args.db_path) as con:
        result = collect_kiwoom_investor_flows(
            con,
            universe_file=args.universe_file,
            end=end_date,
            start=start_date,
            limit=args.limit,
            sleep=max(0.0, float(args.sleep)),
        )

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "source_name": "kiwoom_investor_flows",
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "db_path": str(args.db_path),
        "result": result,
    }
    latest_path = args.report_dir / "kiwoom_investor_flows_latest.json"
    dated_path = args.report_dir / f"kiwoom_investor_flows_{end_date.replace('-', '')}.json"
    for path in (latest_path, dated_path):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
