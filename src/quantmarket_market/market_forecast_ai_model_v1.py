from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

KST = timezone(timedelta(hours=9))
MODEL_VERSION = "qm_market_forecast_ai_v1_20260513"
SCHEMA_VERSION = "market_forecast_ai_model_v1"
TARGET_COLUMN = "target_forward_return"
MIN_ROWS = 600


@dataclass(frozen=True)
class AiModelV1Result:
    prediction_csv: Path
    report_json: Path
    report_md: Path
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


def _read_feature_columns(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["feature_columns"])


def _label_from_prediction(pred: float | None, train_std: float | None) -> str | None:
    if pred is None or pd.isna(pred) or train_std is None or train_std <= 0:
        return None
    z = pred / train_std
    if z >= 0.75:
        return "bullish"
    if z >= 0.2:
        return "mild_bullish"
    if z > -0.2:
        return "neutral"
    if z > -0.75:
        return "mild_bearish"
    return "bearish"


def _build_pipeline(x: pd.DataFrame) -> Pipeline:
    categorical_cols = [col for col in x.columns if x[col].dtype == "object" or str(x[col].dtype).startswith("string")]
    numeric_cols = [col for col in x.columns if col not in categorical_cols]
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False, max_categories=24)),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric_cols),
            ("cat", categorical_pipe, categorical_cols),
        ],
        sparse_threshold=0.0,
    )
    model = HistGradientBoostingRegressor(
        max_iter=220,
        learning_rate=0.035,
        max_leaf_nodes=15,
        l2_regularization=0.08,
        random_state=42,
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def _split_train_test(group: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    group = group.sort_values("asof_date").reset_index(drop=True)
    split_idx = max(int(len(group) * 0.8), MIN_ROWS)
    split_idx = min(split_idx, len(group) - 1)
    return group.iloc[:split_idx].copy(), group.iloc[split_idx:].copy()


def _metrics(test: pd.DataFrame, pred: np.ndarray) -> dict:
    y = pd.to_numeric(test[TARGET_COLUMN], errors="coerce").to_numpy(dtype=float)
    corr = pd.Series(pred).corr(pd.Series(y))
    return {
        "rows": int(len(test)),
        "start_date": str(test["asof_date"].min()),
        "end_date": str(test["asof_date"].max()),
        "prediction_corr": None if pd.isna(corr) else round(float(corr), 6),
        "directional_hit_rate": round(float((np.sign(pred) == np.sign(y)).mean()), 6),
        "mae": round(float(mean_absolute_error(y, pred)), 8),
        "rmse": round(float(np.sqrt(mean_squared_error(y, pred))), 8),
        "mean_predicted_return": round(float(np.mean(pred)), 8),
        "mean_realized_return": round(float(np.mean(y)), 8),
    }


def _promotion_decision(metrics: pd.DataFrame) -> dict:
    if metrics.empty:
        return {"status": "reject", "reason": "no validation metrics"}
    focus = metrics[
        (metrics["forecast_horizon"] == "20d")
        & (metrics["market_scope"].isin(["ALL", "KOSPI", "KOSDAQ"]))
    ]
    pass_rows = focus[
        (pd.to_numeric(focus["prediction_corr"], errors="coerce") >= 0.10)
        & (pd.to_numeric(focus["directional_hit_rate"], errors="coerce") >= 0.53)
    ]
    if len(pass_rows) >= 2:
        return {"status": "promote_candidate", "reason": "at least two 20d scopes pass corr/hit thresholds"}
    return {
        "status": "research_only",
        "reason": "20d validation did not pass minimum corr >= 0.10 and hit >= 0.53 on at least two scopes",
    }


def build_market_forecast_ai_model_v1(
    *,
    train_dataset_csv: Path,
    inference_latest_csv: Path,
    feature_columns_json: Path,
    market_context_db: Path,
    output_dir: Path,
    report_dir: Path,
    model_dir: Path,
) -> AiModelV1Result:
    generated_at = _now_kst()
    feature_columns = _read_feature_columns(feature_columns_json)
    train_all = pd.read_csv(train_dataset_csv)
    inference_latest = pd.read_csv(inference_latest_csv)
    train_all = train_all.dropna(subset=[TARGET_COLUMN]).copy()

    prediction_rows: list[dict] = []
    validation_rows: list[dict] = []
    metrics_rows: list[dict] = []
    model_dir.mkdir(parents=True, exist_ok=True)

    for (scope, horizon), group in train_all.groupby(["market_scope", "forecast_horizon"], sort=True):
        if len(group) < MIN_ROWS:
            continue
        train, test = _split_train_test(group)
        group_features = [
            col
            for col in feature_columns
            if col in train.columns and not train[col].isna().all()
        ]
        x_train = train[group_features].copy()
        y_train = pd.to_numeric(train[TARGET_COLUMN], errors="coerce")
        x_test = test[group_features].copy()
        pipeline = _build_pipeline(x_train)
        pipeline.fit(x_train, y_train)
        pred_test = pipeline.predict(x_test)
        train_std = float(y_train.std(ddof=0)) or 1.0
        metric = {
            "market_scope": scope,
            "forecast_horizon": horizon,
            **_metrics(test, pred_test),
            "train_rows": int(len(train)),
            "train_start_date": str(train["asof_date"].min()),
            "train_end_date": str(train["asof_date"].max()),
        }
        metrics_rows.append(metric)

        test_out = test[["asof_date", "market_scope", "forecast_horizon", TARGET_COLUMN]].copy()
        test_out["ai_v1_predicted_forward_return"] = pred_test
        test_out["ai_v1_prediction_error"] = test_out["ai_v1_predicted_forward_return"] - test_out[TARGET_COLUMN]
        test_out["ai_v1_direction_hit_flag"] = (
            np.sign(test_out["ai_v1_predicted_forward_return"]) == np.sign(test_out[TARGET_COLUMN])
        ).astype(int)
        validation_rows.extend(test_out.to_dict("records"))

        pipeline.fit(group[group_features], pd.to_numeric(group[TARGET_COLUMN], errors="coerce"))
        model_path = model_dir / f"{MODEL_VERSION}_{scope}_{horizon}.joblib"
        joblib.dump(
            {
                "model": pipeline,
                "feature_columns": group_features,
                "target_column": TARGET_COLUMN,
                "market_scope": scope,
                "forecast_horizon": horizon,
                "train_rows": int(len(group)),
                "feature_count": int(len(group_features)),
                "train_std": train_std,
                "model_version": MODEL_VERSION,
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
            },
            model_path,
        )

        infer = inference_latest[
            (inference_latest["market_scope"] == scope)
            & (inference_latest["forecast_horizon"] == horizon)
        ].copy()
        if infer.empty:
            continue
        pred = pipeline.predict(infer[group_features])
        for row, value in zip(infer.to_dict("records"), pred, strict=False):
            prediction_rows.append(
                {
                    "asof_date": row["asof_date"],
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "ai_v1_predicted_forward_return": round(float(value), 8),
                    "ai_v1_forecast_label": _label_from_prediction(float(value), train_std),
                    "ai_v1_training_rows": int(len(group)),
                    "ai_v1_model_path": str(model_path),
                    "model_version": MODEL_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": generated_at,
                }
            )

    predictions = pd.DataFrame(prediction_rows)
    validation = pd.DataFrame(validation_rows)
    metrics = pd.DataFrame(metrics_rows)
    promotion = _promotion_decision(metrics)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    prediction_csv = output_dir / "market_forecast_ai_v1_predictions_current.csv"
    validation_csv = report_dir / "market_forecast_ai_v1_validation_latest.csv"
    metrics_csv = report_dir / "market_forecast_ai_v1_metrics_latest.csv"
    report_json = report_dir / "market_forecast_ai_v1_report_latest.json"
    report_md = report_dir / "market_forecast_ai_v1_report_latest.md"
    predictions.to_csv(prediction_csv, index=False, encoding="utf-8-sig")
    validation.to_csv(validation_csv, index=False, encoding="utf-8-sig")
    metrics.to_csv(metrics_csv, index=False, encoding="utf-8-sig")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS market_forecast_ai_v1_predictions")
        con.execute("DROP TABLE IF EXISTS market_forecast_ai_v1_validation")
        predictions.to_sql("market_forecast_ai_v1_predictions", con, if_exists="replace", index=False)
        validation.to_sql("market_forecast_ai_v1_validation", con, if_exists="replace", index=False)
        con.commit()

    report = {
        "source_name": "QuantMarket market forecast AI model v1",
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "target_column": TARGET_COLUMN,
        "feature_count": int(len(feature_columns)),
        "prediction_rows": int(len(predictions)),
        "validation_rows": int(len(validation)),
        "metrics": metrics.to_dict("records"),
        "promotion_decision": promotion,
        "paths": {
            "prediction_csv": str(prediction_csv),
            "validation_csv": str(validation_csv),
            "metrics_csv": str(metrics_csv),
            "model_dir": str(model_dir),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
        "notes": [
            "AI v1 uses per market_scope + forecast_horizon models.",
            "Validation split is chronological 80/20 within each group.",
            "Predictions are model research outputs for Quant model integration, not public investment advice.",
            "Do not promote this model to production unless promotion_decision.status is promote_candidate.",
        ],
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# QuantMarket Market Forecast AI Model V1",
        "",
        f"- generated_at: {generated_at}",
        f"- model_version: {MODEL_VERSION}",
        f"- target_column: {TARGET_COLUMN}",
        f"- feature_count: {len(feature_columns)}",
        f"- prediction_rows: {len(predictions)}",
        f"- promotion_status: {promotion['status']}",
        f"- promotion_reason: {promotion['reason']}",
        "",
        "## Validation Metrics",
        "",
        "| scope | horizon | rows | corr | hit | mae | rmse |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in metrics.to_dict("records"):
        lines.append(
            f"| {row['market_scope']} | {row['forecast_horizon']} | {row['rows']} | "
            f"{row['prediction_corr']} | {row['directional_hit_rate']} | {row['mae']} | {row['rmse']} |"
        )
    lines.extend(["", "## Outputs", ""])
    for key, value in report["paths"].items():
        lines.append(f"- {key}: `{value}`")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("canonical_files", {})["market_forecast_ai_v1_predictions"] = prediction_csv.name
    manifest.setdefault("tables", {})["market_forecast_ai_v1_predictions"] = {
        "file": prediction_csv.name,
        "row_count": int(len(predictions)),
        "model_version": MODEL_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return AiModelV1Result(
        prediction_csv=prediction_csv,
        report_json=report_json,
        report_md=report_md,
        model_dir=model_dir,
        generated_at=generated_at,
        row_count=int(len(predictions)),
    )
