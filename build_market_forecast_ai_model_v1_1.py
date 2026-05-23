from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.market_forecast_ai_model_v1_1 import build_market_forecast_ai_model_v1_1


def parse_args() -> argparse.Namespace:
    current = ROOT / "service_platform" / "ai_training" / "market_context" / "current"
    parser = argparse.ArgumentParser(description="Train QuantMarket market forecast AI model v1.1.")
    parser.add_argument("--train-dataset-csv", default=str(current / "market_model_ready_train_dataset_current.csv"))
    parser.add_argument("--inference-latest-csv", default=str(current / "market_model_ready_inference_latest_current.csv"))
    parser.add_argument("--market-context-db", default=str(ROOT / "data" / "db" / "market_context.db"))
    parser.add_argument("--output-dir", default=str(current))
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "market_forecast_ai_model_v1_1"))
    parser.add_argument("--model-dir", default=str(ROOT / "models" / "market_forecast_ai_v1_1"))
    parser.add_argument(
        "--model-mode",
        choices=["fast", "balanced", "full"],
        default="fast",
        help="fast=ridge only for daily updates, balanced=ridge+hgb, full=ridge+elasticnet+hgb",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_market_forecast_ai_model_v1_1(
        train_dataset_csv=Path(args.train_dataset_csv),
        inference_latest_csv=Path(args.inference_latest_csv),
        market_context_db=Path(args.market_context_db),
        output_dir=Path(args.output_dir),
        report_dir=Path(args.report_dir),
        model_dir=Path(args.model_dir),
        model_mode=args.model_mode,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": result.generated_at,
                "row_count": result.row_count,
                "prediction_csv": str(result.prediction_csv),
                "feature_set_json": str(result.feature_set_json),
                "report_json": str(result.report_json),
                "report_md": str(result.report_md),
                "model_dir": str(result.model_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
