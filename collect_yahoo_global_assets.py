from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.yahoo_global_assets import collect_yahoo_global_assets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Yahoo global ETF/asset daily data into QuantMarket global context DB.")
    parser.add_argument("--db", default=str(ROOT / "data" / "db" / "global_market_context.db"))
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--sleep", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = collect_yahoo_global_assets(
        db_path=Path(args.db),
        start=args.start,
        end=args.end,
        sleep_seconds=args.sleep,
    )
    report_dir = ROOT / "reports" / "global_context"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "yahoo_global_assets_collection_latest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

