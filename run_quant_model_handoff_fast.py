from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.quant_model_handoff import now_kst, refresh_quant_model_handoff
from validate_quant_model_handoff import validate_handoff


FAILURE_MESSAGE = (
    "forecast/context outputs are not ready for expected_asof. "
    "Request the market-analysis thread to refresh market_model_input and calibrated forecast outputs."
)

EXCLUDED_STEPS = [
    "collectors",
    "build_market_forecast_ai_model_v1_1.py",
    "compare_market_forecast_ai_v1_1_vs_calibration.py",
    "AI training",
    "model comparison",
    "model promotion",
    "threshold/label/calibration policy changes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fast Quant model handoff runner. Copies already-confirmed QuantMarket current "
            "market-context outputs into service_platform/quant_model_handoff and validates "
            "the Quant --model-run-only contract."
        )
    )
    parser.add_argument(
        "--expected-asof",
        required=True,
        help="Expected Quant data-refresh asof date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="Print a failed validation report without returning a non-zero exit code.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = now_kst()
    report: dict = {
        "mode": "fast_handoff_only",
        "generated_at": generated_at,
        "expected_asof": args.expected_asof,
        "excluded_steps": EXCLUDED_STEPS,
    }

    try:
        handoff = refresh_quant_model_handoff(generated_at=generated_at, expected_asof=args.expected_asof)
        validation = validate_handoff(Path(handoff["handoff_dir"]), expected_asof=args.expected_asof)
        ok = bool(validation["ok"])
        report.update(
            {
                "status": "ok" if ok else "failed",
                "handoff": handoff,
                "validation": validation,
            }
        )
        if not ok:
            report["failure_message"] = FAILURE_MESSAGE
    except Exception as exc:
        report.update(
            {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "failure_message": FAILURE_MESSAGE,
            }
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok" and not args.allow_stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
