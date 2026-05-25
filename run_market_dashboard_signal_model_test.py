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

from quantmarket_market.market_dashboard_signal_research import HORIZONS, SCOPES

DATASET_PATH = ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current" / "dashboard_axis_model_dataset_current.csv"
OUTPUT_DIR = ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current"
REPORT_DIR = ROOT / "reports" / "market_dashboard_signal_research" / "model_tests"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _feature_columns(dataset: pd.DataFrame) -> list[str]:
    cols = []
    for col in dataset.columns:
        if col in {"asof_date", "market_scope"}:
            continue
        if col.startswith("forward_return_") or col.startswith("direction_label_"):
            continue
        if pd.api.types.is_numeric_dtype(dataset[col]):
            cols.append(col)
    return cols


def _usable_features(frame: pd.DataFrame, feature_cols: list[str], *, min_observed: int = 30) -> list[str]:
    usable = []
    for col in feature_cols:
        values = frame[col].dropna()
        if values.shape[0] >= min_observed and values.nunique() > 1:
            usable.append(col)
    return usable


def _model_pipeline(model_name: str):
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if model_name == "logistic":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced"),
        )
    if model_name == "hist_gradient_boosting":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            HistGradientBoostingClassifier(
                max_iter=80,
                learning_rate=0.06,
                max_leaf_nodes=15,
                l2_regularization=0.1,
                early_stopping=True,
                random_state=42,
            ),
        )
    if model_name == "extra_trees":
        return make_pipeline(
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
    if model_name == "random_forest":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(
                n_estimators=400,
                max_depth=6,
                min_samples_leaf=20,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
        )
    raise ValueError(f"unsupported model: {model_name}")


def _evaluate_holdout(
    dataset: pd.DataFrame,
    model_name: str,
    *,
    scopes: list[str],
    horizons: list[int],
) -> tuple[pd.DataFrame, dict]:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

    feature_cols = _feature_columns(dataset)
    latest = dataset.sort_values("asof_date").tail(1)
    rows = []
    latest_predictions = {}
    for scope in scopes:
        scoped = dataset[dataset["market_scope"] == scope].sort_values("asof_date")
        for horizon in horizons:
            label_col = f"direction_label_3class_{horizon}d"
            trainable = scoped.dropna(subset=[label_col]).copy()
            trainable = trainable[trainable[feature_cols].notna().any(axis=1)]
            if trainable.shape[0] < 200 or trainable[label_col].nunique() < 3:
                continue
            split = max(int(trainable.shape[0] * 0.8), trainable.shape[0] - 500)
            split = min(split, trainable.shape[0] - 50)
            train = trainable.iloc[:split]
            test = trainable.iloc[split:]
            usable = _usable_features(train, feature_cols)
            if not usable:
                continue
            model = _model_pipeline(model_name)
            model.fit(train[usable], train[label_col])
            pred = model.predict(test[usable])
            baseline = test[label_col].mode().iloc[0]
            rows.append(
                {
                    "model": model_name,
                    "validation": "holdout",
                    "market_scope": scope,
                    "forecast_horizon": f"{horizon}d",
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
            probs = model.predict_proba(latest[usable])[0]
            latest_predictions[f"{scope}_{horizon}d"] = {
                "market_scope": scope,
                "forecast_horizon": f"{horizon}d",
                "asof_date": latest["asof_date"].iloc[0],
                "predicted_label": str(model.predict(latest[usable])[0]),
                "class_probabilities": {
                    str(label): round(float(prob), 6) for label, prob in zip(model.classes_, probs)
                },
            }
    return pd.DataFrame(rows), latest_predictions


def _evaluate_walk_forward(
    dataset: pd.DataFrame,
    model_name: str,
    *,
    scopes: list[str],
    horizons: list[int],
) -> pd.DataFrame:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

    feature_cols = _feature_columns(dataset)
    frame = dataset.copy()
    frame["year"] = pd.to_datetime(frame["asof_date"]).dt.year
    rows = []
    for scope in scopes:
        scoped = frame[frame["market_scope"] == scope].sort_values("asof_date")
        years = [int(year) for year in sorted(scoped["year"].dropna().unique()) if int(year) >= 2020]
        for horizon in horizons:
            label_col = f"direction_label_3class_{horizon}d"
            for test_year in years:
                train = scoped[(scoped["year"] < test_year) & scoped[label_col].notna()].copy()
                test = scoped[(scoped["year"] == test_year) & scoped[label_col].notna()].copy()
                train = train[train[feature_cols].notna().any(axis=1)]
                test = test[test[feature_cols].notna().any(axis=1)]
                if train.shape[0] < 500 or test.shape[0] < 30 or train[label_col].nunique() < 3:
                    continue
                usable = _usable_features(train, feature_cols)
                if not usable:
                    continue
                model = _model_pipeline(model_name)
                model.fit(train[usable], train[label_col])
                pred = model.predict(test[usable])
                baseline = test[label_col].mode().iloc[0]
                rows.append(
                    {
                        "model": model_name,
                        "validation": "walk_forward",
                        "market_scope": scope,
                        "forecast_horizon": f"{horizon}d",
                        "test_year": int(test_year),
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
    return pd.DataFrame(rows)


def _suffix(model_name: str, scopes: list[str], horizons: list[int]) -> str:
    scope_part = "allscopes" if scopes == SCOPES else "-".join(scopes).lower()
    horizon_part = "allhorizons" if horizons == HORIZONS else "-".join(f"{h}d" for h in horizons)
    return f"{model_name}_{scope_part}_{horizon_part}"


def run_model_test(model_name: str, validation: str, scopes: list[str], horizons: list[int]) -> dict:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"dataset is missing: {DATASET_PATH}")
    dataset = pd.read_csv(DATASET_PATH)
    holdout, latest_predictions = _evaluate_holdout(dataset, model_name, scopes=scopes, horizons=horizons)
    walk_forward = (
        _evaluate_walk_forward(dataset, model_name, scopes=scopes, horizons=horizons)
        if validation in {"walk_forward", "both"}
        else pd.DataFrame()
    )
    scorecard = (
        walk_forward.groupby(["model", "market_scope", "forecast_horizon"], as_index=False)
        .agg(
            walk_forward_years=("test_year", "count"),
            walk_forward_balanced_accuracy_avg=("balanced_accuracy", "mean"),
            walk_forward_macro_f1_avg=("macro_f1", "mean"),
            walk_forward_baseline_accuracy_avg=("baseline_accuracy", "mean"),
        )
        if not walk_forward.empty
        else pd.DataFrame()
    )
    if not holdout.empty and not scorecard.empty:
        scorecard = holdout.merge(
            scorecard,
            on=["model", "market_scope", "forecast_horizon"],
            how="left",
            suffixes=("_holdout", ""),
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _suffix(model_name, scopes, horizons)
    holdout.to_csv(OUTPUT_DIR / f"dashboard_axis_model_test_{suffix}_holdout_current.csv", index=False, encoding="utf-8-sig")
    walk_forward.to_csv(OUTPUT_DIR / f"dashboard_axis_model_test_{suffix}_walk_forward_current.csv", index=False, encoding="utf-8-sig")
    scorecard.to_csv(OUTPUT_DIR / f"dashboard_axis_model_test_{suffix}_scorecard_current.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "ok",
        "generated_at": _now_iso(),
        "model": model_name,
        "validation": validation,
        "scopes": scopes,
        "horizons": [f"{h}d" for h in horizons],
        "dataset": str(DATASET_PATH),
        "row_counts": {
            "holdout": int(holdout.shape[0]),
            "walk_forward": int(walk_forward.shape[0]),
            "scorecard": int(scorecard.shape[0]),
        },
        "latest_predictions": latest_predictions,
    }
    (REPORT_DIR / f"{suffix}_summary_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one dashboard signal model test.")
    parser.add_argument(
        "--model",
        required=True,
        choices=["logistic", "hist_gradient_boosting", "extra_trees", "random_forest"],
    )
    parser.add_argument("--validation", choices=["holdout", "walk_forward", "both"], default="holdout")
    parser.add_argument("--scope", action="append", choices=SCOPES, help="Optional market scope filter. Repeatable.")
    parser.add_argument("--horizon", action="append", type=int, choices=HORIZONS, help="Optional horizon filter. Repeatable.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scopes = args.scope or SCOPES
    horizons = args.horizon or HORIZONS
    print(json.dumps(run_model_test(args.model, args.validation, scopes, horizons), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
