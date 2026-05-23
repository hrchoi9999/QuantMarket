from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

KST = timezone(timedelta(hours=9))

MODEL_VERSION = "qm_market_forecast_ai_v1_1_fast_pruned_20260514"
SCHEMA_VERSION = "market_forecast_ai_model_v1_1"
TARGET_COLUMN = "target_forward_return"
MIN_TRAIN_ROWS = 756
REFIT_INTERVAL = 20
MAX_FEATURES = 64
MIN_FEATURE_AVAILABLE_RATE = 0.03

CURATED_FEATURES = [
    "market_forecast_score",
    "calibrated_forecast_score",
    "calibration_confidence_score",
    "market_state_score",
    "trend_score",
    "breadth_score",
    "risk_score",
    "risk_on_score",
    "risk_off_score",
    "expected_volatility_score",
    "drawdown_risk_score",
    "upside_participation_score",
    "global_risk_on_score",
    "external_macro_pressure_score",
    "external_asset_risk_on_score",
    "korea_proxy_momentum_score",
    "us_equity_momentum_score",
    "credit_proxy_score",
    "safe_haven_pressure_score",
    "domestic_flow_derivatives_score",
    "smart_money_score_5d",
    "smart_money_score_20d",
    "foreign_net_buy_ratio_5d",
    "foreign_net_buy_ratio_20d",
    "institution_net_buy_ratio_5d",
    "institution_net_buy_ratio_20d",
    "futures_direction_score",
    "program_pressure_score",
    "derivatives_pressure_score",
    "macro_event_pressure_score",
    "macro_event_count",
    "scheduled_macro_event_count",
    "macro_shock_event_count",
    "major_macro_event_flag",
    "macro_event_risk_window_flag",
    "days_since_scheduled_macro_event",
    "days_to_next_scheduled_macro_event",
    "macro_event_density_5d",
    "inflation_release_flag",
    "employment_release_flag",
    "policy_rate_release_flag",
    "rate_shock_event_flag",
    "fx_shock_event_flag",
    "vix_shock_event_flag",
    "credit_shock_event_flag",
    "macro_surprise_risk_off_score",
    "macro_surprise_pressure_score",
    "macro_surprise_relief_score",
    "macro_surprise_event_count",
    "macro_surprise_abs_zscore_max",
    "inflation_surprise_risk_off_score",
    "employment_surprise_risk_off_score",
    "policy_surprise_risk_off_score",
    "wage_surprise_risk_off_score",
    "macro_surprise_event_density_63d",
    "vix_market_stress_score",
    "semiconductor_momentum_score",
    "global_ex_us_momentum_score",
    "em_vs_dm_score",
    "asia_risk_on_score",
    "bank_stress_relief_score",
    "rate_sensitive_cyclical_score",
    "transport_cyclical_score",
    "low_vol_defensive_pressure_score",
    "crypto_risk_appetite_score",
    "market_state_score_delta_5d",
    "market_state_score_delta_20d",
    "trend_score_delta_5d",
    "breadth_score_delta_5d",
    "risk_on_score_delta_5d",
    "risk_off_score_delta_5d",
    "global_risk_on_score_delta_5d",
    "external_asset_risk_on_score_delta_5d",
    "market_forecast_score_delta_5d",
    "market_forecast_score_delta_20d",
    "market_forecast_score_acceleration_5d",
    "transition_count_20d",
    "days_since_state_change",
    "regime_stability_score",
    "overall_feature_coverage_ratio",
    "forecast_context_coverage_ratio",
    "domestic_market_context_coverage_ratio",
    "risk_context_coverage_ratio",
    "domestic_flow_derivatives_context_coverage_ratio",
    "macro_event_context_coverage_ratio",
    "macro_surprise_context_coverage_ratio",
    "global_macro_context_coverage_ratio",
    "external_market_context_coverage_ratio",
    "ai_calibration_context_coverage_ratio",
    "regime_change_context_coverage_ratio",
]


@dataclass(frozen=True)
class AiModelV11Result:
    prediction_csv: Path
    report_json: Path
    report_md: Path
    feature_set_json: Path
    model_dir: Path
    generated_at: str
    row_count: int


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _read_table(con: sqlite3.Connection, table: str) -> pd.DataFrame:
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return pd.DataFrame()
    return pd.read_sql_query(f"SELECT * FROM {table}", con)


def _read_training_inputs(
    *,
    train_dataset_csv: Path,
    inference_latest_csv: Path,
    market_context_db: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    with _connect(market_context_db) as con:
        train = _read_table(con, "market_model_ready_train_dataset")
        inference = _read_table(con, "market_model_ready_inference_latest")
    if not train.empty and not inference.empty:
        return train, inference, "sqlite"
    return pd.read_csv(train_dataset_csv), pd.read_csv(inference_latest_csv), "csv"


def _numeric_features(df: pd.DataFrame) -> list[str]:
    selected: list[str] = []
    for feature in CURATED_FEATURES:
        if feature not in df.columns:
            continue
        series = pd.to_numeric(df[feature], errors="coerce")
        if float(series.notna().mean()) < MIN_FEATURE_AVAILABLE_RATE:
            continue
        if series.dropna().nunique() <= 1:
            continue
        selected.append(feature)
        if len(selected) >= MAX_FEATURES:
            break
    return selected


def _model_names_for_mode(model_mode: str) -> list[str]:
    if model_mode == "fast":
        return ["ridge"]
    if model_mode == "balanced":
        return ["ridge", "hgb"]
    if model_mode == "full":
        return ["ridge", "elasticnet", "hgb"]
    raise ValueError(f"Unknown model_mode: {model_mode}")


def _pipeline(model_name: str) -> Pipeline:
    if model_name == "ridge":
        model = Ridge(alpha=3.0)
    elif model_name == "elasticnet":
        model = ElasticNet(alpha=0.0008, l1_ratio=0.15, max_iter=10000, random_state=42)
    elif model_name == "hgb":
        model = HistGradientBoostingRegressor(
            max_iter=90,
            learning_rate=0.035,
            max_leaf_nodes=11,
            l2_regularization=0.15,
            random_state=42,
        )
    else:
        raise ValueError(f"Unknown model_name: {model_name}")
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", model),
        ]
    )


def _label_from_prediction(pred: float | None, std: float | None) -> str | None:
    if pred is None or pd.isna(pred) or not std:
        return None
    z = pred / std
    if z >= 0.75:
        return "bullish"
    if z >= 0.2:
        return "mild_bullish"
    if z > -0.2:
        return "neutral"
    if z > -0.75:
        return "mild_bearish"
    return "bearish"


def _metrics(frame: pd.DataFrame, pred_col: str) -> dict:
    sample = frame.dropna(subset=[TARGET_COLUMN, pred_col]).copy()
    if sample.empty:
        return {}
    corr = sample[pred_col].corr(sample[TARGET_COLUMN])
    return {
        "rows": int(len(sample)),
        "start_date": str(sample["asof_date"].min()),
        "end_date": str(sample["asof_date"].max()),
        "prediction_corr": None if pd.isna(corr) else round(float(corr), 6),
        "directional_hit_rate": round(float((np.sign(sample[pred_col]) == np.sign(sample[TARGET_COLUMN])).mean()), 6),
        "mae": round(float(mean_absolute_error(sample[TARGET_COLUMN], sample[pred_col])), 8),
        "rmse": round(float(np.sqrt(mean_squared_error(sample[TARGET_COLUMN], sample[pred_col]))), 8),
    }


def _walk_forward_predict(group: pd.DataFrame, features: list[str], model_name: str) -> pd.DataFrame:
    group = group.sort_values("asof_date").reset_index(drop=True).copy()
    pred_col = f"{model_name}_predicted_forward_return"
    group[pred_col] = np.nan
    idx = MIN_TRAIN_ROWS
    while idx < len(group):
        end_idx = min(idx + REFIT_INTERVAL, len(group))
        train = group.iloc[:idx].dropna(subset=[TARGET_COLUMN]).copy()
        if len(train) >= MIN_TRAIN_ROWS:
            valid_features = [feature for feature in features if not train[feature].isna().all()]
            if valid_features:
                model = _pipeline(model_name)
                model.fit(train[valid_features], train[TARGET_COLUMN])
                group.loc[idx : end_idx - 1, pred_col] = model.predict(group.loc[idx : end_idx - 1, valid_features])
        idx = end_idx
    return group[["asof_date", "market_scope", "forecast_horizon", TARGET_COLUMN, pred_col]]


def _promotion_decision(metrics: pd.DataFrame) -> dict:
    focus = metrics[(metrics["forecast_horizon"] == "20d") & (metrics["selected_model"] != "none")]
    passed = focus[
        (pd.to_numeric(focus["prediction_corr"], errors="coerce") >= 0.15)
        & (pd.to_numeric(focus["directional_hit_rate"], errors="coerce") >= 0.55)
    ]
    if len(passed) >= 2:
        return {"status": "promote_candidate", "reason": "two or more 20d scopes pass corr/hit thresholds"}
    return {"status": "research_only", "reason": "20d prediction accuracy threshold not met"}


def build_market_forecast_ai_model_v1_1(
    *,
    train_dataset_csv: Path,
    inference_latest_csv: Path,
    market_context_db: Path,
    output_dir: Path,
    report_dir: Path,
    model_dir: Path,
    model_mode: str = "fast",
) -> AiModelV11Result:
    generated_at = _now_kst()
    train_all, inference_latest, training_input_storage = _read_training_inputs(
        train_dataset_csv=train_dataset_csv,
        inference_latest_csv=inference_latest_csv,
        market_context_db=market_context_db,
    )
    train_all = train_all.dropna(subset=[TARGET_COLUMN]).copy()
    features = _numeric_features(train_all)
    model_names = _model_names_for_mode(model_mode)

    validation_frames: list[pd.DataFrame] = []
    metrics_rows: list[dict] = []
    prediction_rows: list[dict] = []
    model_dir.mkdir(parents=True, exist_ok=True)

    for (scope, horizon), group in train_all.groupby(["market_scope", "forecast_horizon"], sort=True):
        group_features = [feature for feature in features if feature in group.columns and not group[feature].isna().all()]
        if len(group) < MIN_TRAIN_ROWS or not group_features:
            continue

        candidate_frames = [_walk_forward_predict(group, group_features, model_name) for model_name in model_names]
        merged = candidate_frames[0]
        for frame in candidate_frames[1:]:
            merged = merged.merge(frame.drop(columns=[TARGET_COLUMN]), on=["asof_date", "market_scope", "forecast_horizon"], how="left")

        model_metrics = []
        for model_name in model_names:
            pred_col = f"{model_name}_predicted_forward_return"
            metric = {
                "market_scope": scope,
                "forecast_horizon": horizon,
                "model_name": model_name,
                **_metrics(merged, pred_col),
            }
            model_metrics.append(metric)
        ranked = sorted(
            model_metrics,
            key=lambda row: (
                row.get("prediction_corr") if row.get("prediction_corr") is not None else -999,
                row.get("directional_hit_rate") if row.get("directional_hit_rate") is not None else -999,
            ),
            reverse=True,
        )
        selected = ranked[0]["model_name"] if ranked else "none"
        selected_pred_col = f"{selected}_predicted_forward_return"
        merged["selected_model"] = selected
        merged["ai_v1_1_predicted_forward_return"] = merged[selected_pred_col]
        merged["ai_v1_1_prediction_error"] = merged["ai_v1_1_predicted_forward_return"] - merged[TARGET_COLUMN]
        merged["ai_v1_1_direction_hit_flag"] = (
            np.sign(merged["ai_v1_1_predicted_forward_return"]) == np.sign(merged[TARGET_COLUMN])
        ).astype("Int64")
        validation_frames.append(merged)
        metrics_rows.extend({**row, "selected_model": selected} for row in model_metrics)

        final_model = _pipeline(selected)
        final_model.fit(group[group_features], group[TARGET_COLUMN])
        train_std = float(group[TARGET_COLUMN].std(ddof=0)) or 1.0
        model_path = model_dir / f"{MODEL_VERSION}_{scope}_{horizon}_{selected}.joblib"
        joblib.dump(
            {
                "model": final_model,
                "features": group_features,
                "selected_model": selected,
                "target_column": TARGET_COLUMN,
                "market_scope": scope,
                "forecast_horizon": horizon,
                "model_version": MODEL_VERSION,
                "schema_version": SCHEMA_VERSION,
                "model_mode": model_mode,
                "generated_at": generated_at,
            },
            model_path,
        )

        infer = inference_latest[
            (inference_latest["market_scope"] == scope)
            & (inference_latest["forecast_horizon"] == horizon)
        ].copy()
        if not infer.empty:
            pred = final_model.predict(infer[group_features])
            for row, value in zip(infer.to_dict("records"), pred, strict=False):
                prediction_rows.append(
                    {
                        "asof_date": row["asof_date"],
                        "market_scope": scope,
                        "forecast_horizon": horizon,
                        "ai_v1_1_predicted_forward_return": round(float(value), 8),
                        "ai_v1_1_forecast_label": _label_from_prediction(float(value), train_std),
                        "selected_model": selected,
                        "training_rows": int(len(group)),
                        "feature_count": int(len(group_features)),
                        "model_path": str(model_path),
                        "model_version": MODEL_VERSION,
                        "schema_version": SCHEMA_VERSION,
                        "model_mode": model_mode,
                        "generated_at": generated_at,
                    }
                )

    validation = pd.concat(validation_frames, ignore_index=True, sort=False) if validation_frames else pd.DataFrame()
    metrics = pd.DataFrame(metrics_rows)
    selected_metrics = (
        metrics[metrics["model_name"] == metrics["selected_model"]].copy()
        if not metrics.empty
        else pd.DataFrame()
    )
    promotion = _promotion_decision(selected_metrics)
    predictions = pd.DataFrame(prediction_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    prediction_csv = output_dir / "market_forecast_ai_v1_1_predictions_current.csv"
    feature_set_json = output_dir / "market_forecast_ai_v1_1_feature_set_current.json"
    validation_csv = report_dir / "market_forecast_ai_v1_1_validation_latest.csv"
    metrics_csv = report_dir / "market_forecast_ai_v1_1_metrics_latest.csv"
    report_json = report_dir / "market_forecast_ai_v1_1_report_latest.json"
    report_md = report_dir / "market_forecast_ai_v1_1_report_latest.md"

    predictions.to_csv(prediction_csv, index=False, encoding="utf-8-sig")
    validation.to_csv(validation_csv, index=False, encoding="utf-8-sig")
    metrics.to_csv(metrics_csv, index=False, encoding="utf-8-sig")
    feature_set_json.write_text(
        json.dumps(
            {
                "model_version": MODEL_VERSION,
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "target_column": TARGET_COLUMN,
                "feature_columns": features,
                "curated_feature_count": len(CURATED_FEATURES),
                "max_features": MAX_FEATURES,
                "min_feature_available_rate": MIN_FEATURE_AVAILABLE_RATE,
                "model_mode": model_mode,
                "candidate_models": model_names,
                "training_input_storage": training_input_storage,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS market_forecast_ai_v1_1_predictions")
        con.execute("DROP TABLE IF EXISTS market_forecast_ai_v1_1_validation")
        predictions.to_sql("market_forecast_ai_v1_1_predictions", con, if_exists="replace", index=False)
        validation.to_sql("market_forecast_ai_v1_1_validation", con, if_exists="replace", index=False)
        con.commit()

    report = {
        "source_name": "QuantMarket market forecast AI model v1.1",
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "target_column": TARGET_COLUMN,
        "feature_count": len(features),
        "curated_feature_count": len(CURATED_FEATURES),
        "max_features": MAX_FEATURES,
        "min_feature_available_rate": MIN_FEATURE_AVAILABLE_RATE,
        "model_mode": model_mode,
        "candidate_models": model_names,
        "training_input_storage": training_input_storage,
        "prediction_rows": len(predictions),
        "promotion_decision": promotion,
        "selected_metrics": selected_metrics.to_dict("records"),
        "all_metrics": metrics.to_dict("records"),
        "paths": {
            "prediction_csv": str(prediction_csv),
            "feature_set_json": str(feature_set_json),
            "validation_csv": str(validation_csv),
            "metrics_csv": str(metrics_csv),
            "model_dir": str(model_dir),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# QuantMarket Market Forecast AI Model V1.1",
        "",
        f"- generated_at: {generated_at}",
        f"- model_version: {MODEL_VERSION}",
        f"- target_column: {TARGET_COLUMN}",
        f"- model_mode: {model_mode}",
        f"- training_input_storage: {training_input_storage}",
        f"- feature_count: {len(features)}",
        f"- prediction_rows: {len(predictions)}",
        f"- promotion_status: {promotion['status']}",
        f"- promotion_reason: {promotion['reason']}",
        "",
        "## Selected Validation Metrics",
        "",
        "| scope | horizon | model | rows | corr | hit | mae | rmse |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in selected_metrics.to_dict("records"):
        lines.append(
            f"| {row['market_scope']} | {row['forecast_horizon']} | {row['model_name']} | "
            f"{row.get('rows')} | {row.get('prediction_corr')} | {row.get('directional_hit_rate')} | "
            f"{row.get('mae')} | {row.get('rmse')} |"
        )
    lines.extend(["", "## Outputs", ""])
    for key, value in report["paths"].items():
        lines.append(f"- {key}: `{value}`")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["market_forecast_ai_v1_1_predictions"] = prediction_csv.name
    manifest.setdefault("tables", {})["market_forecast_ai_v1_1_predictions"] = {
        "file": prediction_csv.name,
        "row_count": int(len(predictions)),
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "promotion_status": promotion["status"],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return AiModelV11Result(
        prediction_csv=prediction_csv,
        report_json=report_json,
        report_md=report_md,
        feature_set_json=feature_set_json,
        model_dir=model_dir,
        generated_at=generated_at,
        row_count=int(len(predictions)),
    )
