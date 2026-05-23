from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.bea_collector import DEFAULT_BEA_API_KEY_PATH, bea_key_available, collect_bea_series  # noqa: E402
from quantmarket_market.global_context_db import DEFAULT_GLOBAL_CONTEXT_DB_PATH  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect BEA NIPA macro series.")
    parser.add_argument("--db-path", default=str(DEFAULT_GLOBAL_CONTEXT_DB_PATH))
    parser.add_argument("--api-key-path", default=str(DEFAULT_BEA_API_KEY_PATH))
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "global_context"))
    return parser.parse_args()


def build_coverage(db_path: Path) -> list[dict]:
    with sqlite3.connect(str(db_path)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT
                r.series_id,
                r.display_name,
                r.category,
                r.frequency,
                r.score_direction,
                MIN(o.asof_date) AS start_date,
                MAX(o.asof_date) AS end_date,
                COUNT(o.asof_date) AS row_count
            FROM global_series_registry r
            LEFT JOIN global_observation o
                ON r.source = o.source
               AND r.series_id = o.series_id
            WHERE r.source = 'BEA'
              AND r.is_active = 1
            GROUP BY
                r.series_id, r.display_name, r.category,
                r.frequency, r.score_direction
            ORDER BY r.category, r.series_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    if not bea_key_available(Path(args.api_key_path)):
        result = {
            "status": "skipped",
            "reason": f"BEA API key not found: {args.api_key_path}",
            "db_path": str(db_path),
            "coverage": [],
        }
        (report_dir / "bea_collection_latest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    result = collect_bea_series(
        db_path=db_path,
        api_key_path=Path(args.api_key_path),
        sleep_seconds=args.sleep,
    )
    result["coverage"] = build_coverage(db_path)
    (report_dir / "bea_collection_latest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
