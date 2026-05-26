from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.market_dashboard_signal_research import HORIZONS, SCOPES  # noqa: E402

OUTPUT_DIR = ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current"
REPORT_DIR = ROOT / "reports" / "market_dashboard_signal_research" / "flow_model"
PREDICTIONS_PATH = OUTPUT_DIR / "dashboard_axis_flow_model_predictions_current.csv"
SCORECARD_PATH = OUTPUT_DIR / "dashboard_axis_flow_model_scorecard_current.csv"
LABEL_ORDER = ["down", "sideways", "up"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _argmax_label(frame: pd.DataFrame) -> pd.Series:
    probs = frame[["prob_down", "prob_sideways", "prob_up"]]
    return probs.idxmax(axis=1).str.replace("prob_", "", regex=False)


def _threshold_label(frame: pd.DataFrame, down_threshold: float, up_threshold: float) -> pd.Series:
    down = frame["prob_down"]
    up = frame["prob_up"]
    labels = pd.Series("sideways", index=frame.index, dtype="object")
    down_mask = (down >= down_threshold) & (down >= up)
    up_mask = (up >= up_threshold) & (up > down)
    labels.loc[down_mask] = "down"
    labels.loc[up_mask] = "up"
    return labels


def _metrics(actual: pd.Series, pred: pd.Series) -> dict[str, float]:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

    baseline = actual.mode().iloc[0]
    return {
        "accuracy": float(accuracy_score(actual, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, pred)),
        "macro_f1": float(f1_score(actual, pred, average="macro")),
        "baseline_accuracy": float(accuracy_score(actual, [baseline] * actual.shape[0])),
    }


def _build_ensemble_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    key_cols = ["label_policy", "market_scope", "forecast_horizon", "test_year"]
    for key, group in predictions.groupby(key_cols, dropna=False):
        label_policy, scope, horizon, test_year = key
        actual = group[["asof_date", "actual_label"]].drop_duplicates().sort_values("asof_date")
        model_groups = {
            model: g.set_index("asof_date")[["prob_down", "prob_sideways", "prob_up"]].sort_index()
            for model, g in group.groupby("model")
        }
        if len(model_groups) < 2:
            continue
        models = sorted(model_groups)
        selected = [model_groups[model].loc[actual["asof_date"]].to_numpy() for model in models]
        combined = sum(selected) / len(selected)
        for pos, (_, row) in enumerate(actual.iterrows()):
            rows.append(
                {
                    "model": "ensemble_mean_all",
                    "label_policy": label_policy,
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "test_year": int(test_year),
                    "asof_date": row["asof_date"],
                    "actual_label": row["actual_label"],
                    "prob_down": float(combined[pos][0]),
                    "prob_sideways": float(combined[pos][1]),
                    "prob_up": float(combined[pos][2]),
                }
            )
    return pd.DataFrame(rows)


def _grid_search_thresholds(train: pd.DataFrame) -> dict[str, float]:
    best: dict[str, float] | None = None
    for down_threshold in [x / 100 for x in range(34, 61, 2)]:
        for up_threshold in [x / 100 for x in range(34, 61, 2)]:
            pred = _threshold_label(train, down_threshold, up_threshold)
            met = _metrics(train["actual_label"], pred)
            row = {
                "down_threshold": down_threshold,
                "up_threshold": up_threshold,
                **met,
            }
            if best is None:
                best = row
                continue
            if (row["balanced_accuracy"], row["macro_f1"], row["accuracy"]) > (
                best["balanced_accuracy"],
                best["macro_f1"],
                best["accuracy"],
            ):
                best = row
    if best is None:
        return {
            "down_threshold": 0.34,
            "up_threshold": 0.34,
            "accuracy": 0.0,
            "balanced_accuracy": 0.0,
            "macro_f1": 0.0,
            "baseline_accuracy": 0.0,
        }
    return best


def run_tuning() -> dict:
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(f"missing predictions: {PREDICTIONS_PATH}")
    predictions = pd.read_csv(PREDICTIONS_PATH)
    predictions = predictions[
        predictions["label_policy"].isin(["q2020", "vol_adjusted_q2020", "vol_adjusted_wide_q2020", "existing"])
    ].copy()
    ensemble = _build_ensemble_predictions(predictions)
    all_predictions = pd.concat([predictions, ensemble], ignore_index=True)
    all_predictions["argmax_label"] = _argmax_label(all_predictions)

    tune_rows = []
    eval_rows = []
    threshold_rows = []
    key_cols = ["label_policy", "model", "market_scope", "forecast_horizon"]
    for key, group in all_predictions.groupby(key_cols, dropna=False):
        label_policy, model, scope, horizon = key
        group = group.sort_values(["test_year", "asof_date"]).copy()
        years = [int(year) for year in sorted(group["test_year"].dropna().unique())]
        for test_year in years:
            train = group[group["test_year"] < test_year]
            test = group[group["test_year"] == test_year]
            if train.empty or test.empty:
                continue
            tuned = _grid_search_thresholds(train)
            threshold_rows.append(
                {
                    "label_policy": label_policy,
                    "model": model,
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "test_year": test_year,
                    **tuned,
                }
            )
            tuned_pred = _threshold_label(test, tuned["down_threshold"], tuned["up_threshold"])
            argmax_pred = test["argmax_label"]
            tuned_metrics = _metrics(test["actual_label"], tuned_pred)
            argmax_metrics = _metrics(test["actual_label"], argmax_pred)
            eval_rows.append(
                {
                    "label_policy": label_policy,
                    "model": model,
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "test_year": test_year,
                    "down_threshold": tuned["down_threshold"],
                    "up_threshold": tuned["up_threshold"],
                    "accuracy": tuned_metrics["accuracy"],
                    "balanced_accuracy": tuned_metrics["balanced_accuracy"],
                    "macro_f1": tuned_metrics["macro_f1"],
                    "baseline_accuracy": tuned_metrics["baseline_accuracy"],
                    "argmax_accuracy": argmax_metrics["accuracy"],
                    "argmax_balanced_accuracy": argmax_metrics["balanced_accuracy"],
                    "argmax_macro_f1": argmax_metrics["macro_f1"],
                    "argmax_baseline_accuracy": argmax_metrics["baseline_accuracy"],
                    "rows": int(test.shape[0]),
                }
            )

    eval_frame = pd.DataFrame(eval_rows)
    thresholds = pd.DataFrame(threshold_rows)
    scorecard = (
        eval_frame.groupby(["label_policy", "model", "market_scope", "forecast_horizon"], as_index=False)
        .agg(
            walk_forward_years=("test_year", "count"),
            tuned_balanced_accuracy_avg=("balanced_accuracy", "mean"),
            tuned_macro_f1_avg=("macro_f1", "mean"),
            tuned_accuracy_avg=("accuracy", "mean"),
            baseline_accuracy_avg=("baseline_accuracy", "mean"),
            argmax_balanced_accuracy_avg=("argmax_balanced_accuracy", "mean"),
            argmax_macro_f1_avg=("argmax_macro_f1", "mean"),
            argmax_accuracy_avg=("argmax_accuracy", "mean"),
            avg_down_threshold=("down_threshold", "mean"),
            avg_up_threshold=("up_threshold", "mean"),
        )
    )
    scorecard["balanced_accuracy_lift_vs_argmax"] = (
        scorecard["tuned_balanced_accuracy_avg"] - scorecard["argmax_balanced_accuracy_avg"]
    )
    scorecard["macro_f1_lift_vs_argmax"] = scorecard["tuned_macro_f1_avg"] - scorecard["argmax_macro_f1_avg"]
    scorecard = scorecard.sort_values(
        ["forecast_horizon", "market_scope", "tuned_balanced_accuracy_avg", "tuned_macro_f1_avg"],
        ascending=[True, True, False, False],
    )

    eval_path = OUTPUT_DIR / "dashboard_axis_flow_threshold_tuning_walk_forward_current.csv"
    threshold_path = OUTPUT_DIR / "dashboard_axis_flow_threshold_tuning_thresholds_current.csv"
    scorecard_path = OUTPUT_DIR / "dashboard_axis_flow_threshold_tuning_scorecard_current.csv"
    eval_frame.to_csv(eval_path, index=False, encoding="utf-8-sig")
    thresholds.to_csv(threshold_path, index=False, encoding="utf-8-sig")
    scorecard.to_csv(scorecard_path, index=False, encoding="utf-8-sig")
    summary = {
        "status": "ok",
        "generated_at": _now_iso(),
        "source_predictions": str(PREDICTIONS_PATH),
        "row_counts": {
            "input_predictions": int(predictions.shape[0]),
            "ensemble_predictions": int(ensemble.shape[0]),
            "walk_forward": int(eval_frame.shape[0]),
            "thresholds": int(thresholds.shape[0]),
            "scorecard": int(scorecard.shape[0]),
        },
        "outputs": {
            "walk_forward": str(eval_path),
            "thresholds": str(threshold_path),
            "scorecard": str(scorecard_path),
        },
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "dashboard_axis_flow_threshold_tuning_summary_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description="Tune market/scope-specific flow model probability thresholds.").parse_args()


def main() -> None:
    parse_args()
    print(json.dumps(run_tuning(), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
