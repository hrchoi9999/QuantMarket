from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.quantmarket_market.config import DEFAULT_DB_PATH, ROOT_DIR
from src.quantmarket_market.db import connect, init_db
from src.quantmarket_market.krx_official_collector import collect_krx_official_market_data

KST = timezone(timedelta(hours=9))


def _today_kst() -> str:
    return datetime.now(tz=KST).date().isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect KRX official market-level investor flow data.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--market", default="KR")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD. Default: end - 120 days.")
    parser.add_argument("--end", default=_today_kst(), help="YYYY-MM-DD.")
    parser.add_argument("--cookie-header-path", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=ROOT_DIR / "reports" / "krx_official")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    end_date = args.end
    start_date = args.start or (datetime.fromisoformat(end_date).date() - timedelta(days=120)).isoformat()
    generated_at = datetime.now(tz=KST).replace(microsecond=0).isoformat()

    init_db(args.db_path)
    with connect(args.db_path) as con:
        stats = collect_krx_official_market_data(
            con,
            market=args.market,
            start_date=start_date,
            end_date=end_date,
            updated_at=generated_at,
            cookie_header_path=args.cookie_header_path,
        )

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "source_name": "krx_official_market_data",
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "db_path": str(args.db_path),
        "stats": stats,
    }
    latest_path = args.report_dir / "krx_official_market_data_latest.json"
    dated_path = args.report_dir / f"krx_official_market_data_{end_date.replace('-', '')}.json"
    for path in (latest_path, dated_path):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
