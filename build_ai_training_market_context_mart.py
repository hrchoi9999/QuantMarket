from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.ai_training_context_mart import build_ai_training_context_mart
from quantmarket_market.config import DEFAULT_DB_PATH, QUANT_PRICE_DB_PATH

DEFAULT_CLASSIFICATION_DB = ROOT / ".." / "Quant" / "data" / "db" / "security_classification.db"
DEFAULT_GLOBAL_CONTEXT_DB = ROOT / "data" / "db" / "global_market_context.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AI training market context mart for Quant model threads.")
    parser.add_argument("--source-qm-db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--source-price-db", default=str(QUANT_PRICE_DB_PATH))
    parser.add_argument("--source-classification-db", default=str(DEFAULT_CLASSIFICATION_DB.resolve()))
    parser.add_argument("--source-global-context-db", default=str(DEFAULT_GLOBAL_CONTEXT_DB))
    parser.add_argument("--target-db", default=str(ROOT / "data" / "db" / "market_context.db"))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "service_platform" / "ai_training" / "market_context" / "current"),
    )
    parser.add_argument(
        "--report-dir",
        default=str(ROOT / "reports" / "market_context_mart"),
    )
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_ai_training_context_mart(
        source_qm_db=Path(args.source_qm_db),
        source_price_db=Path(args.source_price_db),
        source_classification_db=Path(args.source_classification_db),
        source_global_context_db=Path(args.source_global_context_db),
        target_db=Path(args.target_db),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
        start=args.start,
        end=args.end,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": result.generated_at,
                "target_db": str(result.target_db),
                "output_dir": str(result.output_dir),
                "report_json": str(result.report_json),
                "report_md": str(result.report_md),
                "row_counts": result.row_counts,
                "date_range": result.date_range,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
