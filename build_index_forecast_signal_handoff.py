from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", message="Skipping features without any observed values.*")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_market_dashboard_flow_model_research import (  # noqa: E402
    DATASET_PATH,
    MIN_TRAIN_COUNT,
    MODELS,
    _add_flow_enhanced_features,
    _apply_label_policy,
    _feature_columns,
    _model_pipeline,
    _usable_features,
)
from tune_market_dashboard_flow_backtest_rules import RULE_PROFILES  # noqa: E402

RESEARCH_DIR = ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current"
OUTPUT_DIR = ROOT / "service_platform" / "index_forecast_handoff" / "current"
DB_PATH = ROOT / "data" / "db" / "market_analysis.db"
BEST_PATH = RESEARCH_DIR / "dashboard_axis_flow_backtest_rule_tuning_best_current.csv"
THRESHOLDS_PATH = RESEARCH_DIR / "dashboard_axis_flow_threshold_tuning_thresholds_current.csv"
INVESTABLE_SCOPES = ["KOSPI", "KOSDAQ", "KOSPI200"]
LABELS = ["down", "sideways", "up"]
INDEX_CODES = {"KOSPI": "1001", "KOSDAQ": "2001", "KOSPI200": "1028"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _argmax_label(row: pd.Series) -> str:
    return max(LABELS, key=lambda label: float(row[f"prob_{label}"]))


def _threshold_label(row: pd.Series, down_threshold: float, up_threshold: float) -> str:
    if float(row["prob_down"]) >= down_threshold and float(row["prob_down"]) >= float(row["prob_up"]):
        return "down"
    if float(row["prob_up"]) >= up_threshold and float(row["prob_up"]) > float(row["prob_down"]):
        return "up"
    return "sideways"


def _predict_model(
    train: pd.DataFrame,
    live: pd.DataFrame,
    feature_cols: list[str],
    label_col: str,
    model_name: str,
) -> dict | None:
    usable = _usable_features(train, feature_cols)
    if train.shape[0] < MIN_TRAIN_COUNT or train[label_col].nunique() < 3 or not usable:
        return None
    model = _model_pipeline(model_name)
    model.fit(train[usable], train[label_col])
    probs = model.predict_proba(live[usable])
    class_index = {str(label): pos for pos, label in enumerate(model.classes_)}
    return {
        "model": model_name,
        "prob_down": float(probs[0][class_index.get("down", -1)]) if "down" in class_index else 0.0,
        "prob_sideways": float(probs[0][class_index.get("sideways", -1)]) if "sideways" in class_index else 0.0,
        "prob_up": float(probs[0][class_index.get("up", -1)]) if "up" in class_index else 0.0,
        "feature_count": int(len(usable)),
        "train_count": int(train.shape[0]),
        "train_start": train["asof_date"].min(),
        "train_end": train["asof_date"].max(),
    }


def _candidate_probability(
    labeled: pd.DataFrame,
    candidate: pd.Series,
    feature_cols: list[str],
    asof_date: str,
) -> tuple[dict | None, list[str]]:
    warnings: list[str] = []
    horizon = int(str(candidate["forecast_horizon"]).replace("d", ""))
    label_col = f"flow_label_{candidate['label_policy']}_{horizon}d"
    scoped = labeled[labeled["market_scope"] == candidate["market_scope"]].sort_values("asof_date").copy()
    train = scoped[scoped[label_col].notna() & scoped[feature_cols].notna().any(axis=1)].copy()
    live = scoped[(scoped["asof_date"] == asof_date) & scoped[feature_cols].notna().any(axis=1)].copy()
    if live.empty:
        return None, ["missing_live_feature_row"]

    model_name = str(candidate["model"])
    if model_name == "ensemble_mean_all":
        members = []
        for member_name in MODELS:
            member = _predict_model(train, live, feature_cols, label_col, member_name)
            if member is None:
                warnings.append(f"skipped_ensemble_member:{member_name}")
                continue
            members.append(member)
        if not members:
            return None, warnings + ["no_usable_ensemble_members"]
        probs = {
            "prob_down": sum(item["prob_down"] for item in members) / len(members),
            "prob_sideways": sum(item["prob_sideways"] for item in members) / len(members),
            "prob_up": sum(item["prob_up"] for item in members) / len(members),
        }
        meta = members[0]
        return {
            "model": model_name,
            **probs,
            "feature_count": meta["feature_count"],
            "train_count": min(int(item["train_count"]) for item in members),
            "train_start": min(item["train_start"] for item in members),
            "train_end": max(item["train_end"] for item in members),
            "ensemble_members": ",".join(item["model"] for item in members),
        }, warnings

    result = _predict_model(train, live, feature_cols, label_col, model_name)
    if result is None:
        return None, ["model_train_failed"]
    result["ensemble_members"] = ""
    return result, warnings


def _load_thresholds() -> pd.DataFrame:
    thresholds = pd.read_csv(THRESHOLDS_PATH)
    thresholds["test_year"] = pd.to_numeric(thresholds["test_year"], errors="coerce").astype("Int64")
    return thresholds


def _threshold_for_candidate(thresholds: pd.DataFrame, candidate: pd.Series, asof_date: str) -> tuple[float | None, float | None]:
    test_year = int(asof_date[:4])
    mask = (
        (thresholds["label_policy"] == candidate["label_policy"])
        & (thresholds["model"] == candidate["model"])
        & (thresholds["market_scope"] == candidate["market_scope"])
        & (thresholds["forecast_horizon"] == candidate["forecast_horizon"])
        & (thresholds["test_year"] <= test_year)
    )
    group = thresholds[mask].sort_values("test_year")
    if group.empty:
        return None, None
    row = group.iloc[-1]
    return float(row["down_threshold"]), float(row["up_threshold"])


def _quality_checks(signal: pd.DataFrame, asof_date: str, max_stale_days: int) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    today = datetime.now().date()
    asof = datetime.strptime(asof_date, "%Y-%m-%d").date()
    if (today - asof).days > max_stale_days:
        errors.append(f"stale_signal_asof:{asof_date}")

    expected = {(scope, f"{horizon}d") for scope in INVESTABLE_SCOPES for horizon in [5, 10, 20, 60]}
    actual = {(row.market_scope, row.forecast_horizon) for row in signal.itertuples()}
    missing = sorted(expected - actual)
    if missing:
        errors.append("missing_market_horizon:" + ",".join(f"{scope}:{horizon}" for scope, horizon in missing))
    if (signal["market_scope"] == "ALL").any():
        errors.append("non_investable_scope_included:ALL")

    if DB_PATH.exists():
        with sqlite3.connect(str(DB_PATH)) as con:
            sample_seed_rows = pd.read_sql_query(
                """
                SELECT COUNT(*) AS row_count
                FROM market_index_daily
                WHERE market = 'KR'
                  AND index_code IN ('1001', '2001', '1028')
                  AND date >= '2026-05-01'
                  AND source = 'sample_seed'
                """,
                con,
            )["row_count"].iloc[0]
            latest_daily = pd.read_sql_query(
                """
                SELECT index_code, MAX(date) AS latest_date
                FROM market_index_daily
                WHERE market = 'KR'
                  AND index_code IN ('1001', '2001', '1028')
                  AND source != 'sample_seed'
                GROUP BY index_code
                """,
                con,
            )
        if int(sample_seed_rows) > 0:
            errors.append(f"recent_sample_seed_rows:{int(sample_seed_rows)}")
        daily_map = dict(zip(latest_daily["index_code"], latest_daily["latest_date"]))
        for scope, code in INDEX_CODES.items():
            latest = daily_map.get(code)
            if not latest:
                warnings.append(f"missing_daily_source:{scope}")
            elif latest < asof_date:
                warnings.append(f"daily_source_older_than_signal:{scope}:{latest}")
    else:
        warnings.append("market_analysis_db_missing")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "asof_date": asof_date,
        "row_count": int(signal.shape[0]),
        "market_count": int(signal["market_scope"].nunique()) if not signal.empty else 0,
        "horizon_count": int(signal["forecast_horizon"].nunique()) if not signal.empty else 0,
    }


def build_handoff(min_asof_date: str, max_stale_days: int) -> dict:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"missing dataset: {DATASET_PATH}")
    best = pd.read_csv(BEST_PATH)
    best = best[best["market_scope"].isin(INVESTABLE_SCOPES)].copy()
    dataset = pd.read_csv(DATASET_PATH)
    dataset["asof_date"] = pd.to_datetime(dataset["asof_date"]).dt.strftime("%Y-%m-%d")
    dataset = dataset[dataset["asof_date"] >= min_asof_date].copy()
    dataset = _add_flow_enhanced_features(dataset)
    asof_date = dataset[dataset["market_scope"].isin(INVESTABLE_SCOPES)]["asof_date"].max()
    feature_cols = _feature_columns(dataset)
    thresholds = _load_thresholds()

    rows = []
    for _, candidate in best.sort_values(["market_scope", "forecast_horizon"]).iterrows():
        horizon = int(str(candidate["forecast_horizon"]).replace("d", ""))
        labeled = _apply_label_policy(
            dataset,
            str(candidate["label_policy"]),
            [str(candidate["market_scope"])],
            [horizon],
        )
        probs, warnings = _candidate_probability(labeled, candidate, feature_cols, asof_date)
        if probs is None:
            rows.append(
                {
                    "asof_date": asof_date,
                    "market_scope": candidate["market_scope"],
                    "forecast_horizon": candidate["forecast_horizon"],
                    "model_status": "failed",
                    "release_stage": "research_beta",
                    "production_ready": False,
                    "quality_warnings": ";".join(warnings),
                }
            )
            continue

        signal_row = {**probs}
        signal_row["confidence"] = max(float(signal_row["prob_down"]), float(signal_row["prob_sideways"]), float(signal_row["prob_up"]))
        if candidate["decision_method"] == "threshold":
            down_th, up_th = _threshold_for_candidate(thresholds, candidate, asof_date)
            if down_th is None or up_th is None:
                predicted = _argmax_label(pd.Series(signal_row))
                warnings.append("missing_threshold_used_argmax")
            else:
                predicted = _threshold_label(pd.Series(signal_row), down_th, up_th)
        else:
            down_th, up_th = None, None
            predicted = _argmax_label(pd.Series(signal_row))

        rule = RULE_PROFILES[str(candidate["rule_name"])]
        confidence_floor = float(candidate["confidence_floor"])
        low_confidence = signal_row["confidence"] < confidence_floor
        exposure = float(rule["fallback"] if low_confidence else rule[predicted])
        if low_confidence:
            warnings.append("low_confidence_fallback")

        rows.append(
            {
                "asof_date": asof_date,
                "market_scope": candidate["market_scope"],
                "forecast_horizon": candidate["forecast_horizon"],
                "label_policy": candidate["label_policy"],
                "model_name": candidate["model"],
                "ensemble_members": signal_row["ensemble_members"],
                "decision_method": candidate["decision_method"],
                "predicted_direction": predicted,
                "prob_down": signal_row["prob_down"],
                "prob_sideways": signal_row["prob_sideways"],
                "prob_up": signal_row["prob_up"],
                "confidence": signal_row["confidence"],
                "down_threshold": down_th,
                "up_threshold": up_th,
                "rule_name": candidate["rule_name"],
                "confidence_floor": confidence_floor,
                "recommended_exposure": exposure,
                "candidate_type": candidate["candidate_type"],
                "selection_sharpe": candidate["sharpe"],
                "selection_sharpe_lift": candidate.get("sharpe_lift"),
                "selection_mdd_improvement": candidate.get("mdd_improvement"),
                "selection_cumulative_return": candidate["cumulative_return"],
                "selection_buyhold_cumulative_return": candidate["buyhold_cumulative_return"],
                "train_start": signal_row["train_start"],
                "train_end": signal_row["train_end"],
                "train_count": signal_row["train_count"],
                "feature_count": signal_row["feature_count"],
                "model_status": "ok",
                "release_stage": "research_beta",
                "production_ready": True,
                "quality_warnings": ";".join(warnings),
                "source_generated_at": _now_iso(),
            }
        )

    signal = pd.DataFrame(rows)
    quality = _quality_checks(signal, asof_date, max_stale_days)
    if not quality["ok"]:
        signal["production_ready"] = False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    signal_path = OUTPUT_DIR / "index_forecast_signal_current.csv"
    signal_json_path = OUTPUT_DIR / "index_forecast_signal_current.json"
    manifest_path = OUTPUT_DIR / "index_forecast_handoff_manifest.json"
    quality_path = OUTPUT_DIR / "index_forecast_signal_quality_report.json"
    schema_path = OUTPUT_DIR / "index_forecast_signal_schema.json"

    signal.to_csv(signal_path, index=False, encoding="utf-8-sig")
    signal_json_path.write_text(signal.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    schema = {
        "version": 1,
        "primary_key": ["asof_date", "market_scope", "forecast_horizon"],
        "scope_policy": "investable_only",
        "markets": INVESTABLE_SCOPES,
        "horizons": ["5d", "10d", "20d", "60d"],
        "directions": LABELS,
        "exposure_range": [0.0, 1.0],
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "status": "ok" if quality["ok"] else "error",
        "release_stage": "research_beta",
        "production_ready": bool(quality["ok"] and signal["production_ready"].all()),
        "asof_date": asof_date,
        "latest_asof_date": asof_date,
        "generated_at": _now_iso(),
        "source": {
            "dataset": str(DATASET_PATH),
            "best_rules": str(BEST_PATH),
            "thresholds": str(THRESHOLDS_PATH),
            "min_asof_date": min_asof_date,
        },
        "quality": quality,
        "outputs": {
            "signal_csv": str(signal_path),
            "signal_json": str(signal_json_path),
            "quality_report": str(quality_path),
            "schema": str(schema_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build beta index forecast signal handoff from flow model research.")
    parser.add_argument("--min-asof-date", default="2020-01-02")
    parser.add_argument("--max-stale-days", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(build_handoff(args.min_asof_date, args.max_stale_days), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
