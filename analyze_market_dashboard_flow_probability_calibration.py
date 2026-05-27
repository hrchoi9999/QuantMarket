from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest_market_dashboard_flow_signals import _load_next_day_returns, _run_backtest, DB_PATH  # noqa: E402
from run_market_dashboard_flow_model_research import (  # noqa: E402
    DATASET_PATH,
    MIN_TEST_YEAR,
    MIN_TRAIN_COUNT,
    OUTPUT_DIR,
    REPORT_DIR,
    _add_flow_enhanced_features,
    _apply_label_policy,
    _feature_columns,
    _usable_features,
)
from tune_market_dashboard_flow_thresholds import _grid_search_thresholds, _threshold_label  # noqa: E402

SCOPES = ["KOSPI", "KOSPI200"]
HORIZON = 5
LABEL_POLICY = "vol_adjusted_wide_q2020"
LABEL_COL = f"flow_label_{LABEL_POLICY}_{HORIZON}d"
LABEL_PROBS = ["prob_down", "prob_sideways", "prob_up"]
RULES = {
    "KOSPI": {
        "decision_method": "argmax",
        "rule_name": "moderate_80_40_0",
        "confidence_floor": 0.45,
        "profile": {"up": 0.8, "sideways": 0.4, "down": 0.0, "fallback": 0.4},
    },
    "KOSPI200": {
        "decision_method": "threshold",
        "rule_name": "defensive_100_30_0",
        "confidence_floor": 0.50,
        "profile": {"up": 1.0, "sideways": 0.3, "down": 0.0, "fallback": 0.3},
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _model(model_name: str):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.pipeline import make_pipeline

    base = make_pipeline(
        SimpleImputer(strategy="median"),
        ExtraTreesClassifier(
            n_estimators=400,
            max_depth=6,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
    )
    if model_name == "extra_trees_raw":
        return base
    if model_name == "extra_trees_calibrated_sigmoid":
        return CalibratedClassifierCV(estimator=base, method="sigmoid", cv=TimeSeriesSplit(n_splits=3))
    raise ValueError(f"unsupported model: {model_name}")


def _argmax_label(frame: pd.DataFrame) -> pd.Series:
    return frame[LABEL_PROBS].idxmax(axis=1).str.replace("prob_", "", regex=False)


def _metrics(actual: pd.Series, pred: pd.Series) -> dict[str, float]:
    labels = ["down", "sideways", "up"]
    actual_values = actual.astype(str).to_numpy()
    pred_values = pred.astype(str).to_numpy()
    recalls = []
    f1_scores = []
    for label in labels:
        actual_mask = actual_values == label
        pred_mask = pred_values == label
        tp = float((actual_mask & pred_mask).sum())
        fp = float((~actual_mask & pred_mask).sum())
        fn = float((actual_mask & ~pred_mask).sum())
        support = float(actual_mask.sum())
        if support > 0:
            recalls.append(tp / support)
        denom = (2.0 * tp) + fp + fn
        f1_scores.append((2.0 * tp / denom) if denom > 0 else 0.0)
    return {
        "accuracy": float((actual_values == pred_values).mean()) if actual_values.size else 0.0,
        "balanced_accuracy": float(sum(recalls) / len(recalls)) if recalls else 0.0,
        "macro_f1": float(sum(f1_scores) / len(f1_scores)) if f1_scores else 0.0,
    }


def _class_index(classes: np.ndarray) -> dict[str, int]:
    return {str(label): pos for pos, label in enumerate(classes)}


def _build_predictions(model_names: list[str]) -> pd.DataFrame:
    dataset = pd.read_csv(DATASET_PATH)
    dataset["asof_date"] = pd.to_datetime(dataset["asof_date"]).dt.strftime("%Y-%m-%d")
    dataset = dataset[dataset["asof_date"] >= "2020-01-01"].copy()
    dataset = _add_flow_enhanced_features(dataset)
    dataset = _apply_label_policy(dataset, LABEL_POLICY, SCOPES, [HORIZON])
    feature_cols = _feature_columns(dataset)
    dataset["year"] = pd.to_datetime(dataset["asof_date"]).dt.year

    rows = []
    for scope in SCOPES:
        scoped = dataset[dataset["market_scope"] == scope].sort_values("asof_date")
        years = [int(year) for year in sorted(scoped["year"].dropna().unique()) if int(year) >= MIN_TEST_YEAR]
        for test_year in years:
            train = scoped[(scoped["year"] < test_year) & scoped[LABEL_COL].notna()].copy()
            test = scoped[(scoped["year"] == test_year) & scoped[LABEL_COL].notna()].copy()
            train = train[train[feature_cols].notna().any(axis=1)]
            test = test[test[feature_cols].notna().any(axis=1)]
            if train.shape[0] < MIN_TRAIN_COUNT or test.shape[0] < 30 or train[LABEL_COL].nunique() < 3:
                continue
            usable = _usable_features(train, feature_cols)
            if not usable:
                continue
            for model_name in model_names:
                model = _model(model_name)
                model.fit(train[usable], train[LABEL_COL])
                probs = model.predict_proba(test[usable])
                class_index = _class_index(model.classes_)
                for pos, (_, test_row) in enumerate(test.iterrows()):
                    prob_map = {
                        label: float(probs[pos][class_index[label]]) if label in class_index else 0.0
                        for label in ["down", "sideways", "up"]
                    }
                    rows.append(
                        {
                            "model": model_name,
                            "label_policy": LABEL_POLICY,
                            "market_scope": scope,
                            "forecast_horizon": f"{HORIZON}d",
                            "test_year": int(test_year),
                            "asof_date": test_row["asof_date"],
                            "actual_label": test_row[LABEL_COL],
                            "prob_down": prob_map["down"],
                            "prob_sideways": prob_map["sideways"],
                            "prob_up": prob_map["up"],
                        }
                    )
    predictions = pd.DataFrame(rows)
    predictions["argmax_label"] = _argmax_label(predictions)
    predictions["confidence"] = predictions[LABEL_PROBS].max(axis=1)
    top2 = np.sort(predictions[LABEL_PROBS].to_numpy(dtype=float), axis=1)[:, -2:]
    predictions["top2_margin"] = top2[:, 1] - top2[:, 0]
    return predictions


def _add_decisions(predictions: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for (scope, model_name), group in predictions.groupby(["market_scope", "model"], dropna=False):
        group = group.sort_values(["test_year", "asof_date"]).copy()
        rule = RULES[scope]
        if rule["decision_method"] == "argmax":
            group["predicted_direction"] = group["argmax_label"]
            group["down_threshold"] = np.nan
            group["up_threshold"] = np.nan
        else:
            labels = []
            down_thresholds = []
            up_thresholds = []
            for _, row in group.iterrows():
                train = group[group["test_year"] < int(row["test_year"])]
                if train.empty:
                    labels.append(row["argmax_label"])
                    down_thresholds.append(np.nan)
                    up_thresholds.append(np.nan)
                    continue
                tuned = _grid_search_thresholds(train)
                labels.append(_threshold_label(pd.DataFrame([row]), tuned["down_threshold"], tuned["up_threshold"]).iloc[0])
                down_thresholds.append(float(tuned["down_threshold"]))
                up_thresholds.append(float(tuned["up_threshold"]))
            group["predicted_direction"] = labels
            group["down_threshold"] = down_thresholds
            group["up_threshold"] = up_thresholds
        low_confidence = group["confidence"] < float(rule["confidence_floor"])
        group["candidate_type"] = "calibration_test"
        group["decision_method"] = rule["decision_method"]
        group["rule_name"] = rule["rule_name"]
        group["confidence_floor"] = float(rule["confidence_floor"])
        group["low_confidence_ratio"] = low_confidence.astype(float)
        base_exposure = group["predicted_direction"].map(rule["profile"]).astype(float)
        group["exposure"] = base_exposure
        group.loc[low_confidence, "exposure"] = float(rule["profile"]["fallback"])
        frames.append(group)
    return pd.concat(frames, ignore_index=True)


def _score_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, group in predictions.groupby(["market_scope", "model"], dropna=False):
        scope, model = key
        argmax_metrics = _metrics(group["actual_label"], group["argmax_label"])
        decision_metrics = _metrics(group["actual_label"], group["predicted_direction"])
        rows.append(
            {
                "market_scope": scope,
                "forecast_horizon": f"{HORIZON}d",
                "model": model,
                "decision_method": RULES[scope]["decision_method"],
                "accuracy": decision_metrics["accuracy"],
                "balanced_accuracy": decision_metrics["balanced_accuracy"],
                "macro_f1": decision_metrics["macro_f1"],
                "argmax_balanced_accuracy": argmax_metrics["balanced_accuracy"],
                "avg_confidence": float(group["confidence"].mean()),
                "median_confidence": float(group["confidence"].median()),
                "avg_top2_margin": float(group["top2_margin"].mean()),
                "low_confidence_ratio": float(group["low_confidence_ratio"].mean()),
            }
        )
    return pd.DataFrame(rows)


def run_analysis(cost_bps: float) -> dict:
    predictions = _build_predictions(["extra_trees_raw", "extra_trees_calibrated_sigmoid"])
    decisions = _add_decisions(predictions)
    pred_scorecard = _score_predictions(decisions)
    returns = _load_next_day_returns(DB_PATH, SCOPES)
    trades, backtest_scorecard = _run_backtest(decisions, returns, cost_bps)

    pred_path = OUTPUT_DIR / "dashboard_axis_flow_probability_calibration_5d_predictions_current.csv"
    pred_score_path = OUTPUT_DIR / "dashboard_axis_flow_probability_calibration_5d_scorecard_current.csv"
    backtest_path = OUTPUT_DIR / "dashboard_axis_flow_probability_calibration_5d_backtest_current.csv"
    trades_path = OUTPUT_DIR / "dashboard_axis_flow_probability_calibration_5d_trades_current.csv"
    summary_path = REPORT_DIR / "dashboard_axis_flow_probability_calibration_5d_summary_latest.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(pred_path, index=False, encoding="utf-8-sig")
    pred_scorecard.to_csv(pred_score_path, index=False, encoding="utf-8-sig")
    backtest_scorecard.to_csv(backtest_path, index=False, encoding="utf-8-sig")
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")

    summary = {
        "status": "ok",
        "generated_at": _now_iso(),
        "scopes": SCOPES,
        "forecast_horizon": f"{HORIZON}d",
        "label_policy": LABEL_POLICY,
        "cost_bps": cost_bps,
        "row_counts": {
            "predictions": int(decisions.shape[0]),
            "prediction_scorecard": int(pred_scorecard.shape[0]),
            "backtest_scorecard": int(backtest_scorecard.shape[0]),
            "trades": int(trades.shape[0]),
        },
        "outputs": {
            "predictions": str(pred_path),
            "prediction_scorecard": str(pred_score_path),
            "backtest_scorecard": str(backtest_path),
            "trades": str(trades_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze 5d probability calibration for KOSPI/KOSPI200 flow signals.")
    parser.add_argument("--cost-bps", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(run_analysis(cost_bps=args.cost_bps), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
