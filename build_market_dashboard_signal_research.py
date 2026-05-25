from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.config import DEFAULT_DB_PATH
from quantmarket_market.market_dashboard_signal_research import build_market_dashboard_signal_research


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build separate research mart for market dashboard 3-axis signals."
    )
    parser.add_argument("--source-db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--target-db", default=str(ROOT / "data" / "db" / "market_dashboard_signal_research.db"))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current"),
    )
    parser.add_argument(
        "--report-dir",
        default=str(ROOT / "reports" / "market_dashboard_signal_research"),
    )
    parser.add_argument("--market", default="KR")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_market_dashboard_signal_research(
        source_db=Path(args.source_db),
        target_db=Path(args.target_db),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
        market=args.market,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": result.generated_at,
                "source_db": str(result.source_db),
                "target_db": str(result.target_db),
                "output_dir": str(result.output_dir),
                "report_dir": str(result.report_dir),
                "row_counts": result.row_counts,
                "latest_signal": result.latest_signal,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
