from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import FinanceDataReader as fdr

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from quantmarket_market.config import DEFAULT_DB_PATH
from quantmarket_market.db import connect, init_db, upsert_many
from quantmarket_market.official_market_data import INDEX_SPECS, _normalize_index_df


def backfill_market_index_daily(*, start_date: str, end_date: str, market: str = "KR") -> dict:
    updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    init_db(DEFAULT_DB_PATH)
    stats: dict[str, object] = {
        "db_path": str(DEFAULT_DB_PATH),
        "market": market,
        "start_date": start_date,
        "end_date": end_date,
        "index_rows": {},
        "updated_at": updated_at,
    }
    with connect(DEFAULT_DB_PATH) as con:
        for index_code, spec in INDEX_SPECS.items():
            df = fdr.DataReader(spec["fdr_symbol"], start_date, end_date)
            rows = _normalize_index_df(
                df,
                market=market,
                index_code=index_code,
                index_name=spec["name"],
                source=f"fdr_backfill:{spec['fdr_symbol']}",
                updated_at=updated_at,
            )
            upsert_many(
                con,
                table="market_index_daily",
                columns=[
                    "market",
                    "index_code",
                    "index_name",
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "value",
                    "source",
                    "updated_at",
                ],
                rows=rows,
                conflict_columns=["market", "index_code", "date"],
            )
            stats["index_rows"][spec["name"]] = len(rows)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill actual KOSPI/KOSDAQ/KOSPI200 index closes into market_index_daily.")
    parser.add_argument("--start", default="2017-01-02")
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    print(backfill_market_index_daily(start_date=args.start, end_date=args.end))


if __name__ == "__main__":
    main()
