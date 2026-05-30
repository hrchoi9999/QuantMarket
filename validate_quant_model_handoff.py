from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_HANDOFF_DIR = ROOT / "service_platform" / "quant_model_handoff" / "market_context" / "current"
REQUIRED_SCOPES = ["ALL", "KOSPI", "KOSDAQ"]
REQUIRED_HORIZON = "20d"


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_handoff(handoff_dir: Path, expected_asof: str | None = None) -> dict:
    manifest_path = handoff_dir / "quant_model_handoff_manifest.json"
    primary_path = handoff_dir / "market_forecast_ai_calibrated_daily_current.csv"
    errors: list[str] = []

    if not manifest_path.exists():
        errors.append(f"missing manifest: {manifest_path}")
        manifest = {}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if not primary_path.exists():
        errors.append(f"missing primary forecast: {primary_path}")
        rows = []
    else:
        rows = _read_csv(primary_path)

    latest_asof = max((row.get("asof_date") for row in rows if row.get("asof_date")), default=None)
    target_asof = expected_asof or latest_asof or manifest.get("asof_date")
    matched = [
        row
        for row in rows
        if row.get("asof_date") == target_asof
        and row.get("forecast_horizon") == REQUIRED_HORIZON
        and row.get("market_scope") in REQUIRED_SCOPES
    ]
    matched_scopes = sorted({row.get("market_scope") for row in matched})
    missing_scopes = [scope for scope in REQUIRED_SCOPES if scope not in matched_scopes]
    if missing_scopes:
        errors.append(f"missing {REQUIRED_HORIZON} primary forecast scopes for {target_asof}: {','.join(missing_scopes)}")
    if expected_asof and latest_asof != expected_asof:
        errors.append(f"latest primary forecast asof {latest_asof} != expected_asof {expected_asof}")
    if manifest.get("status", {}).get("production_ready") is not True:
        errors.append("manifest status.production_ready is not true")
    if manifest.get("asof_date") and target_asof and manifest.get("asof_date") != target_asof:
        errors.append(f"manifest asof_date {manifest.get('asof_date')} != target_asof {target_asof}")

    return {
        "ok": not errors,
        "handoff_dir": str(handoff_dir),
        "manifest": str(manifest_path),
        "primary_forecast": str(primary_path),
        "target_asof": target_asof,
        "latest_asof": latest_asof,
        "required_horizon": REQUIRED_HORIZON,
        "required_scopes": REQUIRED_SCOPES,
        "matched_scopes": matched_scopes,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate QuantMarket handoff contract for Quant --model-run-only.")
    parser.add_argument("--handoff-dir", default=str(DEFAULT_HANDOFF_DIR))
    parser.add_argument("--expected-asof", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = validate_handoff(Path(args.handoff_dir), expected_asof=args.expected_asof)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
