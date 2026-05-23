from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .market_forecast_validation import _build_scope_close, _forward_returns, _read_forecast

KST = timezone(timedelta(hours=9))

CALIBRATION_MODEL_VERSION = "qm_market_forecast_ai_calibration_ridge_v0.4_fast_refit_20260514"
CALIBRATION_SCHEMA_VERSION = "market_forecast_ai_calibration.v4"
MIN_TRAIN_ROWS = 252
MODEL_REFIT_INTERVAL = 20
RIDGE_ALPHA = 1.0

FEATURE_COLUMNS = [
    "market_forecast_score",
    "expected_volatility_score",
    "drawdown_risk_score",
    "upside_participation_score",
    "confidence_score",
    "baseline_market_state_score",
    "baseline_trend_score",
    "baseline_breadth_score",
    "baseline_risk_on_score",
    "baseline_risk_off_score",
    "baseline_global_risk_on_score",
    "baseline_external_asset_risk_on_score",
    "baseline_external_macro_pressure_score",
    "baseline_smart_money_score",
    "global_risk_on_score",
    "external_macro_pressure_score",
    "external_asset_risk_on_score",
    "korea_proxy_momentum_score",
    "domestic_flow_derivatives_score",
    "smart_money_score_5d",
    "smart_money_score_20d",
    "futures_direction_score",
    "program_pressure_score",
    "derivatives_pressure_score",
    "macro_event_pressure_score",
    "macro_event_count",
    "macro_shock_event_count",
    "macro_event_risk_window_flag",
    "days_since_scheduled_macro_event",
    "days_to_next_scheduled_macro_event",
    "macro_event_density_5d",
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
]


@dataclass(frozen=True)
class CalibrationResult:
    report_json: Path
    report_md: Path
    calibrated_csv: Path
    validation_csv: Path
    generated_at: str
    row_count: int


def _now_kst() -> str:
    return datetime.now(tz=KST).replace(microsecond=0).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _read_optional_table(con: sqlite3.Connection, table_name: str) -> pd.DataFrame:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not exists:
        return pd.DataFrame()
    return pd.read_sql_query(f"SELECT * FROM {table_name}", con)


def _select_existing(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [col for col in columns if col in frame.columns]
    return frame[existing].copy() if existing else pd.DataFrame()


def _merge_context_features(market_context_db: Path, forecast: pd.DataFrame) -> pd.DataFrame:
    out = forecast.copy()
    with _connect(market_context_db) as con:
        global_context = _read_optional_table(con, "global_context_daily")
        external_context = _read_optional_table(con, "external_market_context_daily")
        domestic_flow = _read_optional_table(con, "domestic_flow_derivatives_daily")
        macro_event = _read_optional_table(con, "macro_event_calendar_daily")
        macro_surprise = _read_optional_table(con, "macro_surprise_context_daily")

    global_cols = [
        "asof_date",
        "global_risk_on_score",
        "external_macro_pressure_score",
    ]
    if not global_context.empty:
        out = out.merge(_select_existing(global_context, global_cols), on="asof_date", how="left")

    external_cols = [
        "asof_date",
        "external_asset_risk_on_score",
        "korea_proxy_momentum_score",
    ]
    if not external_context.empty:
        out = out.merge(_select_existing(external_context, external_cols), on="asof_date", how="left")

    domestic_cols = [
        "asof_date",
        "market_scope",
        "domestic_flow_derivatives_score",
        "smart_money_score_5d",
        "smart_money_score_20d",
        "futures_direction_score",
        "program_pressure_score",
        "derivatives_pressure_score",
    ]
    if not domestic_flow.empty:
        out = out.merge(_select_existing(domestic_flow, domestic_cols), on=["asof_date", "market_scope"], how="left")

    macro_cols = [
        "asof_date",
        "macro_event_pressure_score",
        "macro_event_count",
        "macro_shock_event_count",
        "macro_event_risk_window_flag",
        "days_since_scheduled_macro_event",
        "days_to_next_scheduled_macro_event",
        "macro_event_density_5d",
    ]
    if not macro_event.empty:
        out = out.merge(_select_existing(macro_event, macro_cols), on="asof_date", how="left")

    surprise_cols = [
        "asof_date",
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
    ]
    if not macro_surprise.empty:
        out = out.merge(_select_existing(macro_surprise, surprise_cols), on="asof_date", how="left")

    for col in FEATURE_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out


def _safe_clip(value: float | None, low: float = -3.0, high: float = 3.0) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(max(low, min(high, value)))


def _label_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.75:
        return "bullish"
    if score >= 0.2:
        return "mild_bullish"
    if score > -0.2:
        return "neutral"
    if score > -0.75:
        return "mild_bearish"
    return "bearish"


def _fit_ridge(x_train: np.ndarray, y_train: np.ndarray) -> np.ndarray:
    x_design = np.column_stack([np.ones(len(x_train)), x_train])
    penalty = np.eye(x_design.shape[1]) * RIDGE_ALPHA
    penalty[0, 0] = 0.0
    return np.linalg.pinv(x_design.T @ x_design + penalty) @ x_design.T @ y_train


def _prepare_matrix(frame: pd.DataFrame, medians: pd.Series | None = None, means: pd.Series | None = None, stds: pd.Series | None = None):
    x = frame[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if medians is None:
        medians = x.median(numeric_only=True).fillna(0.0)
    x = x.fillna(medians)
    if means is None:
        means = x.mean()
    if stds is None:
        stds = x.std(ddof=0).replace(0.0, 1.0).fillna(1.0)
    x_scaled = (x - means) / stds
    return x_scaled.to_numpy(dtype=float), medians, means, stds


def _calibrate_group(group: pd.DataFrame, generated_at: str) -> tuple[list[dict], list[dict]]:
    group = group.sort_values("asof_date").reset_index(drop=True)
    train_indices: list[int] = []
    predictions: list[dict] = []
    validation_rows: list[dict] = []
    cached_beta: np.ndarray | None = None
    cached_medians: pd.Series | None = None
    cached_means: pd.Series | None = None
    cached_stds: pd.Series | None = None
    cached_target_mean: float | None = None
    cached_target_std: float | None = None
    cached_coefficient_norm: float | None = None
    last_fit_count = 0

    for idx, row in group.iterrows():
        prediction = None
        score = None
        confidence = 0.0
        train_count = len(train_indices)
        coefficient_norm = None

        if train_count >= MIN_TRAIN_ROWS:
            if cached_beta is None or train_count - last_fit_count >= MODEL_REFIT_INTERVAL:
                train = group.loc[train_indices].copy()
                x_train, cached_medians, cached_means, cached_stds = _prepare_matrix(train)
                y_train = pd.to_numeric(train["forward_return"], errors="coerce").to_numpy(dtype=float)
                cached_target_mean = float(np.mean(y_train))
                cached_target_std = float(np.std(y_train)) or 1.0
                cached_beta = _fit_ridge(x_train, y_train)
                cached_coefficient_norm = float(np.linalg.norm(cached_beta[1:]))
                last_fit_count = train_count
            x_one, _, _, _ = _prepare_matrix(group.loc[[idx]], medians=cached_medians, means=cached_means, stds=cached_stds)
            prediction = float(np.array([1.0, *x_one[0]]) @ cached_beta)
            score = _safe_clip((prediction - cached_target_mean) / cached_target_std)
            coefficient_norm = cached_coefficient_norm
            completeness = 1.0 - float(row[FEATURE_COLUMNS].isna().mean())
            sample_factor = min(1.0, math.sqrt(train_count / 1000.0))
            signal_factor = min(1.0, abs(score or 0.0) / 1.5)
            confidence = round(max(0.0, min(1.0, 0.45 * sample_factor + 0.35 * completeness + 0.20 * signal_factor)), 4)

        out = {
            "asof_date": row["asof_date"],
            "market_scope": row["market_scope"],
            "forecast_horizon": row["forecast_horizon"],
            "predicted_forward_return": round(prediction, 8) if prediction is not None else None,
            "calibrated_forecast_score": round(score, 6) if score is not None else None,
            "calibrated_forecast_label": _label_from_score(score),
            "calibration_confidence_score": confidence,
            "training_sample_count": train_count,
            "baseline_market_forecast_score": row.get("market_forecast_score"),
            "baseline_market_forecast_label": row.get("market_forecast_label"),
            "calibration_model_version": CALIBRATION_MODEL_VERSION,
            "calibration_schema_version": CALIBRATION_SCHEMA_VERSION,
            "generated_at": generated_at,
        }
        predictions.append(out)

        realized = row.get("forward_return")
        if prediction is not None and realized is not None and not pd.isna(realized):
            validation_rows.append(
                {
                    **out,
                    "realized_forward_return": round(float(realized), 8),
                    "prediction_error": round(float(realized) - float(prediction), 8),
                    "coefficient_norm": round(coefficient_norm, 8) if coefficient_norm is not None else None,
                }
            )

        if realized is not None and not pd.isna(realized):
            train_indices.append(idx)

    return predictions, validation_rows


def _overall_validation(validation: pd.DataFrame) -> list[dict]:
    if validation.empty:
        return []
    rows = []
    for (scope, horizon), g in validation.groupby(["market_scope", "forecast_horizon"]):
        sample = g.dropna(subset=["predicted_forward_return", "realized_forward_return"])
        if sample.empty:
            continue
        corr = sample["predicted_forward_return"].corr(sample["realized_forward_return"])
        score_corr = sample["calibrated_forecast_score"].corr(sample["realized_forward_return"])
        rows.append(
            {
                "market_scope": scope,
                "forecast_horizon": horizon,
                "rows": int(len(sample)),
                "start_date": str(sample["asof_date"].min()),
                "end_date": str(sample["asof_date"].max()),
                "mean_predicted_forward_return": round(float(sample["predicted_forward_return"].mean()), 8),
                "mean_realized_forward_return": round(float(sample["realized_forward_return"].mean()), 8),
                "mae": round(float(sample["prediction_error"].abs().mean()), 8),
                "rmse": round(float(np.sqrt((sample["prediction_error"] ** 2).mean())), 8),
                "directional_win_rate": round(float((np.sign(sample["predicted_forward_return"]) == np.sign(sample["realized_forward_return"])).mean()), 6),
                "prediction_corr": round(float(corr), 6) if corr is not None and not pd.isna(corr) else None,
                "score_corr": round(float(score_corr), 6) if score_corr is not None and not pd.isna(score_corr) else None,
            }
        )
    return sorted(rows, key=lambda row: (row["market_scope"], row["forecast_horizon"]))


def _label_summary(validation: pd.DataFrame) -> pd.DataFrame:
    if validation.empty:
        return pd.DataFrame()
    out = (
        validation.groupby(["market_scope", "forecast_horizon", "calibrated_forecast_label"], dropna=False)
        .agg(
            rows=("realized_forward_return", "size"),
            avg_score=("calibrated_forecast_score", "mean"),
            mean_realized_forward_return=("realized_forward_return", "mean"),
            win_rate=("realized_forward_return", lambda s: (s > 0).mean()),
        )
        .reset_index()
    )
    for col in ["avg_score", "mean_realized_forward_return", "win_rate"]:
        out[col] = out[col].round(8)
    return out


def _update_manifest_and_schema(output_dir: Path, row_count: int, start_date: str | None, end_date: str | None) -> None:
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {}
    manifest.setdefault("canonical_files", {})["market_forecast_ai_calibrated_daily"] = "market_forecast_ai_calibrated_daily_current.csv"
    manifest.setdefault("tables", {})["market_forecast_ai_calibrated_daily"] = {
        "file": "market_forecast_ai_calibrated_daily_current.csv",
        "row_count": row_count,
        "start_date": start_date,
        "end_date": end_date,
        "duplicate_key_count": None,
        "missing_date_count": None,
    }
    manifest.setdefault("label_sets", {})["calibrated_forecast_label"] = [
        "bullish",
        "mild_bullish",
        "neutral",
        "mild_bearish",
        "bearish",
    ]
    manifest.setdefault("warnings", []).append(
        "market_forecast_ai_calibrated_daily is walk-forward ridge calibration and should be treated as model feature, not public advice."
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    schema_path = output_dir / "schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        schema = {"tables": {}}
    schema.setdefault("tables", {})["market_forecast_ai_calibrated_daily"] = {
        "primary_key": ["asof_date", "market_scope", "forecast_horizon"],
        "join_keys": ["asof_date", "market_scope", "forecast_horizon"],
        "model_policy": "Walk-forward ridge calibration of market_forecast_daily using realized forward ETF proxy returns. Historical predictions use only prior realized samples.",
        "columns": [
            {"column_name": "asof_date", "data_type": "date string YYYY-MM-DD", "nullable": False, "score_direction": "identifier"},
            {"column_name": "market_scope", "data_type": "string", "nullable": False, "score_direction": "identifier"},
            {"column_name": "forecast_horizon", "data_type": "string", "nullable": False, "score_direction": "identifier"},
            {"column_name": "predicted_forward_return", "data_type": "float ratio", "nullable": True, "score_direction": "higher is more constructive"},
            {"column_name": "calibrated_forecast_score", "data_type": "float", "nullable": True, "score_direction": "higher is more constructive"},
            {"column_name": "calibrated_forecast_label", "data_type": "string", "nullable": True, "score_direction": "ordered bearish to bullish"},
            {"column_name": "calibration_confidence_score", "data_type": "float 0 to 1", "nullable": False, "score_direction": "higher means stronger model confidence"},
            {"column_name": "training_sample_count", "data_type": "integer", "nullable": False, "score_direction": "higher means more calibration history"},
            {"column_name": "baseline_market_forecast_score", "data_type": "float", "nullable": True, "score_direction": "higher is more constructive baseline"},
            {"column_name": "baseline_market_forecast_label", "data_type": "string", "nullable": True, "score_direction": "baseline label"},
            {"column_name": "calibration_model_version", "data_type": "string", "nullable": False, "score_direction": "metadata"},
            {"column_name": "calibration_schema_version", "data_type": "string", "nullable": False, "score_direction": "metadata"},
            {"column_name": "generated_at", "data_type": "datetime string ISO8601 +09:00", "nullable": False, "score_direction": "metadata"},
        ],
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_report_md(report: dict, label_summary: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Market Forecast AI Calibration",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- calibration_model_version: {report['calibration_model_version']}",
        f"- output_csv: `{report['output_paths']['calibrated_csv']}`",
        f"- validation_csv: `{report['output_paths']['validation_csv']}`",
        "",
        "## Overall Walk-Forward Validation",
        "",
        "| scope | horizon | rows | pred corr | score corr | directional win | MAE | RMSE |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["overall_validation"]:
        lines.append(
            "| {market_scope} | {forecast_horizon} | {rows} | {prediction_corr} | {score_corr} | "
            "{directional_win_rate} | {mae} | {rmse} |".format(**row)
        )
    lines.extend(["", "## Label Summary", ""])
    if label_summary.empty:
        lines.append("- No label summary available.")
    else:
        lines.extend(["| scope | horizon | label | rows | avg score | mean realized | win rate |", "|---|---|---|---:|---:|---:|---:|"])
        for row in label_summary.to_dict("records"):
            lines.append(
                f"| {row['market_scope']} | {row['forecast_horizon']} | {row['calibrated_forecast_label']} | "
                f"{row['rows']} | {row['avg_score']} | {row['mean_realized_forward_return']} | {row['win_rate']} |"
            )
    lines.extend(["", "## Notes", ""])
    for note in report["notes"]:
        lines.append(f"- {note}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_market_forecast_ai_calibration(
    *,
    market_context_db: Path,
    price_db: Path,
    output_dir: Path,
    report_dir: Path,
) -> CalibrationResult:
    generated_at = _now_kst()
    forecast = _merge_context_features(market_context_db, _read_forecast(market_context_db))
    scope_close = _build_scope_close(price_db)
    forward_returns = _forward_returns(scope_close)
    trainable = forecast.merge(forward_returns, on=["asof_date", "market_scope", "forecast_horizon"], how="left")
    if "forward_return" not in trainable.columns and "target_forward_return" in trainable.columns:
        trainable["forward_return"] = trainable["target_forward_return"]

    prediction_rows: list[dict] = []
    validation_rows: list[dict] = []
    for _, group in trainable.groupby(["market_scope", "forecast_horizon"]):
        preds, vals = _calibrate_group(group, generated_at)
        prediction_rows.extend(preds)
        validation_rows.extend(vals)

    predictions = pd.DataFrame(prediction_rows).sort_values(["asof_date", "market_scope", "forecast_horizon"])
    validation = pd.DataFrame(validation_rows).sort_values(["asof_date", "market_scope", "forecast_horizon"]) if validation_rows else pd.DataFrame()
    label_summary = _label_summary(validation)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    calibrated_csv = output_dir / "market_forecast_ai_calibrated_daily_current.csv"
    calibrated_csv_full = output_dir / "market_forecast_ai_calibrated_daily.csv"
    validation_csv = report_dir / "market_forecast_ai_calibration_validation_latest.csv"
    label_csv = report_dir / "market_forecast_ai_calibration_label_summary_latest.csv"
    report_json = report_dir / "market_forecast_ai_calibration_latest.json"
    report_md = report_dir / "market_forecast_ai_calibration_latest.md"

    predictions.to_csv(calibrated_csv, index=False, encoding="utf-8-sig")
    predictions.to_csv(calibrated_csv_full, index=False, encoding="utf-8-sig")
    validation.to_csv(validation_csv, index=False, encoding="utf-8-sig")
    label_summary.to_csv(label_csv, index=False, encoding="utf-8-sig")

    with _connect(market_context_db) as con:
        con.execute("DROP TABLE IF EXISTS market_forecast_ai_calibrated_daily")
        predictions.to_sql("market_forecast_ai_calibrated_daily", con, if_exists="replace", index=False)
        con.commit()

    start_date = str(predictions["asof_date"].min()) if not predictions.empty else None
    end_date = str(predictions["asof_date"].max()) if not predictions.empty else None
    _update_manifest_and_schema(output_dir, int(len(predictions)), start_date, end_date)

    report = {
        "source_name": "QuantMarket market forecast AI calibration",
        "generated_at": generated_at,
        "timezone": "Asia/Seoul",
        "calibration_model_version": CALIBRATION_MODEL_VERSION,
        "calibration_schema_version": CALIBRATION_SCHEMA_VERSION,
        "min_train_rows": MIN_TRAIN_ROWS,
        "model_refit_interval": MODEL_REFIT_INTERVAL,
        "ridge_alpha": RIDGE_ALPHA,
        "feature_columns": FEATURE_COLUMNS,
        "source_paths": {
            "market_context_db": str(market_context_db),
            "price_db_readonly": str(price_db),
        },
        "output_paths": {
            "calibrated_csv": str(calibrated_csv),
            "validation_csv": str(validation_csv),
            "label_summary_csv": str(label_csv),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
        "row_counts": {
            "forecast_rows": int(len(forecast)),
            "calibrated_rows": int(len(predictions)),
            "walk_forward_validation_rows": int(len(validation)),
            "label_summary_rows": int(len(label_summary)),
        },
        "overall_validation": _overall_validation(validation),
        "label_summary": label_summary.to_dict("records"),
        "notes": [
            "Historical calibrated predictions are walk-forward: each prediction uses only prior rows with realized forward returns.",
            "Latest rows without realized forward returns still receive production predictions using all available prior training samples.",
            "This is a model feature for Quant research, not a public market prediction or investment advice.",
        ],
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report_md(report, label_summary, report_md)
    return CalibrationResult(
        report_json=report_json,
        report_md=report_md,
        calibrated_csv=calibrated_csv,
        validation_csv=validation_csv,
        generated_at=generated_at,
        row_count=int(len(predictions)),
    )
