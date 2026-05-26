from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from run_market_dashboard_flow_model_research import (  # noqa: E402
    DATASET_PATH,
    HORIZONS,
    MIN_TEST_YEAR,
    MIN_TRAIN_COUNT,
    OUTPUT_DIR,
    REPORT_DIR,
    SCOPES,
    _add_flow_enhanced_features,
    _apply_label_policy,
    _feature_columns,
    _model_pipeline,
    _usable_features,
)

LABEL_POLICY = "vol_adjusted_q2020"
MODEL_NAMES = ["logistic", "logistic_calibrated"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _prob_for_label(row: pd.Series, label: str) -> float:
    return float(row.get(f"prob_{label}", 0.0))


def _fit_logistic_analysis(dataset: pd.DataFrame, *, scopes: list[str], horizons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score

    feature_cols = _feature_columns(dataset)
    frame = dataset.copy()
    frame["year"] = pd.to_datetime(frame["asof_date"]).dt.year
    importance_rows: list[dict] = []
    prediction_rows: list[dict] = []
    metric_rows: list[dict] = []
    confusion_rows: list[dict] = []

    for scope in scopes:
        scoped = frame[frame["market_scope"] == scope].sort_values("asof_date")
        years = [int(year) for year in sorted(scoped["year"].dropna().unique()) if int(year) >= MIN_TEST_YEAR]
        for horizon in horizons:
            label_col = f"flow_label_{LABEL_POLICY}_{horizon}d"
            for test_year in years:
                train = scoped[(scoped["year"] < test_year) & scoped[label_col].notna()].copy()
                test = scoped[(scoped["year"] == test_year) & scoped[label_col].notna()].copy()
                train = train[train[feature_cols].notna().any(axis=1)]
                test = test[test[feature_cols].notna().any(axis=1)]
                if train.shape[0] < MIN_TRAIN_COUNT or test.shape[0] < 30 or train[label_col].nunique() < 3:
                    continue
                usable = _usable_features(train, feature_cols)
                if not usable:
                    continue
                for model_name in MODEL_NAMES:
                    model = _model_pipeline(model_name)
                    model.fit(train[usable], train[label_col])
                    pred = model.predict(test[usable])
                    probs = model.predict_proba(test[usable])
                    baseline = test[label_col].mode().iloc[0]
                    metric_rows.append(
                        {
                            "model": model_name,
                            "label_policy": LABEL_POLICY,
                            "market_scope": scope,
                            "forecast_horizon": f"{horizon}d",
                            "test_year": test_year,
                            "train_start": train["asof_date"].min(),
                            "train_end": train["asof_date"].max(),
                            "test_start": test["asof_date"].min(),
                            "test_end": test["asof_date"].max(),
                            "train_count": int(train.shape[0]),
                            "test_count": int(test.shape[0]),
                            "feature_count": int(len(usable)),
                            "accuracy": float(accuracy_score(test[label_col], pred)),
                            "balanced_accuracy": float(balanced_accuracy_score(test[label_col], pred)),
                            "macro_f1": float(f1_score(test[label_col], pred, average="macro")),
                            "baseline_accuracy": float(accuracy_score(test[label_col], [baseline] * test.shape[0])),
                        }
                    )
                    if model_name == "logistic":
                        labels = [str(label) for label in model.classes_]
                        classifier = model.named_steps["logisticregression"]
                        coef = classifier.coef_
                        for class_idx, label in enumerate(labels):
                            for feature, value in zip(usable, coef[class_idx]):
                                importance_rows.append(
                                    {
                                        "model": model_name,
                                        "market_scope": scope,
                                        "forecast_horizon": f"{horizon}d",
                                        "test_year": test_year,
                                        "class_label": label,
                                        "feature": feature,
                                        "coefficient": float(value),
                                        "abs_coefficient": abs(float(value)),
                                    }
                                )
                    matrix = confusion_matrix(test[label_col], pred, labels=["down", "sideways", "up"])
                    for actual_idx, actual in enumerate(["down", "sideways", "up"]):
                        for pred_idx, predicted in enumerate(["down", "sideways", "up"]):
                            confusion_rows.append(
                                {
                                    "model": model_name,
                                    "market_scope": scope,
                                    "forecast_horizon": f"{horizon}d",
                                    "test_year": test_year,
                                    "actual_label": actual,
                                    "predicted_label": predicted,
                                    "count": int(matrix[actual_idx, pred_idx]),
                                }
                            )
                    class_index = {str(label): i for i, label in enumerate(model.classes_)}
                    for pos, (_, test_row) in enumerate(test.iterrows()):
                        prob = {
                            "down": float(probs[pos][class_index.get("down", -1)]) if "down" in class_index else 0.0,
                            "sideways": float(probs[pos][class_index.get("sideways", -1)]) if "sideways" in class_index else 0.0,
                            "up": float(probs[pos][class_index.get("up", -1)]) if "up" in class_index else 0.0,
                        }
                        predicted = str(pred[pos])
                        actual = str(test_row[label_col])
                        prediction_rows.append(
                            {
                                "model": model_name,
                                "market_scope": scope,
                                "forecast_horizon": f"{horizon}d",
                                "test_year": test_year,
                                "asof_date": test_row["asof_date"],
                                "actual_label": actual,
                                "predicted_label": predicted,
                                "is_correct": int(actual == predicted),
                                "prob_down": prob["down"],
                                "prob_sideways": prob["sideways"],
                                "prob_up": prob["up"],
                                "predicted_probability": prob[predicted],
                                "actual_probability": prob[actual],
                                "confidence_gap": prob[predicted] - prob[actual],
                                "forward_return": test_row.get(f"forward_return_{horizon}d"),
                            }
                        )
    return (
        pd.DataFrame(metric_rows),
        pd.DataFrame(importance_rows),
        pd.DataFrame(confusion_rows),
        pd.DataFrame(prediction_rows),
    )


def _summarize_importance(importance: pd.DataFrame) -> pd.DataFrame:
    if importance.empty:
        return pd.DataFrame()
    return (
        importance.groupby(["model", "market_scope", "forecast_horizon", "class_label", "feature"], as_index=False)
        .agg(
            mean_coefficient=("coefficient", "mean"),
            mean_abs_coefficient=("abs_coefficient", "mean"),
            positive_years=("coefficient", lambda s: int((s > 0).sum())),
            negative_years=("coefficient", lambda s: int((s < 0).sum())),
            years=("test_year", "nunique"),
        )
        .sort_values(
            ["forecast_horizon", "market_scope", "class_label", "mean_abs_coefficient"],
            ascending=[True, True, True, False],
        )
    )


def _summarize_errors(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if predictions.empty:
        return pd.DataFrame(), pd.DataFrame()
    summary = (
        predictions.groupby(["model", "market_scope", "forecast_horizon", "test_year"], as_index=False)
        .agg(
            rows=("is_correct", "count"),
            accuracy=("is_correct", "mean"),
            avg_confidence_gap=("confidence_gap", lambda s: float(s.mean())),
            wrong_high_confidence=("is_correct", lambda s: int((s == 0).sum())),
        )
        .sort_values(["accuracy", "rows"], ascending=[True, False])
    )
    wrong = predictions[predictions["is_correct"] == 0].copy()
    worst = wrong.sort_values("confidence_gap", ascending=False).head(200)
    return summary, worst


def run_analysis(min_asof_date: str) -> dict:
    dataset = pd.read_csv(DATASET_PATH)
    dataset["asof_date"] = pd.to_datetime(dataset["asof_date"]).dt.strftime("%Y-%m-%d")
    dataset = dataset[dataset["asof_date"] >= min_asof_date].copy()
    dataset = _add_flow_enhanced_features(dataset)
    dataset = _apply_label_policy(dataset, LABEL_POLICY, SCOPES, HORIZONS)
    metrics, importance, confusion, predictions = _fit_logistic_analysis(dataset, scopes=SCOPES, horizons=HORIZONS)
    importance_summary = _summarize_importance(importance)
    error_summary, worst_errors = _summarize_errors(predictions)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "metrics": OUTPUT_DIR / "dashboard_axis_flow_logistic_metrics_current.csv",
        "feature_importance": OUTPUT_DIR / "dashboard_axis_flow_logistic_feature_importance_current.csv",
        "feature_importance_summary": OUTPUT_DIR / "dashboard_axis_flow_logistic_feature_importance_summary_current.csv",
        "confusion": OUTPUT_DIR / "dashboard_axis_flow_logistic_confusion_current.csv",
        "predictions": OUTPUT_DIR / "dashboard_axis_flow_logistic_predictions_current.csv",
        "error_summary": OUTPUT_DIR / "dashboard_axis_flow_logistic_error_summary_current.csv",
        "worst_errors": OUTPUT_DIR / "dashboard_axis_flow_logistic_worst_errors_current.csv",
    }
    metrics.to_csv(paths["metrics"], index=False, encoding="utf-8-sig")
    importance.to_csv(paths["feature_importance"], index=False, encoding="utf-8-sig")
    importance_summary.to_csv(paths["feature_importance_summary"], index=False, encoding="utf-8-sig")
    confusion.to_csv(paths["confusion"], index=False, encoding="utf-8-sig")
    predictions.to_csv(paths["predictions"], index=False, encoding="utf-8-sig")
    error_summary.to_csv(paths["error_summary"], index=False, encoding="utf-8-sig")
    worst_errors.to_csv(paths["worst_errors"], index=False, encoding="utf-8-sig")
    summary = {
        "status": "ok",
        "generated_at": _now_iso(),
        "models": MODEL_NAMES,
        "label_policy": LABEL_POLICY,
        "min_test_year": MIN_TEST_YEAR,
        "min_train_count": MIN_TRAIN_COUNT,
        "min_asof_date": min_asof_date,
        "dataset_rows": int(dataset.shape[0]),
        "row_counts": {
            "metrics": int(metrics.shape[0]),
            "feature_importance": int(importance.shape[0]),
            "feature_importance_summary": int(importance_summary.shape[0]),
            "confusion": int(confusion.shape[0]),
            "predictions": int(predictions.shape[0]),
            "error_summary": int(error_summary.shape[0]),
            "worst_errors": int(worst_errors.shape[0]),
        },
        "outputs": {key: str(path) for key, path in paths.items()},
    }
    (REPORT_DIR / "dashboard_axis_flow_logistic_analysis_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze 2020+ vol-adjusted flow-only Logistic model.")
    parser.add_argument("--min-asof-date", default="2020-01-02")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(run_analysis(args.min_asof_date), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
