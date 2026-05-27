from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
warnings.filterwarnings("ignore", message="A single label was found in.*")

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantmarket_market.market_dashboard_signal_research import HORIZONS, SCOPES  # noqa: E402

DATASET_PATH = ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current" / "dashboard_axis_model_dataset_current.csv"
OUTPUT_DIR = ROOT / "service_platform" / "research" / "market_dashboard_signal" / "current"
REPORT_DIR = ROOT / "reports" / "market_dashboard_signal_research" / "flow_model"
MODELS = ["logistic", "logistic_calibrated", "hist_gradient_boosting", "random_forest", "extra_trees"]
LABEL_POLICIES = ["existing", "q2020", "vol_adjusted_q2020", "vol_adjusted_wide_q2020"]
MIN_TEST_YEAR = 2022
MIN_TRAIN_COUNT = 400


@dataclass(frozen=True)
class FitResult:
    rows: list[dict]
    predictions: pd.DataFrame


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


def _add_flow_enhanced_features(dataset: pd.DataFrame) -> pd.DataFrame:
    frame = dataset.copy()
    frame = frame.sort_values(["market_scope", "asof_date"]).reset_index(drop=True)
    flow_cols = [
        "flow_foreign_net_eok",
        "flow_institution_net_eok",
        "flow_individual_net_eok",
        "flow_smart_money_net_eok",
        "flow_foreign_minus_individual_eok",
        "flow_institution_minus_individual_eok",
        "flow_foreign_net_eok_5d_sum",
        "flow_institution_net_eok_5d_sum",
        "flow_individual_net_eok_5d_sum",
        "flow_smart_money_net_eok_5d_sum",
        "kiwoom_foreign_net_eok",
        "kiwoom_institution_net_eok",
        "kiwoom_individual_net_eok",
        "kiwoom_smart_money_net_eok",
        "kiwoom_foreign_minus_individual_eok",
        "kiwoom_foreign_net_eok_5d_sum",
        "kiwoom_institution_net_eok_5d_sum",
        "kiwoom_individual_net_eok_5d_sum",
        "kiwoom_smart_money_net_eok_5d_sum",
        "kiwoom_individual_positive_ratio",
        "kiwoom_foreign_positive_ratio",
        "kiwoom_institution_positive_ratio",
    ]
    flow_cols = [col for col in flow_cols if col in frame.columns]
    for col in flow_cols:
        values = pd.to_numeric(frame[col], errors="coerce")
        frame[col] = values
        grouped = frame.groupby("market_scope", sort=False)[col]
        for window in (20, 60):
            mean = grouped.transform(lambda s: s.rolling(window, min_periods=max(10, window // 2)).mean())
            std = grouped.transform(lambda s: s.rolling(window, min_periods=max(10, window // 2)).std())
            frame[f"{col}_z{window}d"] = (values - mean) / std.replace({0: pd.NA})
        frame[f"{col}_pctile_60d"] = grouped.transform(
            lambda s: s.rolling(60, min_periods=20).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1],
                raw=False,
            )
        )

    pairs = [
        ("flow_smart_money_net_eok_5d_sum_z60d", "flow_individual_net_eok_5d_sum_z60d", "flow_smart_vs_individual_z60d"),
        ("kiwoom_smart_money_net_eok_5d_sum_z60d", "kiwoom_individual_net_eok_5d_sum_z60d", "kiwoom_smart_vs_individual_z60d"),
        ("kiwoom_foreign_positive_ratio_z60d", "kiwoom_individual_positive_ratio_z60d", "kiwoom_foreign_vs_individual_breadth_z60d"),
    ]
    for left, right, out in pairs:
        if left in frame.columns and right in frame.columns:
            frame[out] = frame[left] - frame[right]
    return frame


def _usable_features(frame: pd.DataFrame, feature_cols: list[str], *, min_observed: int = 30) -> list[str]:
    usable = []
    for col in feature_cols:
        values = frame[col].dropna()
        if values.shape[0] >= min_observed and values.nunique() > 1:
            usable.append(col)
    return usable


def _model_pipeline(model_name: str):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if model_name == "logistic":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42),
        )
    if model_name == "logistic_calibrated":
        base = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42),
        )
        return CalibratedClassifierCV(
            estimator=base,
            method="sigmoid",
            cv=TimeSeriesSplit(n_splits=3),
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
    raise ValueError(f"unsupported model: {model_name}")


def _apply_label_policy(dataset: pd.DataFrame, policy: str, scopes: list[str], horizons: list[int]) -> pd.DataFrame:
    frame = dataset.copy()
    frame = frame.sort_values(["market_scope", "asof_date"]).reset_index(drop=True)
    for scope in scopes:
        scope_mask = frame["market_scope"] == scope
        for horizon in horizons:
            label_col = f"flow_label_{policy}_{horizon}d"
            if policy == "existing":
                frame[label_col] = frame[f"direction_label_3class_{horizon}d"]
                continue

            returns = pd.to_numeric(frame.loc[scope_mask, f"forward_return_{horizon}d"], errors="coerce")
            if policy in {"vol_adjusted_q2020", "vol_adjusted_wide_q2020"}:
                vol = returns.rolling(252, min_periods=60).std().abs()
                score = returns / vol.replace({0: pd.NA})
            elif policy == "q2020":
                score = returns
            else:
                raise ValueError(f"unsupported label policy: {policy}")

            valid = score.dropna()
            if valid.empty:
                frame.loc[scope_mask, label_col] = pd.NA
                continue
            lower_q, upper_q = (0.35, 0.65) if policy == "vol_adjusted_wide_q2020" else (0.4, 0.6)
            q40 = float(valid.quantile(lower_q))
            q60 = float(valid.quantile(upper_q))
            labels = pd.Series(pd.NA, index=score.index, dtype="object")
            labels.loc[score <= q40] = "down"
            labels.loc[(score > q40) & (score <= q60)] = "sideways"
            labels.loc[score > q60] = "up"
            frame.loc[scope_mask, label_col] = labels
    return frame


def _evaluate_single_models(
    dataset: pd.DataFrame,
    *,
    label_policy: str,
    scopes: list[str],
    horizons: list[int],
    models: list[str],
    min_train_count: int,
) -> FitResult:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

    feature_cols = _feature_columns(dataset)
    frame = dataset.copy()
    frame["year"] = pd.to_datetime(frame["asof_date"]).dt.year
    rows: list[dict] = []
    pred_rows: list[dict] = []
    for scope in scopes:
        scoped = frame[frame["market_scope"] == scope].sort_values("asof_date")
        years = [int(year) for year in sorted(scoped["year"].dropna().unique()) if int(year) >= MIN_TEST_YEAR]
        for horizon in horizons:
            label_col = f"flow_label_{label_policy}_{horizon}d"
            for test_year in years:
                train = scoped[(scoped["year"] < test_year) & scoped[label_col].notna()].copy()
                test = scoped[(scoped["year"] == test_year) & scoped[label_col].notna()].copy()
                train = train[train[feature_cols].notna().any(axis=1)]
                test = test[test[feature_cols].notna().any(axis=1)]
                if train.shape[0] < min_train_count or test.shape[0] < 30 or train[label_col].nunique() < 3:
                    continue
                usable = _usable_features(train, feature_cols)
                if not usable:
                    continue
                for model_name in models:
                    model = _model_pipeline(model_name)
                    model.fit(train[usable], train[label_col])
                    pred = model.predict(test[usable])
                    probs = model.predict_proba(test[usable])
                    baseline = test[label_col].mode().iloc[0]
                    rows.append(
                        {
                            "model": model_name,
                            "label_policy": label_policy,
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
                    class_index = {str(label): i for i, label in enumerate(model.classes_)}
                    for pos, (_, test_row) in enumerate(test.iterrows()):
                        pred_rows.append(
                            {
                                "model": model_name,
                                "label_policy": label_policy,
                                "market_scope": scope,
                                "forecast_horizon": f"{horizon}d",
                                "test_year": int(test_year),
                                "asof_date": test_row["asof_date"],
                                "actual_label": test_row[label_col],
                                "prob_down": float(probs[pos][class_index.get("down", -1)]) if "down" in class_index else 0.0,
                                "prob_sideways": float(probs[pos][class_index.get("sideways", -1)]) if "sideways" in class_index else 0.0,
                                "prob_up": float(probs[pos][class_index.get("up", -1)]) if "up" in class_index else 0.0,
                            }
                        )
    return FitResult(rows=rows, predictions=pd.DataFrame(pred_rows))


def _ensemble_metrics(single_metrics: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

    if predictions.empty:
        return pd.DataFrame()
    rows = []
    key_cols = ["label_policy", "market_scope", "forecast_horizon", "test_year"]
    history: dict[tuple[str, str, str], pd.DataFrame] = {}
    for key, group in single_metrics.groupby(["label_policy", "market_scope", "forecast_horizon"], dropna=False):
        history[key] = group.copy()

    for key_values, group in predictions.groupby(key_cols, dropna=False):
        label_policy, scope, horizon, test_year = key_values
        actual = group[["asof_date", "actual_label"]].drop_duplicates().sort_values("asof_date")
        model_groups = {
            model: g.set_index("asof_date")[["prob_down", "prob_sideways", "prob_up"]].sort_index()
            for model, g in group.groupby("model")
        }
        if len(model_groups) < 2:
            continue
        aligned_models = sorted(model_groups)
        probs = [model_groups[model].loc[actual["asof_date"]].to_numpy() for model in aligned_models]
        prev = history.get((label_policy, scope, horizon), pd.DataFrame())
        prev = prev[prev["test_year"] < int(test_year)] if not prev.empty else prev
        variants: list[tuple[str, list[str], list[float]]] = [
            ("ensemble_mean_all", aligned_models, [1.0] * len(aligned_models)),
        ]
        if not prev.empty:
            avg = (
                prev.groupby("model", as_index=False)["balanced_accuracy"]
                .mean()
                .sort_values("balanced_accuracy", ascending=False)
            )
            weights = []
            for model in aligned_models:
                val = avg.loc[avg["model"] == model, "balanced_accuracy"]
                weights.append(max(float(val.iloc[0]) if not val.empty else 0.0, 0.001))
            variants.append(("ensemble_weighted_prev_balacc", aligned_models, weights))
            top2 = avg["model"].head(2).tolist()
            if len(top2) >= 2:
                variants.append(("ensemble_top2_prev_balacc", top2, [1.0] * len(top2)))

        for model_name, selected_models, weights in variants:
            selected_probs = [model_groups[model].loc[actual["asof_date"]].to_numpy() for model in selected_models]
            total = sum(weights)
            combined = sum(prob * weight for prob, weight in zip(selected_probs, weights)) / total
            labels = pd.Series(combined.argmax(axis=1)).map({0: "down", 1: "sideways", 2: "up"}).to_list()
            baseline = actual["actual_label"].mode().iloc[0]
            rows.append(
                {
                    "model": model_name,
                    "label_policy": label_policy,
                    "validation": "walk_forward",
                    "market_scope": scope,
                    "forecast_horizon": horizon,
                    "test_year": int(test_year),
                    "train_start": None,
                    "train_end": None,
                    "test_start": actual["asof_date"].min(),
                    "test_end": actual["asof_date"].max(),
                    "train_count": None,
                    "test_count": int(actual.shape[0]),
                    "feature_count": None,
                    "accuracy": float(accuracy_score(actual["actual_label"], labels)),
                    "balanced_accuracy": float(balanced_accuracy_score(actual["actual_label"], labels)),
                    "macro_f1": float(f1_score(actual["actual_label"], labels, average="macro")),
                    "baseline_accuracy": float(accuracy_score(actual["actual_label"], [baseline] * actual.shape[0])),
                    "ensemble_members": ",".join(selected_models),
                }
            )
    return pd.DataFrame(rows)


def _scorecard(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()
    return (
        metrics.groupby(["model", "label_policy", "market_scope", "forecast_horizon"], as_index=False)
        .agg(
            walk_forward_years=("test_year", "count"),
            walk_forward_balanced_accuracy_avg=("balanced_accuracy", "mean"),
            walk_forward_macro_f1_avg=("macro_f1", "mean"),
            walk_forward_accuracy_avg=("accuracy", "mean"),
            walk_forward_baseline_accuracy_avg=("baseline_accuracy", "mean"),
        )
        .sort_values(
            ["forecast_horizon", "market_scope", "walk_forward_balanced_accuracy_avg", "walk_forward_macro_f1_avg"],
            ascending=[True, True, False, False],
        )
    )


def run_research(
    min_asof_date: str,
    label_policies: list[str],
    scopes: list[str],
    horizons: list[int],
    models: list[str] | None = None,
) -> dict:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"dataset is missing: {DATASET_PATH}")
    dataset = pd.read_csv(DATASET_PATH)
    dataset["asof_date"] = pd.to_datetime(dataset["asof_date"]).dt.strftime("%Y-%m-%d")
    dataset = dataset[dataset["asof_date"] >= min_asof_date].copy()
    dataset = _add_flow_enhanced_features(dataset)
    all_metrics = []
    all_predictions = []
    models = models or MODELS
    for label_policy in label_policies:
        labeled = _apply_label_policy(dataset, label_policy, scopes, horizons)
        result = _evaluate_single_models(
            labeled,
            label_policy=label_policy,
            scopes=scopes,
            horizons=horizons,
            models=models,
            min_train_count=MIN_TRAIN_COUNT,
        )
        single = pd.DataFrame(result.rows)
        ensemble = _ensemble_metrics(single, result.predictions)
        all_metrics.extend([single, ensemble])
        all_predictions.append(result.predictions)

    metrics = pd.concat([m for m in all_metrics if not m.empty], ignore_index=True)
    predictions = pd.concat([p for p in all_predictions if not p.empty], ignore_index=True)
    scorecard = _scorecard(metrics)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUTPUT_DIR / "dashboard_axis_flow_model_walk_forward_current.csv"
    prediction_path = OUTPUT_DIR / "dashboard_axis_flow_model_predictions_current.csv"
    scorecard_path = OUTPUT_DIR / "dashboard_axis_flow_model_scorecard_current.csv"
    metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")
    predictions.to_csv(prediction_path, index=False, encoding="utf-8-sig")
    scorecard.to_csv(scorecard_path, index=False, encoding="utf-8-sig")
    summary = {
        "status": "ok",
        "generated_at": _now_iso(),
        "min_asof_date": min_asof_date,
        "label_policies": label_policies,
        "scopes": scopes,
        "horizons": [f"{h}d" for h in horizons],
        "models": models,
        "min_test_year": MIN_TEST_YEAR,
        "min_train_count": MIN_TRAIN_COUNT,
        "dataset_rows": int(dataset.shape[0]),
        "row_counts": {
            "walk_forward": int(metrics.shape[0]),
            "predictions": int(predictions.shape[0]),
            "scorecard": int(scorecard.shape[0]),
        },
        "outputs": {
            "metrics": str(metrics_path),
            "predictions": str(prediction_path),
            "scorecard": str(scorecard_path),
        },
    }
    (REPORT_DIR / "dashboard_axis_flow_model_summary_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 2020+ flow-only dashboard signal model research.")
    parser.add_argument("--min-asof-date", default="2020-01-02")
    parser.add_argument("--label-policy", action="append", choices=LABEL_POLICIES)
    parser.add_argument("--scope", action="append", choices=SCOPES)
    parser.add_argument("--horizon", action="append", type=int, choices=HORIZONS)
    parser.add_argument("--model", action="append", choices=MODELS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_research(
        min_asof_date=args.min_asof_date,
        label_policies=args.label_policy or LABEL_POLICIES,
        scopes=args.scope or SCOPES,
        horizons=args.horizon or HORIZONS,
        models=args.model or MODELS,
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
