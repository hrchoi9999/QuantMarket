from __future__ import annotations

import json
import os
import subprocess
import sys
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.quant_model_handoff import now_kst as _now_kst
from quantmarket_market.quant_model_handoff import refresh_quant_model_handoff

STEPS = [
    "collect_treasury_yield_curve.py",
    "collect_fred_global_data.py",
    "collect_bls_global_data.py",
    "collect_bea_global_data.py",
    "collect_eia_global_data.py",
    "collect_kiwoom_investor_flows.py",
    "build_global_context_features.py",
    "collect_yahoo_global_assets.py",
    "build_external_market_context_features.py",
    "build_ai_training_market_context_mart.py",
    "build_domestic_flow_derivatives_daily.py",
    "build_macro_event_calendar_daily.py",
    "build_macro_surprise_daily.py",
    "build_market_forecast_ai_calibration.py",
    "build_market_model_input_mart.py",
    "validate_market_forecast_daily.py",
    "build_market_forecast_monitoring_mart.py",
    "build_market_model_readiness.py",
    ("build_market_forecast_ai_model_v1_1.py", "--model-mode", "fast"),
    "compare_market_forecast_ai_v1_1_vs_calibration.py",
]

def _step_command(step: str | tuple[str, ...]) -> list[str]:
    if isinstance(step, tuple):
        script_name, *args = step
        return [sys.executable, str(ROOT / script_name), *args]
    return [sys.executable, str(ROOT / step)]


def _step_name(step: str | tuple[str, ...]) -> str:
    return step[0] if isinstance(step, tuple) else step


def _run_step(step: str | tuple[str, ...]) -> dict:
    started_at = _now_kst()
    env = os.environ.copy()
    env.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
    proc = subprocess.run(
        _step_command(step),
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        env=env,
    )
    ended_at = _now_kst()
    result = {
        "script": _step_name(step),
        "command": _step_command(step),
        "started_at": started_at,
        "ended_at": ended_at,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    if proc.returncode != 0:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QuantMarket daily AI training market-context update.")
    parser.add_argument(
        "--expected-asof",
        default=None,
        help="Optional Quant data-refresh asof_date. Handoff production_ready becomes false if primary forecast latest asof differs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = _now_kst()
    step_results = []
    for step in STEPS:
        step_results.append(_run_step(step))
    handoff = refresh_quant_model_handoff(generated_at=_now_kst(), expected_asof=args.expected_asof)

    report = {
        "status": "ok",
        "generated_at": generated_at,
        "completed_at": _now_kst(),
        "timezone": "Asia/Seoul",
        "steps": step_results,
        "handoff": handoff,
    }
    report_dir = ROOT / "reports" / "market_ai_training_daily_update"
    report_dir.mkdir(parents=True, exist_ok=True)
    latest_path = report_dir / "market_ai_training_daily_update_latest.json"
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "report": str(latest_path), "handoff_manifest": handoff["manifest"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
