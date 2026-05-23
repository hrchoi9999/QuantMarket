from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KST = timezone(timedelta(hours=9))
SCHEMA_VERSION = "market_model_readiness.v2"
FEATURE_VERSION = "qm_market_model_readiness_v2_sqlite_training_tables_20260514"

TARGET_COLUMNS = [
    "target_forward_return",
    "target_excess_return_vs_cash",
    "target_excess_return_vs_all",
    "target_forward_max_drawdown",
    "target_forward_max_runup",
    "target_upside_flag",
    "target_downside_risk_flag",
    "target_large_upside_flag",
]


@dataclass(frozen=True)
class ReadinessResult:
    report_json: Path
    report_md: Path
    train_dataset_csv: Path
    inference_latest_csv: Path
    leakage_audit_csv: Path
    regime_report_csv: Path
    generated_at: str


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _read_table(con: sqlite3.Connection, table: str) -> pd.DataFrame:
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return pd.DataFrame()
    return pd.read_sql_query(f"SELECT * FROM {table}", con)


def _safe_corr(df: pd.DataFrame, x: str, y: str) -> float | None:
    sample = df[[x, y]].dropna()
    if len(sample) < 20:
        return None
    value = sample[x].corr(sample[y])
    return None if pd.isna(value) else round(float(value), 6)


def _safe_mean(series: pd.Series) -> float | None:
    value = pd.to_numeric(series, errors="coerce").mean()
    return None if pd.isna(value) else round(float(value), 8)


def _leakage_checks(model_input: pd.DataFrame, target: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    checks = []

    def add_check(name: str, status: str, failed_rows: int, detail: str) -> None:
        checks.append({"check_name": name, "status": status, "failed_rows": int(failed_rows), "detail": detail})

    if {"global_source_asof_date", "asof_date"}.issubset(model_input.columns):
        sample = model_input.dropna(subset=["global_source_asof_date"])
        failed = (pd.to_datetime(sample["global_source_asof_date"]) >= pd.to_datetime(sample["asof_date"])).sum()
        add_check("global_source_date_before_model_asof", "pass" if failed == 0 else "fail", failed, "global_source_asof_date must be earlier than model asof_date")

    if {"external_source_asof_date", "asof_date"}.issubset(model_input.columns):
        sample = model_input.dropna(subset=["external_source_asof_date"])
        failed = (pd.to_datetime(sample["external_source_asof_date"]) >= pd.to_datetime(sample["asof_date"])).sum()
        add_check("external_source_date_before_model_asof", "pass" if failed == 0 else "fail", failed, "external_source_asof_date must be earlier than model asof_date")

    if {"target_end_asof_date", "asof_date", "target_available_flag"}.issubset(target.columns):
        sample = target[target["target_available_flag"] == 1].dropna(subset=["target_end_asof_date"])
        failed = (pd.to_datetime(sample["target_end_asof_date"]) <= pd.to_datetime(sample["asof_date"])).sum()
        add_check("target_end_after_asof", "pass" if failed == 0 else "fail", failed, "target end date must be after asof_date")

    leaked_targets = sorted(set(feature_columns) & set(TARGET_COLUMNS))
    add_check("target_columns_excluded_from_features", "pass" if not leaked_targets else "fail", len(leaked_targets), ",".join(leaked_targets) if leaked_targets else "no target columns in feature list")

    generated_cols = [col for col in feature_columns if col.startswith("generated_at") or col.endswith("_generated_at")]
    add_check("generated_at_columns_excluded_from_features", "pass" if not generated_cols else "fail", len(generated_cols), ",".join(generated_cols) if generated_cols else "no generated_at columns in feature list")
    return pd.DataFrame(checks)


def _feature_columns(model_input: pd.DataFrame) -> list[str]:
    keys = {"asof_date", "market_scope", "forecast_horizon"}
    blocked_prefixes = ("target_",)
    blocked_contains = ("generated_at",)
    blocked_exact = {
        "schema_version",
        "feature_version",
        "coverage_policy",
        "global_pit_lag_rule",
        "external_pit_lag_rule",
    }
    cols = []
    for col in model_input.columns:
        if col in keys or col in blocked_exact:
            continue
        if col.startswith(blocked_prefixes):
            continue
        if any(token in col for token in blocked_contains):
            continue
        cols.append(col)
    return cols


def _regime_performance(validation: pd.DataFrame, model_input: pd.DataFrame) -> pd.DataFrame:
    regime_cols = [
        "market_state_label",
        "risk_regime_label",
        "volatility_regime_label",
        "regime_momentum_label",
        "coverage_quality_label",
    ]
    joined = validation.merge(
        model_input[["asof_date", "market_scope", "forecast_horizon", *regime_cols]],
        on=["asof_date", "market_scope", "forecast_horizon"],
        how="left",
        suffixes=("", "_feature"),
    )
    joined = joined[joined["target_available_flag"] == 1].copy()
    numeric_cols = [
        "target_forward_return",
        "market_forecast_score",
        "predicted_forward_return",
        "baseline_direction_hit_flag",
        "ai_direction_hit_flag",
        "baseline_forecast_error",
        "ai_forecast_error",
    ]
    for column in numeric_cols:
        if column in joined.columns:
            joined[column] = pd.to_numeric(joined[column], errors="coerce")
    rows = []
    for regime_col in regime_cols:
        for keys, g in joined.groupby(["market_scope", "forecast_horizon", regime_col], dropna=False):
            scope, horizon, regime_value = keys
            rows.append(
                {
                    "dimension": regime_col,
                    "dimension_value": regime_value,
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "rows": int(len(g)),
                    "mean_target_forward_return": _safe_mean(g["target_forward_return"]),
                    "baseline_corr": _safe_corr(g, "market_forecast_score", "target_forward_return"),
                    "ai_corr": _safe_corr(g, "predicted_forward_return", "target_forward_return"),
                    "baseline_hit_rate": _safe_mean(g["baseline_direction_hit_flag"]),
                    "ai_hit_rate": _safe_mean(g["ai_direction_hit_flag"]),
                    "baseline_mae": _safe_mean(g["baseline_forecast_error"].abs()),
                    "ai_mae": _safe_mean(g["ai_forecast_error"].abs()),
                }
            )
    return pd.DataFrame(rows)


def build_market_model_readiness(
    *,
    market_context_db: Path,
    output_dir: Path,
    report_dir: Path,
) -> ReadinessResult:
    generated_at = _now_kst()
    with _connect(market_context_db) as con:
        model_input = _read_table(con, "market_model_input_daily")
        target = _read_table(con, "market_forecast_target_daily")
        validation = _read_table(con, "market_forecast_validation_daily")
    if model_input.empty or target.empty or validation.empty:
        raise RuntimeError("model_input, target, and validation marts are required.")

    feature_columns = _feature_columns(model_input)
    train = model_input.merge(target, on=["asof_date", "market_scope", "forecast_horizon"], how="inner")
    train = train[train["target_available_flag"] == 1].copy()
    latest_asof = model_input["asof_date"].max()
    inference_latest = model_input[model_input["asof_date"] == latest_asof].copy()

    leakage = _leakage_checks(model_input, target, feature_columns)
    regime = _regime_performance(validation, model_input)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    train_csv = output_dir / "market_model_ready_train_dataset_current.csv"
    inference_csv = output_dir / "market_model_ready_inference_latest_current.csv"
    feature_json = output_dir / "market_model_ready_feature_columns_current.json"
    leakage_csv = report_dir / "market_model_leakage_audit_latest.csv"
    regime_csv = report_dir / "market_model_regime_performance_latest.csv"
    report_json = report_dir / "market_model_readiness_latest.json"
    report_md = report_dir / "market_model_readiness_latest.md"

    train.to_csv(train_csv, index=False, encoding="utf-8-sig")
    inference_latest.to_csv(inference_csv, index=False, encoding="utf-8-sig")
    leakage.to_csv(leakage_csv, index=False, encoding="utf-8-sig")
    regime.to_csv(regime_csv, index=False, encoding="utf-8-sig")
    feature_json.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "feature_version": FEATURE_VERSION,
                "generated_at": generated_at,
                "join_keys": ["asof_date", "market_scope", "forecast_horizon"],
                "feature_columns": feature_columns,
                "target_columns": TARGET_COLUMNS,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report = {
        "source_name": "QuantMarket model readiness pack",
        "schema_version": SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "generated_at": generated_at,
        "row_counts": {
            "model_input_rows": int(len(model_input)),
            "target_rows": int(len(target)),
            "validation_rows": int(len(validation)),
            "train_dataset_rows": int(len(train)),
            "inference_latest_rows": int(len(inference_latest)),
            "feature_count": int(len(feature_columns)),
        },
        "leakage_audit": leakage.to_dict("records"),
        "regime_rows": int(len(regime)),
        "paths": {
            "train_dataset_csv": str(train_csv),
            "inference_latest_csv": str(inference_csv),
            "feature_columns_json": str(feature_json),
            "leakage_audit_csv": str(leakage_csv),
            "regime_performance_csv": str(regime_csv),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS market_model_ready_train_dataset")
        con.execute("DROP TABLE IF EXISTS market_model_ready_inference_latest")
        train.to_sql("market_model_ready_train_dataset", con, if_exists="replace", index=False)
        inference_latest.to_sql("market_model_ready_inference_latest", con, if_exists="replace", index=False)
        con.commit()

    lines = [
        "# QuantMarket Model Readiness Pack",
        "",
        f"- generated_at: {generated_at}",
        f"- train_dataset_rows: {len(train)}",
        f"- inference_latest_rows: {len(inference_latest)}",
        f"- feature_count: {len(feature_columns)}",
        "",
        "## Leakage Audit",
        "",
    ]
    for row in report["leakage_audit"]:
        lines.append(f"- {row['check_name']}: {row['status']} ({row['failed_rows']})")
    lines.extend(["", "## Outputs", ""])
    for key, value in report["paths"].items():
        lines.append(f"- {key}: `{value}`")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["market_model_ready_train_dataset"] = train_csv.name
    manifest.setdefault("canonical_files", {})["market_model_ready_inference_latest"] = inference_csv.name
    manifest.setdefault("canonical_files", {})["market_model_ready_feature_columns"] = feature_json.name
    manifest.setdefault("tables", {})["market_model_ready_train_dataset"] = {
        "db_table": "market_model_ready_train_dataset",
        "file": train_csv.name,
        "row_count": int(len(train)),
        "storage_policy": "SQLite table is preferred for internal training; CSV remains canonical handoff.",
    }
    manifest.setdefault("tables", {})["market_model_ready_inference_latest"] = {
        "db_table": "market_model_ready_inference_latest",
        "file": inference_csv.name,
        "row_count": int(len(inference_latest)),
        "storage_policy": "SQLite table is preferred for internal training; CSV remains canonical handoff.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return ReadinessResult(
        report_json=report_json,
        report_md=report_md,
        train_dataset_csv=train_csv,
        inference_latest_csv=inference_csv,
        leakage_audit_csv=leakage_csv,
        regime_report_csv=regime_csv,
        generated_at=generated_at,
    )
