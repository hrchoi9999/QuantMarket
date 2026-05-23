from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.config import QUANT_PRICE_DB_PATH
from quantmarket_market.market_forecast_ai_calibration import build_market_forecast_ai_calibration


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build walk-forward AI calibration layer for QuantMarket market forecast mart.")
    parser.add_argument("--market-context-db", default=str(ROOT / "data" / "db" / "market_context.db"))
    parser.add_argument("--price-db", default=str(QUANT_PRICE_DB_PATH))
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "service_platform" / "ai_training" / "market_context" / "current"),
    )
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "market_forecast_ai_calibration"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_market_forecast_ai_calibration(
        market_context_db=Path(args.market_context_db),
        price_db=Path(args.price_db),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": result.generated_at,
                "row_count": result.row_count,
                "calibrated_csv": str(result.calibrated_csv),
                "validation_csv": str(result.validation_csv),
                "report_json": str(result.report_json),
                "report_md": str(result.report_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

