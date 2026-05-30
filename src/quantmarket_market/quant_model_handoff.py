from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from quantmarket_market.config import ROOT_DIR


KST = timezone(timedelta(hours=9))

HANDOFF_FILES = [
    "market_model_input_daily_current.csv",
    "domestic_flow_derivatives_daily_current.csv",
    "macro_event_calendar_daily_current.csv",
    "macro_surprise_context_daily_current.csv",
    "macro_surprise_event_daily_current.csv",
    "market_forecast_ai_calibrated_daily_current.csv",
    "market_forecast_monitoring_daily_current.csv",
    "market_forecast_target_daily_current.csv",
    "market_forecast_validation_daily_current.csv",
    "market_forecast_ai_v1_1_predictions_current.csv",
    "market_forecast_ai_v1_1_feature_set_current.json",
    "theme_context_daily_quant_bucket_current.csv",
    "theme_bucket_crosswalk_current.csv",
    "market_model_ready_feature_columns_current.json",
    "market_model_ready_inference_latest_current.csv",
    "market_model_ready_train_dataset_current.csv",
    "manifest.json",
    "schema.json",
]

REQUIRED_PRIMARY_FORECAST_HORIZON = "20d"
REQUIRED_PRIMARY_MARKET_SCOPES = ["ALL", "KOSPI", "KOSDAQ"]


def now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _read_csv_dicts(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def primary_forecast_contract(handoff_dir: Path, expected_asof: str | None = None) -> dict:
    primary_path = handoff_dir / "market_forecast_ai_calibrated_daily_current.csv"
    if not primary_path.exists():
        return {
            "ready": False,
            "asof_date": None,
            "latest_asof_date": None,
            "expected_asof_date": expected_asof,
            "required_horizon": REQUIRED_PRIMARY_FORECAST_HORIZON,
            "required_market_scopes": REQUIRED_PRIMARY_MARKET_SCOPES,
            "matched_rows": 0,
            "missing_scopes": REQUIRED_PRIMARY_MARKET_SCOPES,
            "failure_reason": f"missing primary forecast file: {primary_path}",
        }

    rows = _read_csv_dicts(primary_path)
    asof_dates = sorted({row.get("asof_date") for row in rows if row.get("asof_date")})
    latest_asof = asof_dates[-1] if asof_dates else None
    target_asof = expected_asof or latest_asof
    matched = [
        row
        for row in rows
        if row.get("asof_date") == target_asof
        and row.get("forecast_horizon") == REQUIRED_PRIMARY_FORECAST_HORIZON
        and row.get("market_scope") in REQUIRED_PRIMARY_MARKET_SCOPES
    ]
    matched_scopes = sorted({row.get("market_scope") for row in matched})
    missing_scopes = [scope for scope in REQUIRED_PRIMARY_MARKET_SCOPES if scope not in matched_scopes]
    missing_prediction_scopes = [
        row.get("market_scope")
        for row in matched
        if row.get("predicted_forward_return") in (None, "", "nan", "NaN")
    ]
    ready = bool(target_asof) and not missing_scopes and not missing_prediction_scopes
    failure_reasons = []
    if expected_asof and latest_asof != expected_asof:
        failure_reasons.append(f"latest_asof {latest_asof} != expected_asof {expected_asof}")
    if missing_scopes:
        failure_reasons.append(f"missing required scopes for {target_asof}: {','.join(missing_scopes)}")
    if missing_prediction_scopes:
        failure_reasons.append(f"missing predicted_forward_return scopes: {','.join(missing_prediction_scopes)}")
    return {
        "ready": ready and (not expected_asof or latest_asof == expected_asof),
        "asof_date": target_asof,
        "latest_asof_date": latest_asof,
        "expected_asof_date": expected_asof,
        "required_horizon": REQUIRED_PRIMARY_FORECAST_HORIZON,
        "required_market_scopes": REQUIRED_PRIMARY_MARKET_SCOPES,
        "matched_rows": len(matched),
        "matched_scopes": matched_scopes,
        "missing_scopes": missing_scopes,
        "missing_prediction_scopes": missing_prediction_scopes,
        "failure_reason": "; ".join(failure_reasons) if failure_reasons else None,
        "primary_forecast_file": primary_path.name,
    }


def _file_meta(path: Path) -> dict:
    stat = path.stat()
    return {
        "file": path.name,
        "bytes": int(stat.st_size),
        "last_modified_local": datetime.fromtimestamp(stat.st_mtime, tz=KST).replace(microsecond=0).isoformat(),
    }


def refresh_quant_model_handoff(
    *,
    generated_at: str,
    expected_asof: str | None = None,
    source_dir: Path | None = None,
    handoff_dir: Path | None = None,
) -> dict:
    source_dir = source_dir or ROOT_DIR / "service_platform" / "ai_training" / "market_context" / "current"
    handoff_dir = handoff_dir or ROOT_DIR / "service_platform" / "quant_model_handoff" / "market_context" / "current"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    file_meta = {}
    for file_name in HANDOFF_FILES:
        src = source_dir / file_name
        if not src.exists():
            raise FileNotFoundError(f"Missing handoff source file: {src}")
        dst = handoff_dir / file_name
        shutil.copy2(src, dst)
        copied.append(file_name)
        file_meta[file_name] = _file_meta(dst)

    manifest_path = handoff_dir / "quant_model_handoff_manifest.json"
    primary_contract = primary_forecast_contract(handoff_dir, expected_asof=expected_asof)
    production_ready = bool(primary_contract["ready"])
    manifest = {
        "source_name": "QuantMarket to Quant model market context handoff",
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "handoff_version": "quant_model_market_context_handoff.v2_20260515",
        "asof_date": primary_contract["asof_date"],
        "latest_asof_date": primary_contract["latest_asof_date"],
        "expected_asof_date": expected_asof,
        "primary_policy": "Use ridge calibration as current production primary until Quant model review accepts AI v1.1 promotion. Daily AI v1.1 uses fast/pruned training; full candidate comparison can be run separately.",
        "join_keys": ["asof_date", "market_scope", "forecast_horizon"],
        "theme_join_keys": ["asof_date", "quant_theme_bucket"],
        "data_contract": {
            "required_for_quant_model_run": {
                "primary_forecast": "market_forecast_ai_calibrated_daily_current.csv",
                "forecast_horizon": REQUIRED_PRIMARY_FORECAST_HORIZON,
                "market_scopes": REQUIRED_PRIMARY_MARKET_SCOPES,
                "asof_date_policy": "Must match Quant --data-refresh-only asof before Quant --model-run-only.",
                "production_ready_required": True,
            }
        },
        "files": {
            "primary_market_input": "market_model_input_daily_current.csv",
            "domestic_flow_derivatives": "domestic_flow_derivatives_daily_current.csv",
            "macro_event_calendar": "macro_event_calendar_daily_current.csv",
            "macro_surprise_context": "macro_surprise_context_daily_current.csv",
            "macro_surprise_events": "macro_surprise_event_daily_current.csv",
            "primary_forecast": "market_forecast_ai_calibrated_daily_current.csv",
            "monitoring": "market_forecast_monitoring_daily_current.csv",
            "target": "market_forecast_target_daily_current.csv",
            "validation": "market_forecast_validation_daily_current.csv",
            "research_ai_v1_1_predictions": "market_forecast_ai_v1_1_predictions_current.csv",
            "research_ai_v1_1_feature_set": "market_forecast_ai_v1_1_feature_set_current.json",
            "theme_context": "theme_context_daily_quant_bucket_current.csv",
            "theme_crosswalk": "theme_bucket_crosswalk_current.csv",
            "feature_columns": "market_model_ready_feature_columns_current.json",
            "ready_inference_latest": "market_model_ready_inference_latest_current.csv",
            "ready_train_dataset": "market_model_ready_train_dataset_current.csv",
            "source_manifest": "manifest.json",
            "source_schema": "schema.json",
        },
        "recommended_usage": [
            "Use forecast_horizon=20d first.",
            "Join KOSPI/KOSDAQ by stock listing market.",
            "Use ALL as broad market context.",
            "Use calibrated ridge forecast as current production primary unless Quant model explicitly switches primary.",
            "Review AI v1.1 fast/pruned output as a daily research feature; run full mode separately for formal promotion tests.",
            "Use domestic_flow_derivatives for daily investor flow, smart-money, futures, and program-pressure context with availability flags.",
            "Use macro_event_calendar as PIT-safe event flags only; V1 does not contain macro surprise values.",
            "Use macro_surprise_context as FRED actual-only proxy surprise. Consensus fields are reserved and currently null.",
            "Do not zero-fill nulls before checking coverage flags.",
        ],
        "readiness_checks": {
            "primary_forecast_contract": primary_contract,
            "file_count": len(copied),
        },
        "file_meta": file_meta,
        "status": {
            "primary_forecast_model": "ridge_calibration",
            "ai_v1_1_status": "daily_fast_research_feature",
            "production_ready": production_ready,
            "failure_reason": None if production_ready else primary_contract.get("failure_reason"),
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"handoff_dir": str(handoff_dir), "manifest": str(manifest_path), "copied_files": copied}
