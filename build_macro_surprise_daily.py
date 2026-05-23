from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.macro_surprise_daily import build_macro_surprise_daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PIT-safe macro surprise proxy mart for QuantMarket.")
    parser.add_argument("--market-context-db", default=str(ROOT / "data" / "db" / "market_context.db"))
    parser.add_argument("--global-context-db", default=str(ROOT / "data" / "db" / "global_market_context.db"))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "service_platform" / "ai_training" / "market_context" / "current"),
    )
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "macro_surprise"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_macro_surprise_daily(
        market_context_db=Path(args.market_context_db),
        global_context_db=Path(args.global_context_db),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": result.generated_at,
                "event_row_count": result.event_row_count,
                "context_row_count": result.context_row_count,
                "event_csv": str(result.event_csv),
                "context_csv": str(result.context_csv),
                "report_json": str(result.report_json),
                "report_md": str(result.report_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
