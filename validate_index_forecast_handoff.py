from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_HANDOFF_DIR = ROOT / "service_platform" / "index_forecast_handoff" / "current"
REQUIRED_MARKETS = ["KOSPI", "KOSDAQ", "KOSPI200"]
REQUIRED_HORIZONS = ["5d", "10d", "20d", "60d"]
ALLOWED_DIRECTIONS = {"down", "sideways", "up"}
ALLOWED_RELEASE_STAGES = {"research_beta", "production"}
REQUIRED_FILES = {
    "manifest": "index_forecast_handoff_manifest.json",
    "signal_csv": "index_forecast_signal_current.csv",
    "signal_json": "index_forecast_signal_current.json",
    "quality_report": "index_forecast_signal_quality_report.json",
    "schema": "index_forecast_signal_schema.json",
}
REQUIRED_COLUMNS = [
    "asof_date",
    "market_scope",
    "forecast_horizon",
    "label_policy",
    "model_name",
    "decision_method",
    "predicted_direction",
    "prob_down",
    "prob_sideways",
    "prob_up",
    "confidence",
    "rule_name",
    "confidence_floor",
    "recommended_exposure",
    "model_status",
    "release_stage",
    "production_ready",
]


def _read_json(path: Path, errors: list[str]) -> dict | list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid json {path.name}: {exc}")
        return {}


def _read_csv(path: Path, errors: list[str]) -> list[dict]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception as exc:
        errors.append(f"invalid csv {path.name}: {exc}")
        return []


def _to_float(value: str | None, field: str, row_key: str, errors: list[str]) -> float | None:
    try:
        if value in (None, ""):
            raise ValueError("empty")
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            raise ValueError("not finite")
        return num
    except Exception:
        errors.append(f"invalid numeric {field} at {row_key}: {value}")
        return None


def validate_handoff(
    handoff_dir: Path,
    *,
    expected_asof: str | None = None,
    require_production_ready: bool = True,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    paths = {name: handoff_dir / filename for name, filename in REQUIRED_FILES.items()}

    for name, path in paths.items():
        if not path.exists():
            errors.append(f"missing {name}: {path}")

    manifest = _read_json(paths["manifest"], errors) if paths["manifest"].exists() else {}
    quality = _read_json(paths["quality_report"], errors) if paths["quality_report"].exists() else {}
    schema = _read_json(paths["schema"], errors) if paths["schema"].exists() else {}
    rows = _read_csv(paths["signal_csv"], errors) if paths["signal_csv"].exists() else []
    json_rows = _read_json(paths["signal_json"], errors) if paths["signal_json"].exists() else []

    csv_columns = list(rows[0].keys()) if rows else []
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in csv_columns]
    if missing_cols:
        errors.append("missing required columns: " + ",".join(missing_cols))

    if not isinstance(json_rows, list):
        errors.append("signal_json is not a list")
        json_rows = []
    if rows and json_rows and len(rows) != len(json_rows):
        errors.append(f"csv/json row count mismatch: {len(rows)} != {len(json_rows)}")

    latest_asof = max((row.get("asof_date") for row in rows if row.get("asof_date")), default=None)
    target_asof = expected_asof or latest_asof or manifest.get("asof_date")
    if expected_asof and latest_asof != expected_asof:
        errors.append(f"latest_asof {latest_asof} != expected_asof {expected_asof}")
    if manifest.get("asof_date") and target_asof and manifest.get("asof_date") != target_asof:
        errors.append(f"manifest asof_date {manifest.get('asof_date')} != target_asof {target_asof}")
    if manifest.get("latest_asof_date") and latest_asof and manifest.get("latest_asof_date") != latest_asof:
        errors.append(f"manifest latest_asof_date {manifest.get('latest_asof_date')} != csv latest_asof {latest_asof}")

    release_stage = manifest.get("release_stage")
    if release_stage not in ALLOWED_RELEASE_STAGES:
        errors.append(f"invalid manifest release_stage: {release_stage}")
    if require_production_ready and manifest.get("production_ready") is not True:
        errors.append("manifest production_ready is not true")
    if quality.get("ok") is not True:
        errors.append("quality_report ok is not true")
    if quality.get("errors"):
        errors.append("quality_report has errors: " + ",".join(map(str, quality.get("errors", []))))

    schema_pk = schema.get("primary_key") if isinstance(schema, dict) else None
    if schema_pk != ["asof_date", "market_scope", "forecast_horizon"]:
        errors.append(f"invalid schema primary_key: {schema_pk}")

    required_keys = {(market, horizon) for market in REQUIRED_MARKETS for horizon in REQUIRED_HORIZONS}
    actual_keys = set()
    duplicate_keys = set()
    for row in rows:
        row_key = f"{row.get('asof_date')}:{row.get('market_scope')}:{row.get('forecast_horizon')}"
        key = (row.get("market_scope"), row.get("forecast_horizon"))
        if key in actual_keys:
            duplicate_keys.add(key)
        actual_keys.add(key)

        if row.get("asof_date") != target_asof:
            errors.append(f"non-target asof row at {row_key}")
        if row.get("market_scope") not in REQUIRED_MARKETS:
            errors.append(f"invalid market_scope at {row_key}: {row.get('market_scope')}")
        if row.get("forecast_horizon") not in REQUIRED_HORIZONS:
            errors.append(f"invalid forecast_horizon at {row_key}: {row.get('forecast_horizon')}")
        if row.get("predicted_direction") not in ALLOWED_DIRECTIONS:
            errors.append(f"invalid predicted_direction at {row_key}: {row.get('predicted_direction')}")
        if row.get("release_stage") not in ALLOWED_RELEASE_STAGES:
            errors.append(f"invalid row release_stage at {row_key}: {row.get('release_stage')}")
        if require_production_ready and str(row.get("production_ready")).lower() != "true":
            errors.append(f"row production_ready is not true at {row_key}")
        if row.get("model_status") != "ok":
            errors.append(f"model_status is not ok at {row_key}: {row.get('model_status')}")

        probs = [_to_float(row.get(col), col, row_key, errors) for col in ["prob_down", "prob_sideways", "prob_up"]]
        if all(value is not None for value in probs):
            for col, value in zip(["prob_down", "prob_sideways", "prob_up"], probs):
                if value < 0.0 or value > 1.0:
                    errors.append(f"{col} out of range at {row_key}: {value}")
            prob_sum = sum(value for value in probs if value is not None)
            if abs(prob_sum - 1.0) > 0.0001:
                errors.append(f"probability sum != 1 at {row_key}: {prob_sum:.6f}")
        for col in ["confidence", "confidence_floor", "recommended_exposure"]:
            value = _to_float(row.get(col), col, row_key, errors)
            if value is not None and (value < 0.0 or value > 1.0):
                errors.append(f"{col} out of range at {row_key}: {value}")

    missing_keys = sorted(required_keys - actual_keys)
    if missing_keys:
        errors.append("missing market/horizon rows: " + ",".join(f"{m}:{h}" for m, h in missing_keys))
    if duplicate_keys:
        errors.append("duplicate market/horizon rows: " + ",".join(f"{m}:{h}" for m, h in sorted(duplicate_keys)))

    return {
        "ok": not errors,
        "handoff_dir": str(handoff_dir),
        "target_asof": target_asof,
        "latest_asof": latest_asof,
        "release_stage": release_stage,
        "required_markets": REQUIRED_MARKETS,
        "required_horizons": REQUIRED_HORIZONS,
        "row_count": len(rows),
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate QuantMarket index forecast handoff contract.")
    parser.add_argument("--handoff-dir", default=str(DEFAULT_HANDOFF_DIR))
    parser.add_argument("--expected-asof", default=None)
    parser.add_argument("--allow-not-production-ready", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = validate_handoff(
        Path(args.handoff_dir),
        expected_asof=args.expected_asof,
        require_production_ready=not args.allow_not_production_ready,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
