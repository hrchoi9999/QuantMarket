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
from quantmarket_market.domestic_flow_derivatives_daily import build_domestic_flow_derivatives_daily

DEFAULT_AI_FEATURE_EXT_DB = ROOT / ".." / "Quant" / "data" / "db" / "ai_feature_ext.db"
DEFAULT_CLASSIFICATION_DB = ROOT / ".." / "Quant" / "data" / "db" / "security_classification.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build domestic flow/derivatives daily features for QM market forecast mart.")
    parser.add_argument("--market-context-db", default=str(ROOT / "data" / "db" / "market_context.db"))
    parser.add_argument("--ai-feature-ext-db", default=str(DEFAULT_AI_FEATURE_EXT_DB.resolve()))
    parser.add_argument("--source-qm-db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--source-classification-db", default=str(DEFAULT_CLASSIFICATION_DB.resolve()))
    parser.add_argument("--output-dir", default=str(ROOT / "service_platform" / "ai_training" / "market_context" / "current"))
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "domestic_flow_derivatives"))
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_domestic_flow_derivatives_daily(
        market_context_db=Path(args.market_context_db),
        ai_feature_ext_db=Path(args.ai_feature_ext_db),
        source_qm_db=Path(args.source_qm_db),
        source_classification_db=Path(args.source_classification_db),
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
                "row_count": result.row_count,
                "output_csv": str(result.output_csv),
                "report_json": str(result.report_json),
                "report_md": str(result.report_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
