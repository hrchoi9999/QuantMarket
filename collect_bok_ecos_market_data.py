from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.bok_ecos_collector import (  # noqa: E402
    DEFAULT_BOK_API_KEY_PATH,
    collect_bok_ecos_market_data,
)
from quantmarket_market.config import DEFAULT_DB_PATH  # noqa: E402
from quantmarket_market.db import connect, init_db  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect BOK ECOS KR FX/rate market data.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--api-key-path", default=str(DEFAULT_BOK_API_KEY_PATH))
    parser.add_argument("--market", default="KR")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD. Default: 730 days ago.")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD. Default: today.")
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "bok_ecos"))
    return parser.parse_args()


def build_coverage(db_path: Path, *, market: str) -> dict:
    with sqlite3.connect(str(db_path)) as con:
        con.row_factory = sqlite3.Row
        fx = con.execute(
            """
            SELECT series_code code, series_name name, source,
                   MIN(date) start_date, MAX(date) end_date, COUNT(*) row_count
            FROM market_fx_daily
            WHERE market = ? AND source LIKE 'bok_ecos:%'
            GROUP BY series_code, series_name, source
            ORDER BY series_code
            """,
            (market,),
        ).fetchall()
        rates = con.execute(
            """
            SELECT rate_code code, rate_name name, source,
                   MIN(date) start_date, MAX(date) end_date, COUNT(*) row_count
            FROM market_rates_daily
            WHERE market = ? AND source LIKE 'bok_ecos:%'
            GROUP BY rate_code, rate_name, source
            ORDER BY rate_code
            """,
            (market,),
        ).fetchall()
    return {"fx": [dict(row) for row in fx], "rates": [dict(row) for row in rates]}


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    end_date = args.end or date.today().isoformat()
    start_date = args.start or (date.today() - timedelta(days=730)).isoformat()
    init_db(db_path)
    with connect(db_path) as con:
        result = collect_bok_ecos_market_data(
            con,
            market=args.market,
            start_date=start_date,
            end_date=end_date,
            updated_at=date.today().isoformat(),
            api_key_path=Path(args.api_key_path),
            sleep_seconds=args.sleep,
        )
    result["coverage"] = build_coverage(db_path, market=args.market)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    latest_path = report_dir / "bok_ecos_collection_latest.json"
    latest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
