from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.config import DEFAULT_DB_PATH
from quantmarket_market.db import connect, upsert_many

KST = timezone(timedelta(hours=9))
INVESTORS = ["외국인", "기관합계", "개인"]
SCOPES = ["KOSPI", "KOSDAQ"]


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def recompute_aggregate(db_path: Path, start: str, end: str) -> dict:
    updated_at = _now_kst()
    with connect(db_path) as con:
        source = pd.read_sql_query(
            """
            SELECT date, market_scope, investor, SUM(net_value) AS net_buy_value
            FROM kiwoom_stock_investor_flow_daily
            WHERE date BETWEEN ? AND ?
              AND market_scope IN ('KOSPI', 'KOSDAQ')
              AND investor IN ('외국인', '기관합계', '개인')
            GROUP BY date, market_scope, investor
            """,
            con,
            params=[start, end],
        )
        if source.empty:
            return {"status": "empty", "start": start, "end": end, "rows": 0}

        all_scope = (
            source.groupby(["date", "investor"], as_index=False)["net_buy_value"]
            .sum()
            .assign(market_scope="ALL")
        )
        out = pd.concat([source, all_scope], ignore_index=True)
        out["market"] = "KR"
        out["source"] = "kiwoom_rest_ka10059:top_universe_aggregate_recomputed"
        out["source_status"] = "proxy_top_universe_recomputed"
        out["updated_at"] = updated_at
        out = out[
            [
                "market",
                "date",
                "market_scope",
                "investor",
                "net_buy_value",
                "source",
                "source_status",
                "updated_at",
            ]
        ].sort_values(["date", "market_scope", "investor"])
        upsert_many(
            con,
            table="market_investor_flow_daily",
            columns=list(out.columns),
            rows=out.to_dict(orient="records"),
            conflict_columns=["market", "date", "market_scope", "investor"],
        )
    return {
        "status": "ok",
        "db_path": str(db_path),
        "start": start,
        "end": end,
        "rows": int(out.shape[0]),
        "dates": int(out["date"].nunique()),
        "updated_at": updated_at,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute market investor flow aggregates from Kiwoom stock-level rows.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(recompute_aggregate(args.db_path, args.start, args.end), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
